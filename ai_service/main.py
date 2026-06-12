from __future__ import annotations

import os
import re
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

try:
    from neo4j import GraphDatabase
except ModuleNotFoundError:
    GraphDatabase = None

try:
    from ai_service.rag import vector_store
except Exception:
    vector_store = None

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:
    ChatGoogleGenerativeAI = None

try:
    from langchain_openai import ChatOpenAI
except Exception:
    ChatOpenAI = None

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "model_best.keras"
FAISS_INDEX_PATH = BASE_DIR / "product_index.faiss"

app = FastAPI(title="E-commerce AI Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendationItem(BaseModel):
    product_id: int
    score: float
    reason: str


class RecommendationResponse(BaseModel):
    user_id: int
    recommendations: list[RecommendationItem]


class ChatRequest(BaseModel):
    message: str


class ChatProduct(BaseModel):
    id: int
    name: str
    category: str
    type: str
    price: float
    stock: int
    image_url: str


class ChatResponse(BaseModel):
    reply: str
    products: list[ChatProduct]


ACTION_WEIGHTS = {
    "buy": 1.0,
    "add_to_cart": 0.85,
    "click": 0.6,
    "view": 0.35,
}

load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value if value is not None else default


@lru_cache(maxsize=1)
def get_neo4j_driver():
    if GraphDatabase is None:
        raise RuntimeError("Missing dependency: neo4j. Install the neo4j Python driver.")
    uri = _env("NEO4J_URI", _env("NEO4J_URL", "neo4j+s://localhost:7687"))
    username = _env("NEO4J_USERNAME", _env("NEO4J_USER", "neo4j"))
    password = _env("NEO4J_PASSWORD", "")
    if not uri or not username or not password:
        raise RuntimeError("Missing Neo4j connection variables in .env")
    return GraphDatabase.driver(uri, auth=(username, password))


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {key: 0.0 for key in scores}
    return {key: float(val / max_score) for key, val in scores.items()}


def _safe_top(values: list[tuple[int, float]], limit: int) -> dict[int, float]:
    merged: dict[int, float] = defaultdict(float)
    for product_id, score in values:
        merged[int(product_id)] += float(score)
    ordered = sorted(merged.items(), key=lambda item: item[1], reverse=True)[:limit]
    return _normalize(dict(ordered))


def fetch_user_history(user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    query = """
    MATCH (u:User {id: $user_id})-[r:BUY|VIEW|CLICK|ADD_TO_CART]->(p:Product)
    RETURN p.id AS product_id, p.name AS name, p.category AS category,
           type(r) AS action, coalesce(r.timestamp, '') AS timestamp
    ORDER BY timestamp DESC
    LIMIT $limit
    """
    try:
        with get_neo4j_driver().session(database=_env("NEO4J_DATABASE", "neo4j")) as session:
            rows = session.run(query, user_id=user_id, limit=limit)
            return [dict(row) for row in rows]
    except Exception:
        return []


def _derive_query_from_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return ""
    parts: list[str] = []
    for row in history[:8]:
        name = str(row.get("name") or "").strip()
        category = str(row.get("category") or "").strip()
        action = str(row.get("action") or "").lower().strip()
        if name:
            parts.append(name)
        if category:
            parts.append(category)
        if action in {"buy", "add_to_cart"}:
            parts.append("recommended")
    return " ".join(parts)


def lstm_predict(user_id: int, candidate_ids: list[int] | None = None) -> dict[int, float]:
    history = fetch_user_history(user_id, limit=100)
    if not history:
        return {pid: 0.0 for pid in (candidate_ids or [])}

    scores: dict[int, float] = defaultdict(float)
    for rank, row in enumerate(history):
        product_id = int(row.get("product_id") or 0)
        if candidate_ids is not None and product_id not in candidate_ids:
            continue
        action = str(row.get("action") or "view").lower()
        action_weight = ACTION_WEIGHTS.get(action, 0.2)
        recency_weight = 0.93**rank
        scores[product_id] += action_weight * recency_weight

    return _normalize(dict(scores))


class Neo4jRecommender:
    def __init__(self) -> None:
        self.database = _env("NEO4J_DATABASE", "neo4j")

    def get_recommendations(self, user_id: int, limit: int = 50) -> dict[int, float]:
        query = """
        MATCH (u:User {id: $user_id})-[r:BUY|VIEW|CLICK|ADD_TO_CART]->(p:Product)
        OPTIONAL MATCH (p)-[s:SIMILAR]->(rec:Product)
        OPTIONAL MATCH (other:User)-[r2:BUY|VIEW|CLICK|ADD_TO_CART]->(rec)
        WHERE rec IS NOT NULL AND NOT (u)-[:BUY|VIEW|CLICK|ADD_TO_CART]->(rec)
        WITH rec,
             count(DISTINCT other) AS user_hits,
             max(coalesce(s.score, 0.0)) AS sim_score
        RETURN rec.id AS product_id,
               (user_hits * 1.0) + coalesce(sim_score, 0.0) AS score
        ORDER BY score DESC
        LIMIT $limit
        """
        fallback_query = """
        MATCH (u:User {id: $user_id})-[:BUY|VIEW|CLICK|ADD_TO_CART]->(p:Product)-[s:SIMILAR]->(rec:Product)
        WHERE NOT (u)-[:BUY|VIEW|CLICK|ADD_TO_CART]->(rec)
        RETURN rec.id AS product_id, coalesce(s.score, 1.0) AS score
        ORDER BY score DESC
        LIMIT $limit
        """
        try:
            with get_neo4j_driver().session(database=self.database) as session:
                rows = session.run(query, user_id=user_id, limit=limit)
                data = [(row["product_id"], row["score"]) for row in rows if row["product_id"] is not None]
                if not data:
                    rows = session.run(fallback_query, user_id=user_id, limit=limit)
                    data = [(row["product_id"], row["score"]) for row in rows if row["product_id"] is not None]
        except Exception:
            data = []

        return _safe_top([(int(pid), float(score)) for pid, score in data], limit)


neo4j_recommender = Neo4jRecommender()


def rag_recommend(query: str, limit: int = 50) -> dict[int, float]:
    if not query.strip() or vector_store is None:
        return {}

    try:
        if not FAISS_INDEX_PATH.exists():
            return {}
        indexes = vector_store.search(query, top_k=limit)
    except Exception:
        return {}

    scores: dict[int, float] = {}
    total = max(len(indexes), 1)
    for rank, idx in enumerate(indexes):
        product_id = int(idx)
        scores[product_id] = (total - rank) / total
    return _normalize(scores)


def hybrid_score(
    lstm_scores: dict[int, float],
    graph_scores: dict[int, float],
    rag_scores: dict[int, float],
    w1: float = 0.4,
    w2: float = 0.35,
    w3: float = 0.25,
) -> list[dict[str, Any]]:
    product_ids = set(lstm_scores) | set(graph_scores) | set(rag_scores)
    results: list[dict[str, Any]] = []
    for product_id in product_ids:
        lstm = float(lstm_scores.get(product_id, 0.0))
        graph = float(graph_scores.get(product_id, 0.0))
        rag = float(rag_scores.get(product_id, 0.0))
        final = (w1 * lstm) + (w2 * graph) + (w3 * rag)

        reason_parts = []
        if lstm >= 0.35:
            reason_parts.append("LSTM")
        if graph >= 0.35:
            reason_parts.append("Graph")
        if rag >= 0.35:
            reason_parts.append("RAG")
        reason = "+".join(reason_parts[:2]) if reason_parts else "Hybrid"

        results.append(
            {
                "product_id": int(product_id),
                "score": round(final, 6),
                "reason": reason,
                "components": {
                    "lstm": round(lstm, 6),
                    "graph": round(graph, 6),
                    "rag": round(rag, 6),
                },
            }
        )

    results.sort(key=lambda item: item["score"], reverse=True)
    return results


@app.get("/recommend", response_model=RecommendationResponse)
def recommend(
    user_id: int = Query(..., description="User identifier"),
    limit: int = Query(5, ge=1, le=100),
    query: str | None = Query(None, description="Optional semantic query"),
):
    history = fetch_user_history(user_id, limit=100)
    user_query = (query or _derive_query_from_history(history)).strip()

    lstm_scores = lstm_predict(user_id)
    graph_scores = neo4j_recommender.get_recommendations(user_id, limit=max(limit * 3, 20))
    rag_scores = rag_recommend(user_query, limit=max(limit * 3, 20))

    recommendations = hybrid_score(lstm_scores, graph_scores, rag_scores)
    if not recommendations:
        raise HTTPException(status_code=404, detail="No recommendations available")

    payload = recommendations[:limit]
    return {"user_id": user_id, "recommendations": payload}


def build_llm():
    """Build LLM from .env (prefer Gemini > GitHub Models > OpenAI)."""
    if ChatGoogleGenerativeAI is None and ChatOpenAI is None:
        return None

    gemini_key = _env("GEMINI_API_KEY", "")
    github_token = _env("GITHUB_TOKEN", "")
    openai_key = _env("OPENAI_API_KEY", "")

    if gemini_key:
        try:
            model_name = _env("GEMINI_MODEL", "gemini-1.5-flash")
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.7,
                google_api_key=gemini_key,
            )
        except Exception:
            pass

    if github_token and ChatOpenAI is not None:
        try:
            model_name = _env("GITHUB_MODEL", "openai/gpt-4o-mini")
            base_url = _env("GITHUB_MODELS_BASE_URL", "https://models.github.ai/inference")
            return ChatOpenAI(
                model=model_name,
                temperature=0.7,
                api_key=github_token,
                base_url=base_url,
            )
        except Exception:
            pass

    if openai_key:
        try:
            model_name = _env("OPENAI_MODEL", "gpt-3.5-turbo")
            return ChatOpenAI(
                model=model_name,
                temperature=0.7,
                api_key=openai_key,
            )
        except Exception:
            pass

    return None


def parse_intent_and_entities(message: str) -> tuple[str, dict[str, str]]:
    """Simple NLP: extract price, category, brand from message."""
    message_lower = message.lower()
    intent = "search"

    entities: dict[str, str] = {}

    # Keyword matching for categories
    categories = ["laptop", "phone", "tablet", "camera", "keyboard", "mouse", "monitor", "gaming"]
    for cat in categories:
        if cat in message_lower:
            entities["category"] = cat
            break

    # Price extraction: "dưới X", "từ X đến Y", "X triệu"
    import re

    price_patterns = [
        r"dưới\s+(\d+)\s*(?:triệu|tr|VND|đ)?",
        r"từ\s+(\d+)\s*(?:triệu|tr)?\s*đến\s+(\d+)\s*(?:triệu|tr)?",
        r"(\d+)\s*(?:triệu|tr|t)",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, message_lower)
        if match:
            if len(match.groups()) >= 2 and match.group(2):
                entities["price_max"] = str(int(match.group(2)) * 1_000_000)
            else:
                entities["price_max"] = str(int(match.group(1)) * 1_000_000)
            break

    # Brand keywords
    brands = ["apple", "samsung", "asus", "acer", "dell", "hp", "lenovo", "lg", "sony"]
    for brand in brands:
        if brand in message_lower:
            entities["brand"] = brand
            break

    # Intent detection
    if any(word in message_lower for word in ["so sánh", "khác nhau", "cái nào tốt"]):
        intent = "compare"
    elif any(word in message_lower for word in ["đánh giá", "review", "như thế nào", "tốt không"]):
        intent = "review"
    elif any(word in message_lower for word in ["giá", "bao nhiêu", "chi phí", "giá cả"]):
        intent = "price"

    return intent, entities


@lru_cache(maxsize=1)
def _load_catalog_for_chatbot() -> list[dict[str, Any]]:
    """Load product catalog from Django's product DB for chatbot retrieval."""
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "E_commerce.settings")
        import django

        django.setup()
        from product_service.models import Product
    except Exception:
        return []

    try:
        products = (
            Product.objects.using("product")
            .select_related("category")
            .order_by("id")
        )
        return [_product_to_chatbot_doc(product) for product in products]
    except Exception:
        return []


