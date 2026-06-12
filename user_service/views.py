import json
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.contrib.auth import authenticate
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import User


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _parse_json(request):
    if not request.body:
        return {}, None
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, _bad_request("Invalid JSON")


ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=7)


def _encode_token(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def _decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _build_tokens(user: User) -> dict:
    now = datetime.now(tz=timezone.utc)
    access_payload = {
        "sub": str(user.id),
        "role": user.role,
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    refresh_payload = {
        "sub": str(user.id),
        "type": "refresh",
        "iat": now,
        "exp": now + REFRESH_TOKEN_TTL,
    }
    return {
        "access": _encode_token(access_payload),
        "refresh": _encode_token(refresh_payload),
    }


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

    try:
        return User.objects.get(id=user_id), None
    except User.DoesNotExist:
        return None, _bad_request("User not found", status=404)


def _require_admin(user: User) -> JsonResponse | None:
    if not user.is_superuser:
        return _bad_request("Admin required", status=403)
    return None


def _require_admin_or_self(user: User, target_user_id: int) -> JsonResponse | None:
    if user.is_superuser or user.id == target_user_id:
        return None
    return _bad_request("Admin or owner required", status=403)


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


@csrf_exempt
def register(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    data, error = _parse_json(request)
    if error:
        return error

    username = data.get("username")
    password = data.get("password")
    email = data.get("email", "")

    if not username or not password:
        return _bad_request("Missing username or password")

    if User.objects.filter(username=username).exists():
        return _bad_request("Username already exists")

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role=User.ROLE_CUSTOMER,
    )
    tokens = _build_tokens(user)

    return JsonResponse({"user": _serialize_user(user), **tokens}, status=201)


@csrf_exempt
def login_view(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    data, error = _parse_json(request)
    if error:
        return error

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return _bad_request("Missing username or password")

    user = authenticate(request, username=username, password=password)
    if not user:
        return _bad_request("Invalid credentials", status=401)

    tokens = _build_tokens(user)
    return JsonResponse({"user": _serialize_user(user), **tokens})


@csrf_exempt
def refresh_token(request):
    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    data, error = _parse_json(request)
    if error:
        return error

    refresh = data.get("refresh")
    if not refresh:
        return _bad_request("Missing refresh token")

    payload = _decode_token(refresh)
    if not payload or payload.get("type") != "refresh":
        return _bad_request("Invalid refresh token", status=401)

    user_id = payload.get("sub")
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return _bad_request("User not found", status=404)

    tokens = _build_tokens(user)
    return JsonResponse(tokens)


@csrf_exempt
def users_collection(request):
    if request.method != "GET":
        return _bad_request("Method not allowed", status=405)

    user, error = _get_authenticated_user(request)
    if error:
        return error

    auth_error = _require_admin(user)
    if auth_error:
        return auth_error

    users = User.objects.all().order_by("id")
    payload = [_serialize_user(user) for user in users]
    return JsonResponse(payload, safe=False)


@csrf_exempt
def user_detail(request, user_id: int):
    user, error = _get_authenticated_user(request)
    if error:
        return error

    auth_error = _require_admin_or_self(user, user_id)
    if auth_error:
        return auth_error

    target = User.objects.filter(id=user_id).first()
    if not target:
        return _bad_request("User not found", status=404)

    if request.method == "GET":
        return JsonResponse(_serialize_user(target))

    if request.method == "PUT":
        data, parse_error = _parse_json(request)
        if parse_error:
            return parse_error

        if "username" in data:
            target.username = data["username"]
        if "email" in data:
            target.email = data["email"]
        if "password" in data:
            target.set_password(data["password"])

        if "role" in data:
            if not user.is_superuser:
                return _bad_request("Admin required", status=403)
            target.role = data["role"]

        target.save()
        return JsonResponse(_serialize_user(target))

    if request.method == "DELETE":
        auth_error = _require_admin(user)
        if auth_error:
            return auth_error

        target.delete()
        return HttpResponse(status=204)

    return _bad_request("Method not allowed", status=405)
