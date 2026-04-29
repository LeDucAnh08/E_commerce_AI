import json

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import Book, Category, Electronics, Fashion, Product


def _serialize_product(product: Product) -> dict:
    data = {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "stock": product.stock,
        "category": product.category.name,
        "type": None,
        "details": None,
    }

    if hasattr(product, "book_details"):
        data["type"] = "book"
        data["details"] = {
            "author": product.book_details.author,
            "publisher": product.book_details.publisher,
            "isbn": product.book_details.isbn,
        }
    elif hasattr(product, "electronics_details"):
        data["type"] = "electronics"
        data["details"] = {
            "brand": product.electronics_details.brand,
            "warranty": product.electronics_details.warranty,
        }
    elif hasattr(product, "fashion_details"):
        data["type"] = "fashion"
        data["details"] = {
            "size": product.fashion_details.size,
            "color": product.fashion_details.color,
        }

    return data


def _get_product_type(product: Product) -> str | None:
    if hasattr(product, "book_details"):
        return "book"
    if hasattr(product, "electronics_details"):
        return "electronics"
    if hasattr(product, "fashion_details"):
        return "fashion"
    return None


def _bad_request(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _parse_json(request) -> tuple[dict | None, JsonResponse | None]:
    if not request.body:
        return {}, None
    try:
        return json.loads(request.body), None
    except json.JSONDecodeError:
        return None, _bad_request("Invalid JSON")


def _require_staff(request) -> JsonResponse | None:
    if not request.user.is_authenticated or not request.user.is_staff:
        return _bad_request("Admin/staff required", status=403)
    return None


def _require_admin(request) -> JsonResponse | None:
    if not request.user.is_authenticated or not request.user.is_superuser:
        return _bad_request("Admin required", status=403)
    return None


def _apply_type_filter(queryset, product_type: str):
    if product_type == "book":
        return queryset.filter(book_details__isnull=False)
    if product_type == "electronics":
        return queryset.filter(electronics_details__isnull=False)
    if product_type == "fashion":
        return queryset.filter(fashion_details__isnull=False)
    return None


@csrf_exempt
def products_collection(request):
    if request.method == "GET":
        products = Product.objects.select_related("category").all()

        category_name = request.GET.get("category")
        if category_name:
            products = products.filter(category__name__iexact=category_name)

        search = request.GET.get("q")
        if search:
            products = products.filter(name__icontains=search)

        min_price = request.GET.get("min_price")
        if min_price:
            try:
                min_price_value = float(min_price)
            except ValueError:
                return _bad_request("Invalid min_price")
            products = products.filter(price__gte=min_price_value)

        max_price = request.GET.get("max_price")
        if max_price:
            try:
                max_price_value = float(max_price)
            except ValueError:
                return _bad_request("Invalid max_price")
            products = products.filter(price__lte=max_price_value)

        product_type = request.GET.get("type")
        if product_type:
            filtered = _apply_type_filter(products, product_type)
            if filtered is None:
                return _bad_request("Invalid product type")
            products = filtered

        payload = [_serialize_product(product) for product in products]
        return JsonResponse(payload, safe=False)

    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    auth_error = _require_staff(request)
    if auth_error:
        return auth_error

    data, error = _parse_json(request)
    if error:
        return error

    name = data.get("name")
    category_name = data.get("category")
    product_type = data.get("type")
    details = data.get("details") or {}

    try:
        price = float(data.get("price"))
        stock = int(data.get("stock"))
    except (TypeError, ValueError):
        return _bad_request("Invalid price or stock")

    if not name or not category_name or not product_type:
        return _bad_request("Missing required fields")

    if product_type == "book":
        required_keys = ("author", "publisher", "isbn")
    elif product_type == "electronics":
        required_keys = ("brand", "warranty")
    elif product_type == "fashion":
        required_keys = ("size", "color")
    else:
        return _bad_request("Invalid product type")

    if not all(key in details for key in required_keys):
        return _bad_request("Missing product details")

    with transaction.atomic():
        category, _ = Category.objects.get_or_create(name=category_name)
        product = Product.objects.create(
            name=name,
            price=price,
            stock=stock,
            category=category,
        )

        if product_type == "book":
            Book.objects.create(
                product=product,
                author=details["author"],
                publisher=details["publisher"],
                isbn=details["isbn"],
            )
        elif product_type == "electronics":
            try:
                warranty_value = int(details["warranty"])
            except (TypeError, ValueError):
                return _bad_request("Invalid warranty")
            Electronics.objects.create(
                product=product,
                brand=details["brand"],
                warranty=warranty_value,
            )
        else:
            Fashion.objects.create(
                product=product,
                size=details["size"],
                color=details["color"],
            )

    return JsonResponse(_serialize_product(product), status=201)


@csrf_exempt
def product_detail(request, product_id: int):
    if request.method == "GET":
        product = get_object_or_404(
            Product.objects.select_related("category"),
            id=product_id,
        )
        return JsonResponse(_serialize_product(product))

    if request.method == "PUT":
        auth_error = _require_staff(request)
        if auth_error:
            return auth_error

        data, error = _parse_json(request)
        if error:
            return error

        product = get_object_or_404(
            Product.objects.select_related("category"),
            id=product_id,
        )

        if "name" in data:
            product.name = data["name"]

        if "price" in data:
            try:
                product.price = float(data["price"])
            except (TypeError, ValueError):
                return _bad_request("Invalid price")

        if "stock" in data:
            try:
                product.stock = int(data["stock"])
            except (TypeError, ValueError):
                return _bad_request("Invalid stock")

        if "category" in data:
            category_name = data["category"]
            if not category_name:
                return _bad_request("Invalid category")
            category, _ = Category.objects.get_or_create(name=category_name)
            product.category = category

        existing_type = _get_product_type(product)
        requested_type = data.get("type")
        if requested_type and requested_type != existing_type:
            return _bad_request("Product type mismatch")

        details = data.get("details") or {}

        with transaction.atomic():
            product.save()

            if existing_type == "book":
                book = product.book_details
                if "author" in details:
                    book.author = details["author"]
                if "publisher" in details:
                    book.publisher = details["publisher"]
                if "isbn" in details:
                    book.isbn = details["isbn"]
                book.save()
            elif existing_type == "electronics":
                electronics = product.electronics_details
                if "brand" in details:
                    electronics.brand = details["brand"]
                if "warranty" in details:
                    try:
                        electronics.warranty = int(details["warranty"])
                    except (TypeError, ValueError):
                        return _bad_request("Invalid warranty")
                electronics.save()
            elif existing_type == "fashion":
                fashion = product.fashion_details
                if "size" in details:
                    fashion.size = details["size"]
                if "color" in details:
                    fashion.color = details["color"]
                fashion.save()

        return JsonResponse(_serialize_product(product))

    if request.method == "DELETE":
        auth_error = _require_admin(request)
        if auth_error:
            return auth_error

        product = get_object_or_404(Product, id=product_id)
        product.delete()
        return HttpResponse(status=204)

    return _bad_request("Method not allowed", status=405)


@csrf_exempt
def categories_collection(request):
    if request.method == "GET":
        categories = Category.objects.all().order_by("name")
        payload = [{"id": category.id, "name": category.name} for category in categories]
        return JsonResponse(payload, safe=False)

    if request.method != "POST":
        return _bad_request("Method not allowed", status=405)

    auth_error = _require_admin(request)
    if auth_error:
        return auth_error

    data, error = _parse_json(request)
    if error:
        return error

    name = data.get("name")
    if not name:
        return _bad_request("Missing category name")

    category, created = Category.objects.get_or_create(name=name)
    status = 201 if created else 200
    return JsonResponse({"id": category.id, "name": category.name}, status=status)
