import json

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Shipment


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _parse_json(request):
    if not request.body:
        return {}, None
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, _bad_request("Invalid JSON")


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _get_authenticated_user(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, _bad_request("Missing token", status=401)

    token = auth_header.split(" ", 1)[1].strip()
    payload = _decode_token(token)
    if not payload or payload.get("type") != "access":
        return None, _bad_request("Invalid token", status=401)

    return payload, None


def _require_staff_or_admin(payload: dict):
    if payload.get("role") in {"staff", "admin"}:
        return None
    return _bad_request("Staff/admin required", status=403)


def _serialize_shipment(shipment: Shipment) -> dict:
    return {
        "id": shipment.id,
        "order_id": shipment.order_id,
        "address": shipment.address,
        "shipping_method": shipment.shipping_method,
        "status": shipment.status,
    }


@csrf_exempt
def create_shipment(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    payload, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    role_error = _require_staff_or_admin(payload)
    if role_error:
        return role_error

    data, error = _parse_json(request)
    if error:
        return error

    try:
        order_id = int(data.get("order_id"))
    except (TypeError, ValueError):
        return _bad_request("Invalid order_id")

    address = data.get("address")
    if not address:
        return _bad_request("Missing address")

    shipping_method = data.get("shipping_method", Shipment.METHOD_STANDARD)
    if shipping_method not in {choice[0] for choice in Shipment.METHOD_CHOICES}:
        return _bad_request("Invalid shipping_method")

    shipment = Shipment.objects.create(
        order_id=order_id,
        address=address,
        shipping_method=shipping_method,
        status=Shipment.STATUS_PROCESSING,
    )

    return JsonResponse(_serialize_shipment(shipment), status=201)


@csrf_exempt
def shipping_status(request, order_id: int):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    shipment = Shipment.objects.filter(order_id=order_id).order_by("-id").first()
    if not shipment:
        return _bad_request("Shipment not found", status=404)

    return JsonResponse(_serialize_shipment(shipment))


@csrf_exempt
def update_shipment_status(request, shipment_id: int):
    if request.method != "PUT":
        return _bad_request("Method not allowed", status=405)

    payload, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    role_error = _require_staff_or_admin(payload)
    if role_error:
        return role_error

    data, error = _parse_json(request)
    if error:
        return error

    status = data.get("status")
    allowed = {choice[0] for choice in Shipment.STATUS_CHOICES}
    if status not in allowed:
        return _bad_request("Invalid status")

    shipment = Shipment.objects.filter(id=shipment_id).first()
    if not shipment:
        return _bad_request("Shipment not found", status=404)

    shipment.status = status
    shipment.save(update_fields=["status"])
    return JsonResponse(_serialize_shipment(shipment))


@csrf_exempt
def shipments_collection(request):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    payload, auth_error = _get_authenticated_user(request)
    if auth_error:
        return auth_error

    role_error = _require_staff_or_admin(payload)
    if role_error:
        return role_error

    shipments = Shipment.objects.all().order_by("-id")
    data = [_serialize_shipment(shipment) for shipment in shipments]
    return JsonResponse(data, safe=False)
