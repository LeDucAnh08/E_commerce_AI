import json

import jwt
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Cart, CartItem


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


def _get_authenticated_customer(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, _bad_request("Missing token", status=401)

    token = auth_header.split(" ", 1)[1].strip()
    payload = _decode_token(token)
    if not payload or payload.get("type") != "access":
        return None, _bad_request("Invalid token", status=401)

    if payload.get("role") != "customer":
        return None, _bad_request("Customer required", status=403)

    user_id = payload.get("sub")
    if not user_id:
        return None, _bad_request("Invalid token", status=401)

    return int(user_id), None


def _get_cart(user_id: int) -> Cart:
    cart, _ = Cart.objects.get_or_create(user_id=user_id)
    return cart


def _serialize_cart(cart: Cart) -> dict:
    items = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "quantity": item.quantity,
            "subtotal": item.quantity,
        }
        for item in cart.items.all()
    ]
    total = sum(item["subtotal"] for item in items)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "items": items,
        "total": total,
    }


@csrf_exempt
def add_to_cart(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    user_id, auth_error = _get_authenticated_customer(request)
    if auth_error:
        return auth_error

    data, error = _parse_json(request)
    if error:
        return error

    try:
        product_id = int(data.get("product_id"))
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return _bad_request("Invalid product_id or quantity")

    if quantity <= 0:
        return _bad_request("Quantity must be positive")

    cart = _get_cart(user_id)
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product_id=product_id,
        defaults={"quantity": quantity},
    )
    if not created:
        item.quantity += quantity
        item.save()

    return JsonResponse(_serialize_cart(cart), status=201)


@csrf_exempt
def cart_detail(request):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    user_id, auth_error = _get_authenticated_customer(request)
    if auth_error:
        return auth_error

    cart = _get_cart(user_id)
    return JsonResponse(_serialize_cart(cart))


@csrf_exempt
def update_cart_item(request, item_id: int):
    if request.method != "PUT":
        return _bad_request("Method not allowed", status=405)

    user_id, auth_error = _get_authenticated_customer(request)
    if auth_error:
        return auth_error

    data, error = _parse_json(request)
    if error:
        return error

    try:
        quantity = int(data.get("quantity"))
    except (TypeError, ValueError):
        return _bad_request("Invalid quantity")

    if quantity <= 0:
        return _bad_request("Quantity must be positive")

    cart = _get_cart(user_id)
    item = CartItem.objects.filter(cart=cart, id=item_id).first()
    if not item:
        return _bad_request("Item not found", status=404)

    item.quantity = quantity
    item.save()
    return JsonResponse(_serialize_cart(cart))


@csrf_exempt
def remove_from_cart(request, item_id: int):
    if request.method != "DELETE":
        return _bad_request("Method not allowed", status=405)

    user_id, auth_error = _get_authenticated_customer(request)
    if auth_error:
        return auth_error

    cart = _get_cart(user_id)
    deleted, _ = CartItem.objects.filter(cart=cart, id=item_id).delete()
    if not deleted:
        return _bad_request("Item not found", status=404)

    return JsonResponse(_serialize_cart(cart))


@csrf_exempt
def clear_cart(request):
    if request.method != "DELETE":
        return _bad_request("Method not allowed", status=405)

    user_id, auth_error = _get_authenticated_customer(request)
    if auth_error:
        return auth_error

    cart = _get_cart(user_id)
    cart.items.all().delete()
    return JsonResponse(_serialize_cart(cart))