def _product_to_chatbot_doc(product: Any) -> dict[str, Any]:
    details: list[str] = []
    product_type = "general"

    if hasattr(product, "book_details"):
        product_type = "book"
        details.extend(
            [
                f"author {product.book_details.author}",
                f"publisher {product.book_details.publisher}",
                f"isbn {product.book_details.isbn}",
            ]
        )
    elif hasattr(product, "electronics_details"):
        product_type = "electronics"
        details.extend(
            [
                f"brand {product.electronics_details.brand}",
                f"warranty {product.electronics_details.warranty} months",
            ]
        )
    elif hasattr(product, "fashion_details"):
        product_type = "fashion"
        details.extend(
            [
                f"size {product.fashion_details.size}",
                f"color {product.fashion_details.color}",
            ]
        )

    description = " ".join(
        [
            product.name,
            product.category.name,
            product_type,
            *details,
            f"price {product.price}",
            f"stock {product.stock}",
        ]
    )
    return {
        "id": int(product.id),
        "name": product.name,
        "category": product.category.name,
        "type": product_type,
        "price": float(product.price),
        "stock": int(product.stock),
        "image_url": product.image_url,
        "description": description,
    }


def _ensure_product_index(catalog: list[dict[str, Any]]) -> None:
    if vector_store is None or not catalog:
        return

    meta_path = BASE_DIR / "product_index_meta.json"
    expected_ids = [item["id"] for item in catalog]
    needs_build = not FAISS_INDEX_PATH.exists() or not meta_path.exists()

    if not needs_build:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            needs_build = meta.get("product_ids") != expected_ids
        except (OSError, json.JSONDecodeError):
            needs_build = True

    if needs_build:
        vector_store.build_index(catalog)


