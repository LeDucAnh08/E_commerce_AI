import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from order_service.models import OrderItem
from product_service.models import Product

from .hybrid_recommender import generate_hybrid_recommendations
from .lstm.models import UserBehavior


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _parse_json(request):
    if not request.body:
        return {}, None
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, _bad_request("Invalid JSON")


def _serialize_behavior(record: UserBehavior) -> dict:
    return {
        "id": record.id,
        "user_id": record.user_id,
        "product_id": record.product_id,
        "action": record.action,
        "timestamp": record.timestamp.isoformat(),
    }


def _build_reason(scores: dict) -> str:
    components = [
        ("LSTM", float(scores.get("lstm", 0.0))),
        ("Graph", float(scores.get("graph", 0.0))),
        ("RAG", float(scores.get("rag", 0.0))),
    ]
    components.sort(key=lambda item: item[1], reverse=True)
    strong = [name for name, value in components if value >= 0.35]
    if len(strong) >= 2:
        return "+".join(strong[:2])
    if strong:
        return strong[0]
    return "+".join(name for name, _ in components[:2])


def _parse_limit(value, default: int = 5, maximum: int = 20) -> int:
    try:
        limit = int(value or default)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


def _ordered_ids(queryset) -> list[int]:
    return [int(product_id) for product_id in queryset.values_list("id", flat=True)]


def _product_type(product: Product) -> str | None:
    if hasattr(product, "book_details"):
        return "book"
    if hasattr(product, "electronics_details"):
        return "electronics"
    if hasattr(product, "fashion_details"):
        return "fashion"
    return None


def _similar_product_ids(product_id: int, limit: int) -> list[int]:
    product = (
        Product.objects.using("product")
        .select_related("category")
        .filter(id=product_id)
        .first()
    )
    if not product:
        return []

    products = Product.objects.using("product").select_related("category").exclude(id=product_id)
    product_type = _product_type(product)
    if product_type == "book":
        products = products.filter(book_details__isnull=False)
    elif product_type == "electronics":
        products = products.filter(electronics_details__isnull=False)
    elif product_type == "fashion":
        products = products.filter(fashion_details__isnull=False)

    ids = _ordered_ids(products.filter(category=product.category).order_by("price")[:limit])
    if len(ids) < limit:
        fallback = (
            Product.objects.using("product")
            .exclude(id=product_id)
            .exclude(id__in=ids)
            .order_by("category__name", "price")[: limit - len(ids)]
        )
        ids.extend(_ordered_ids(fallback))
    return ids[:limit]


@csrf_exempt
def search_products(request):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    query = str(request.GET.get("q", "")).strip()
    limit = _parse_limit(request.GET.get("limit"), default=10)
    if not query:
        return _bad_request("Missing q")

    products = Product.objects.using("product").select_related("category")
    matches = (
        products.filter(name__icontains=query)
        | products.filter(category__name__icontains=query)
        | products.filter(book_details__author__icontains=query)
        | products.filter(electronics_details__brand__icontains=query)
        | products.filter(fashion_details__color__icontains=query)
    )
    query_lower = query.lower()
    category_aliases = {
        "Books": {"book", "books", "sach", "sách"},
        "Electronics": {
            "electronics",
            "dien tu",
            "điện tử",
            "laptop",
            "notebook",
            "keyboard",
            "monitor",
            "headphone",
            "headphones",
            "earbuds",
            "tablet",
        },
        "Fashion": {"fashion", "thoi trang", "thời trang", "shirt", "hoodie", "sneaker", "jacket", "wallet"},
    }
    for category_name, aliases in category_aliases.items():
        if any(alias in query_lower for alias in aliases):
            matches = matches | products.filter(category__name=category_name)

    product_ids = _ordered_ids(matches.distinct().order_by("category__name", "price")[:limit])
    return JsonResponse({"query": query, "product_ids": product_ids})


