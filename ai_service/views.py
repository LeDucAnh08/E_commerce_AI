import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import UserBehavior


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
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    data, error = _parse_json(request)
    if error:
        return error

    user_id = data.get("user_id")
    query = data.get("query")

    return JsonResponse(
        {
            "user_id": user_id,
            "query": query,
            "recommendations": [],
            "note": "Stub response. Implement LSTM/Knowledge Graph/RAG here.",
        }
    )


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
