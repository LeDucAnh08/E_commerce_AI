import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

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