@csrf_exempt
def frequently_bought_together(request):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    raw_product_ids = str(request.GET.get("product_ids", "")).strip()
    limit = _parse_limit(request.GET.get("limit"), default=5)
    try:
        product_ids = {
            int(value)
            for value in raw_product_ids.split(",")
            if value.strip()
        }
    except ValueError:
        return _bad_request("Invalid product_ids")

    if not product_ids:
        return _bad_request("Missing product_ids")

    order_ids = (
        OrderItem.objects.using("default")
        .filter(product_id__in=product_ids)
        .values_list("order_id", flat=True)
        .distinct()
    )
    co_items = (
        OrderItem.objects.using("default")
        .filter(order_id__in=order_ids)
        .exclude(product_id__in=product_ids)
        .values_list("product_id", flat=True)
    )

    scores: dict[int, int] = {}
    for product_id in co_items:
        scores[int(product_id)] = scores.get(int(product_id), 0) + 1

    ranked_ids = [
        product_id
        for product_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ][:limit]

    if len(ranked_ids) < limit:
        seed_product = Product.objects.using("product").filter(id__in=product_ids).first()
        if seed_product:
            fallback = (
                Product.objects.using("product")
                .filter(category=seed_product.category)
                .exclude(id__in=set(ranked_ids) | product_ids)
                .order_by("price")[: limit - len(ranked_ids)]
            )
            ranked_ids.extend(_ordered_ids(fallback))

    return JsonResponse({"product_ids": ranked_ids[:limit]})


@csrf_exempt
def similar_products(request, product_id: int):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    limit = _parse_limit(request.GET.get("limit"), default=5)
    product_ids = _similar_product_ids(product_id, limit)
    if not product_ids:
        return _bad_request("Product not found", status=404)
    return JsonResponse({"product_id": product_id, "product_ids": product_ids})


@csrf_exempt
def collect_behavior(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    data, error = _parse_json(request)
    if error:
        return error

    try:
        user_id = int(data.get("user_id"))
        product_id = int(data.get("product_id"))
    except (TypeError, ValueError):
        return _bad_request("Invalid user_id or product_id")

    action = data.get("action")
    if action not in {choice[0] for choice in UserBehavior.ACTION_CHOICES}:
        return _bad_request("Invalid action")

    timestamp_raw = data.get("timestamp")
    if timestamp_raw:
        try:
            timestamp = timezone.datetime.fromisoformat(timestamp_raw)
        except ValueError:
            return _bad_request("Invalid timestamp")
    else:
        timestamp = timezone.now()

    record = UserBehavior.objects.create(
        user_id=user_id,
        product_id=product_id,
        action=action,
        timestamp=timestamp,
    )

    return JsonResponse(_serialize_behavior(record), status=201)


@csrf_exempt
def recommend(request):
    if request.method == "GET":
        query_data = request.GET
        query = str(query_data.get("query", "")).strip()
        try:
            user_id = int(query_data.get("user_id"))
        except (TypeError, ValueError):
            return _bad_request("Invalid user_id")

        try:
            limit = int(query_data.get("limit", 5))
        except (TypeError, ValueError):
            return _bad_request("Invalid limit")
        if limit <= 0:
            return _bad_request("limit must be positive")

        recommendations, _ = generate_hybrid_recommendations(
            user_id=user_id,
            query=query,
            top_k=limit,
            w1=query_data.get("w1", 0.4),
            w2=query_data.get("w2", 0.35),
            w3=query_data.get("w3", 0.25),
        )

        payload = [
            {
                "product_id": item["product_id"],
                "score": item["scores"]["final_score"],
                "reason": _build_reason(item["scores"]),
            }
            for item in recommendations
        ]

        return JsonResponse({"user_id": user_id, "recommendations": payload})

    if request.method == "POST":
        data, error = _parse_json(request)
        if error:
            return error

        try:
            user_id = int(data.get("user_id"))
        except (TypeError, ValueError):
            return _bad_request("Invalid user_id")

        query = str(data.get("query", "")).strip()

        try:
            top_k = int(data.get("top_k", 10))
        except (TypeError, ValueError):
            return _bad_request("Invalid top_k")
        if top_k <= 0:
            return _bad_request("top_k must be positive")

        recommendations, weights = generate_hybrid_recommendations(
            user_id=user_id,
            query=query,
            top_k=top_k,
            w1=data.get("w1", 0.4),
            w2=data.get("w2", 0.35),
            w3=data.get("w3", 0.25),
        )

        return JsonResponse(
            {
                "user_id": user_id,
                "query": query,
                "weights": weights,
                "formula": "final_score = w1 * lstm + w2 * graph + w3 * rag",
                "recommendations": recommendations,
            }
        )

    return _bad_request("Method not allowed", status=405)


@csrf_exempt
def chat(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    data, error = _parse_json(request)
    if error:
        return error

    message = data.get("message")
    if not message:
        return _bad_request("Missing message")

    return JsonResponse(
        {
            "message": message,
            "response": "Stub response. Implement chatbot here.",
        }
    )
