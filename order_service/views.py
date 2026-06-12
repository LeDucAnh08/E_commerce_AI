import json

import jwt
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from cart_service.models import Cart, CartItem
from shipping_service.models import Shipment

from .models import Order, OrderItem


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

    user_id = payload.get("sub")
    if not user_id:
        return None, _bad_request("Invalid token", status=401)

    return payload, None


def _require_customer(payload: dict):
    if payload.get("role") != "customer":
        return _bad_request("Customer required", status=403)
    return None


def _require_admin_or_staff(payload: dict):
    if payload.get("role") in {"admin", "staff"}:
        return None
    return _bad_request("Admin/staff required", status=403)


def _serialize_order(order: Order) -> dict:
    shipment = Shipment.objects.filter(order_id=order.id).order_by("-id").first()
    return {
        "id": order.id,
        "user_id": order.user_id,
        "total_price": order.total_price,
        "status": order.status,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
            }
            for item in order.items.all()
        ],
        "shipment": (
            {
                "id": shipment.id,
                "address": shipment.address,
                "shipping_method": shipment.shipping_method,
                "status": shipment.status,
            }
            if shipment
            else None
        ),
    }


def _calculate_cart_total(cart: Cart) -> float:
    items = cart.items.all()
    return float(sum(item.quantity for item in items))


def _send_payment_request(order: Order) -> dict:
    return {"status": "payment_requested", "order_id": order.id}


@csrf_exempt
def create_order_from_cart(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    payload, error = _get_authenticated_user(request)
    if error:
        return error

    auth_error = _require_customer(payload)
    if auth_error:
        return auth_error

    user_id = int(payload["sub"])
    cart = Cart.objects.filter(user_id=user_id).first()
    if not cart or not cart.items.exists():
        return _bad_request("Cart is empty")

    data, parse_error = _parse_json(request)
    if parse_error:
        return parse_error

    shipping_address = str(data.get("shipping_address", "")).strip()
    if not shipping_address:
        return _bad_request("Missing shipping_address")

    shipping_method = data.get("shipping_method", Shipment.METHOD_STANDARD)
    if shipping_method not in {choice[0] for choice in Shipment.METHOD_CHOICES}:
        return _bad_request("Invalid shipping_method")

    total_price = _calculate_cart_total(cart)

    with transaction.atomic():
        order = Order.objects.create(
            user_id=user_id,
            total_price=total_price,
            status="payment_pending",
        )

        items = [
            OrderItem(order=order, product_id=item.product_id, quantity=item.quantity)
            for item in cart.items.all()
        ]
        OrderItem.objects.bulk_create(items)

        _send_payment_request(order)
        order.status = "payment_requested"
        order.save(update_fields=["status"])

        Shipment.objects.create(
            order_id=order.id,
            address=shipping_address,
            shipping_method=shipping_method,
            status=Shipment.STATUS_PROCESSING,
        )

        CartItem.objects.filter(cart=cart).delete()

    return JsonResponse(_serialize_order(order), status=201)


@csrf_exempt
def orders_collection(request):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    payload, error = _get_authenticated_user(request)
    if error:
        return error

    role = payload.get("role")
    user_id = int(payload["sub"])

    if role in {"admin", "staff"}:
        orders = Order.objects.all().order_by("id")
    else:
        orders = Order.objects.filter(user_id=user_id).order_by("id")

    data = [_serialize_order(order) for order in orders]
    return JsonResponse(data, safe=False)


@csrf_exempt
def order_detail(request, order_id: int):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    payload, error = _get_authenticated_user(request)
    if error:
        return error

    order = Order.objects.filter(id=order_id).first()
    if not order:
        return _bad_request("Order not found", status=404)

    role = payload.get("role")
    user_id = int(payload["sub"])
    if role not in {"admin", "staff"} and order.user_id != user_id:
        return _bad_request("Forbidden", status=403)

    return JsonResponse(_serialize_order(order))


@csrf_exempt
def mark_order_paid(request, order_id: int):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    payload, error = _get_authenticated_user(request)
    if error:
        return error

    auth_error = _require_admin_or_staff(payload)
    if auth_error:
        return auth_error

    order = Order.objects.filter(id=order_id).first()
    if not order:
        return _bad_request("Order not found", status=404)

    order.status = "shipping"
    order.save(update_fields=["status"])
    return JsonResponse(_serialize_order(order))