def _keyword_product_ids(message: str, catalog: list[dict[str, Any]], limit: int) -> list[int]:
    query = message.lower()
    tokens = [token for token in re.findall(r"\w+", query) if len(token) > 2]
    scored: list[tuple[int, int]] = []

    for product in catalog:
        haystack = " ".join(
            [
                product["name"],
                product["category"],
                product["type"],
                product["description"],
            ]
        ).lower()
        score = sum(1 for token in tokens if token in haystack)
        if product["category"].lower() in query:
            score += 3
        if product["type"].lower() in query:
            score += 2
        if score:
            scored.append((product["id"], score))

    if not scored:
        return []

    scored.sort(key=lambda item: item[1], reverse=True)
    return [product_id for product_id, _ in scored[:limit]]


def _is_product_query(message: str, catalog: list[dict[str, Any]]) -> bool:
    query = message.lower()
    shopping_keywords = {
        "buy",
        "shop",
        "shopping",
        "product",
        "products",
        "recommend",
        "suggest",
        "compare",
        "price",
        "cheap",
        "expensive",
        "stock",
        "book",
        "books",
        "electronics",
        "fashion",
        "laptop",
        "headphone",
        "hoodie",
        "sneaker",
        "mua",
        "ban",
        "bán",
        "san pham",
        "sản phẩm",
        "goi y",
        "gợi ý",
        "de xuat",
        "đề xuất",
        "tu van",
        "tư vấn",
        "gia",
        "giá",
        "re",
        "rẻ",
        "dat",
        "đắt",
        "so sanh",
        "so sánh",
        "sach",
        "sách",
        "dien tu",
        "điện tử",
        "thoi trang",
        "thời trang",
    }
    if any(keyword in query for keyword in shopping_keywords):
        return True

    stopwords = {
        "for",
        "the",
        "and",
        "you",
        "your",
        "what",
        "why",
        "how",
        "are",
        "can",
        "toi",
        "tôi",
        "ban",
        "bạn",
        "cho",
        "hoi",
        "hỏi",
        "cua",
        "của",
        "nay",
        "này",
        "la",
        "là",
    }
    tokens = {
        token
        for token in re.findall(r"\w+", query)
        if len(token) > 2 and token not in stopwords
    }
    if not tokens:
        return False

    for product in catalog:
        catalog_tokens = {
            token
            for token in re.findall(
                r"\w+",
                f"{product['name']} {product['category']} {product['type']} {product['description']}".lower(),
            )
            if len(token) > 2 and token not in stopwords
        }
        if tokens & catalog_tokens:
            return True

    return False


