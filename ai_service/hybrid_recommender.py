from __future__ import annotations

from pathlib import Path

from product_service.models import Product

from .lstm.models import UserBehavior

ACTION_WEIGHTS = {
    UserBehavior.ACTION_ADD_TO_CART: 1.0,
    UserBehavior.ACTION_CLICK: 0.65,
    UserBehavior.ACTION_VIEW: 0.35,
}


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {key: 0.0 for key in scores}
    return {key: float(value / max_score) for key, value in scores.items()}


def _safe_weight(value, default: float) -> float:
    try:
        parsed = float(value)
        if parsed < 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


def _build_lstm_like_scores(user_id: int, product_ids: list[int]) -> dict[int, float]:
    rows = list(
        UserBehavior.objects.filter(user_id=user_id)
        .order_by("-timestamp")
        .values("product_id", "action")[:300]
    )
    scores = {product_id: 0.0 for product_id in product_ids}
    for rank, row in enumerate(rows):
        product_id = int(row["product_id"])
        if product_id not in scores:
            continue
        action_weight = ACTION_WEIGHTS.get(row["action"], 0.2)
        recency_weight = 0.92**rank
        scores[product_id] += action_weight * recency_weight
    return _normalize(scores)


def _build_graph_scores(user_id: int, product_ids: list[int]) -> dict[int, float]:
    user_products = set(
        UserBehavior.objects.filter(user_id=user_id).values_list("product_id", flat=True)
    )
    scores = {product_id: 0.0 for product_id in product_ids}
    if not user_products:
        return scores

    related_user_ids = set(
        UserBehavior.objects.filter(product_id__in=user_products).values_list("user_id", flat=True)
    )
    if not related_user_ids:
        return scores

    related_rows = UserBehavior.objects.filter(user_id__in=related_user_ids).values("product_id", "action")
    for row in related_rows:
        product_id = int(row["product_id"])
        if product_id not in scores:
            continue
        if product_id in user_products:
            continue
        scores[product_id] += ACTION_WEIGHTS.get(row["action"], 0.2)

    return _normalize(scores)


def _build_rag_scores(query: str, products: list[Product]) -> dict[int, float]:
    scores = {product.id: 0.0 for product in products}
    if not query or not query.strip() or not products:
        return scores

    try:
        from ai_service.rag import vector_store
    except Exception:
        return scores

    docs = [
        {
            "name": product.name,
            "description": product.name,
            "category": product.category.name,
        }
        for product in products
    ]

    index_path = Path("product_index.faiss")
    try:
        if not index_path.exists():
            vector_store.build_index(docs)
        result_indexes = vector_store.search(query, top_k=min(30, len(products)))
    except Exception:
        try:
            vector_store.build_index(docs)
            result_indexes = vector_store.search(query, top_k=min(30, len(products)))
        except Exception:
            return scores

    ranked_scores: dict[int, float] = {}
    total = max(len(result_indexes), 1)
    for rank, index in enumerate(result_indexes):
        if index < 0 or index >= len(products):
            continue
        product_id = products[index].id
        ranked_scores[product_id] = (total - rank) / total

    for product_id, value in ranked_scores.items():
        scores[product_id] = value
    return _normalize(scores)


def generate_hybrid_recommendations(
    user_id: int,
    query: str,
    top_k: int = 10,
    w1: float = 0.4,
    w2: float = 0.35,
    w3: float = 0.25,
) -> tuple[list[dict], dict]:
    products = list(Product.objects.select_related("category").all())
    if not products:
        return [], {"w1": 0.4, "w2": 0.35, "w3": 0.25}

    product_ids = [product.id for product in products]

    w1 = _safe_weight(w1, 0.4)
    w2 = _safe_weight(w2, 0.35)
    w3 = _safe_weight(w3, 0.25)
    total_weight = w1 + w2 + w3
    if total_weight <= 0:
        w1, w2, w3 = 0.4, 0.35, 0.25
        total_weight = 1.0
    w1, w2, w3 = w1 / total_weight, w2 / total_weight, w3 / total_weight

    lstm_scores = _build_lstm_like_scores(user_id, product_ids)
    graph_scores = _build_graph_scores(user_id, product_ids)
    rag_scores = _build_rag_scores(query, products)

    user_products = set(
        UserBehavior.objects.filter(user_id=user_id).values_list("product_id", flat=True)
    )

    results = []
    for product in products:
        lstm_score = float(lstm_scores.get(product.id, 0.0))
        graph_score = float(graph_scores.get(product.id, 0.0))
        rag_score = float(rag_scores.get(product.id, 0.0))
        final_score = (w1 * lstm_score) + (w2 * graph_score) + (w3 * rag_score)
        if product.id in user_products:
            final_score *= 0.92

        results.append(
            {
                "product_id": product.id,
                "name": product.name,
                "category": product.category.name,
                "price": product.price,
                "scores": {
                    "lstm": round(lstm_score, 6),
                    "graph": round(graph_score, 6),
                    "rag": round(rag_score, 6),
                    "final_score": round(final_score, 6),
                },
            }
        )

    results.sort(key=lambda item: item["scores"]["final_score"], reverse=True)
    return results[: max(1, int(top_k))], {
        "w1": round(w1, 4),
        "w2": round(w2, 4),
        "w3": round(w3, 4),
    }