def _chatbot_products_payload(
    product_ids: list[int],
    product_details: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    payload = []
    for product_id in product_ids:
        product = product_details.get(product_id)
        if not product:
            continue
        payload.append(
            {
                "id": product["id"],
                "name": product["name"],
                "category": product["category"],
                "type": product["type"],
                "price": product["price"],
                "stock": product["stock"],
                "image_url": product["image_url"],
            }
        )
    return payload


def retrieve_products_for_chatbot(message: str, limit: int = 5) -> dict[str, Any]:
    """Retrieve catalog products using FAISS, with DB keyword fallback."""
    products_data: dict[str, Any] = {"ids": [], "details": {}}
    catalog = _load_catalog_for_chatbot()
    products_data["details"] = {item["id"]: item for item in catalog}

    if not catalog:
        return products_data

    if not _is_product_query(message, catalog):
        return products_data

    if vector_store is not None:
        try:
            _ensure_product_index(catalog)
            if FAISS_INDEX_PATH.exists():
                result_ids = vector_store.search(message, top_k=limit)
                valid_ids = {item["id"] for item in catalog}
                products_data["ids"] = [pid for pid in result_ids if pid in valid_ids][:limit]
        except Exception:
            products_data["ids"] = []

    if not products_data["ids"]:
        products_data["ids"] = _keyword_product_ids(message, catalog, limit)

    return products_data


def generate_chatbot_reply(
    message: str,
    products_ids: list[int],
    product_details: dict[int, dict[str, Any]] | None = None,
) -> str:
    """Generate natural language reply using LLM."""
    llm = build_llm()
    product_details = product_details or {}
    products = [product_details[pid] for pid in products_ids if pid in product_details]

    if llm is None:
        if not products:
            return "Mình chưa kết nối được LLM nên hiện chỉ hỗ trợ tìm sản phẩm. Bạn kiểm tra GITHUB_TOKEN và cài dependency LLM rồi restart ai-service nhé."
        names = ", ".join(product["name"] for product in products[:3])
        return f"Mình tìm thấy {len(products)} sản phẩm phù hợp: {names}. Bạn xem danh sách sản phẩm bên dưới nhé."

    # Build context from products
    product_context = ""
    if products:
        lines = [
            f"- {product['name']} (ID {product['id']}), {product['category']}, price {product['price']}, {product['description']}"
            for product in products
        ]
        product_context = "\n\nProducts found:\n" + "\n".join(lines)

    # Prompt for LLM
    prompt = f"""Bạn là trợ lý bán hàng thân thiện của một cửa hàng thương mại điện tử. Hãy trả lời câu hỏi của khách hàng một cách ngắn gọn, chuyên nghiệp và hữu ích.

Câu hỏi khách hàng: {message}
{product_context}

Trả lời (tiếng Việt, tối đa 150 từ):"""

    try:
        response = llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception as e:
        return f"Mình chưa tạo được câu trả lời chi tiết lúc này. Bạn thử lại sau nhé. ({str(e)[:50]})"


@app.post("/chatbot", response_model=ChatResponse)
def chatbot(request: ChatRequest):
    """Chatbot endpoint: NLP parse → retrieve → generate reply."""
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    intent, entities = parse_intent_and_entities(message)

    products_data = retrieve_products_for_chatbot(message, limit=5)
    product_ids = products_data.get("ids", [])

    reply = generate_chatbot_reply(message, product_ids, products_data.get("details", {}))

    return {
        "reply": reply,
        "products": _chatbot_products_payload(product_ids, products_data.get("details", {})),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
