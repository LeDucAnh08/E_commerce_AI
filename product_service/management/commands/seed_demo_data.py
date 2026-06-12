from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from ai_service.lstm.models import UserBehavior
from cart_service.models import Cart, CartItem
from order_service.models import Order, OrderItem
from payment_service.models import Payment
from product_service.models import Book, Category, Electronics, Fashion, Product
from shipping_service.models import Shipment


class Command(BaseCommand):
    help = "Seed demo data into PostgreSQL product DB and MySQL service DB."

    def handle(self, *args, **options):
        products = self.seed_products()
        users = self.seed_users()
        self.seed_carts(users, products)
        self.seed_orders(users, products)
        self.seed_behavior(users, products)

        self.stdout.write(self.style.SUCCESS("Seed data completed."))
        self.stdout.write(f"Products: {len(products)} in PostgreSQL alias 'product'")
        self.stdout.write(f"Users: {len(users)} in MySQL alias 'default'")

    def seed_products(self):
        category_names = ["Books", "Electronics", "Fashion"]
        categories = {
            name: Category.objects.using("product").update_or_create(
                name=name,
                defaults={},
            )[0]
            for name in category_names
        }

        product_specs = [
            {
                "name": "Clean Architecture",
                "price": 42.5,
                "stock": 30,
                "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=900&q=80",
                "category": "Books",
                "type": "book",
                "details": {
                    "author": "Robert C. Martin",
                    "publisher": "Prentice Hall",
                    "isbn": "9780134494166",
                },
            },
            {
                "name": "Django for APIs",
                "price": 34.0,
                "stock": 45,
                "image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=900&q=80",
                "category": "Books",
                "type": "book",
                "details": {
                    "author": "William S. Vincent",
                    "publisher": "WelcomeToCode",
                    "isbn": "9781735467221",
                },
            },
            {
                "name": "NovaBook Pro 14",
                "price": 1299.0,
                "stock": 12,
                "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=80",
                "category": "Electronics",
                "type": "electronics",
                "details": {
                    "brand": "NovaTech",
                    "warranty": 24,
                },
            },
            {
                "name": "AeroSound Wireless Headphones",
                "price": 159.0,
                "stock": 60,
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80",
                "category": "Electronics",
                "type": "electronics",
                "details": {
                    "brand": "AeroSound",
                    "warranty": 12,
                },
            },
            {
                "name": "Everyday Cotton Hoodie",
                "price": 49.9,
                "stock": 80,
                "image_url": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=900&q=80",
                "category": "Fashion",
                "type": "fashion",
                "details": {
                    "size": "M",
                    "color": "Navy",
                },
            },
            {
                "name": "Urban Runner Sneakers",
                "price": 89.0,
                "stock": 40,
                "image_url": "https://images.unsplash.com/photo-1549298916-b41d501d3772?auto=format&fit=crop&w=900&q=80",
                "category": "Fashion",
                "type": "fashion",
                "details": {
                    "size": "42",
                    "color": "White",
                },
            },
        ]

        products = {}
        for spec in product_specs:
            product, _ = Product.objects.using("product").update_or_create(
                name=spec["name"],
                defaults={
                    "price": spec["price"],
                    "stock": spec["stock"],
                    "image_url": spec.get("image_url", ""),
                    "category": categories[spec["category"]],
                },
            )
            details = spec["details"]
            if spec["type"] == "book":
                Book.objects.using("product").update_or_create(
                    product=product,
                    defaults=details,
                )
            elif spec["type"] == "electronics":
                Electronics.objects.using("product").update_or_create(
                    product=product,
                    defaults=details,
                )
            elif spec["type"] == "fashion":
                Fashion.objects.using("product").update_or_create(
                    product=product,
                    defaults=details,
                )
            products[spec["name"]] = product

        return products

    def seed_users(self):
        User = get_user_model()
        user_specs = [
            {
                "username": "admin",
                "email": "admin@example.com",
                "password": "admin123",
                "role": User.ROLE_ADMIN,
            },
            {
                "username": "staff",
                "email": "staff@example.com",
                "password": "staff123",
                "role": User.ROLE_STAFF,
            },
            {
                "username": "alice",
                "email": "alice@example.com",
                "password": "alice123",
                "role": User.ROLE_CUSTOMER,
            },
            {
                "username": "bob",
                "email": "bob@example.com",
                "password": "bob123",
                "role": User.ROLE_CUSTOMER,
            },
        ]

        users = {}
        for spec in user_specs:
            user, _ = User.objects.db_manager("default").update_or_create(
                username=spec["username"],
                defaults={
                    "email": spec["email"],
                    "role": spec["role"],
                },
            )
            user.set_password(spec["password"])
            user.save(using="default")
            users[spec["username"]] = user

        return users

    def seed_carts(self, users, products):
        product_items = [
            products["NovaBook Pro 14"],
            products["Everyday Cotton Hoodie"],
        ]
        user = users["alice"]

        cart, _ = Cart.objects.using("default").get_or_create(user_id=user.id)
        CartItem.objects.using("default").filter(cart=cart).delete()
        for product in product_items:
            CartItem.objects.using("default").create(
                cart=cart,
                product_id=product.id,
                quantity=1,
            )

        bob_cart, _ = Cart.objects.using("default").get_or_create(user_id=users["bob"].id)
        CartItem.objects.using("default").filter(cart=bob_cart).delete()
        CartItem.objects.using("default").create(
            cart=bob_cart,
            product_id=products["Clean Architecture"].id,
            quantity=2,
        )

    def seed_orders(self, users, products):
        sample_user_ids = [users["alice"].id, users["bob"].id]
        existing_order_ids = list(
            Order.objects.using("default")
            .filter(user_id__in=sample_user_ids)
            .values_list("id", flat=True)
        )
        Payment.objects.using("default").filter(order_id__in=existing_order_ids).delete()
        Shipment.objects.using("default").filter(order_id__in=existing_order_ids).delete()
        Order.objects.using("default").filter(id__in=existing_order_ids).delete()

        alice_order = Order.objects.using("default").create(
            user_id=users["alice"].id,
            total_price=products["NovaBook Pro 14"].price + products["Everyday Cotton Hoodie"].price,
            status="shipping",
        )
        OrderItem.objects.using("default").bulk_create(
            [
                OrderItem(
                    order=alice_order,
                    product_id=products["NovaBook Pro 14"].id,
                    quantity=1,
                ),
                OrderItem(
                    order=alice_order,
                    product_id=products["Everyday Cotton Hoodie"].id,
                    quantity=1,
                ),
            ]
        )
        Payment.objects.using("default").create(
            order_id=alice_order.id,
            amount=alice_order.total_price,
            status=Payment.STATUS_SUCCESS,
        )
        Shipment.objects.using("default").create(
            order_id=alice_order.id,
            address="123 Demo Street, District 1, Ho Chi Minh City",
            status=Shipment.STATUS_IN_TRANSIT,
        )

        bob_order = Order.objects.using("default").create(
            user_id=users["bob"].id,
            total_price=products["Clean Architecture"].price * 2,
            status="pending",
        )
        OrderItem.objects.using("default").create(
            order=bob_order,
            product_id=products["Clean Architecture"].id,
            quantity=2,
        )
        Payment.objects.using("default").create(
            order_id=bob_order.id,
            amount=bob_order.total_price,
            status=Payment.STATUS_PENDING,
        )

    def seed_behavior(self, users, products):
        sample_user_ids = [users["alice"].id, users["bob"].id]
        UserBehavior.objects.using("default").filter(user_id__in=sample_user_ids).delete()

        now = timezone.now()
        behavior_specs = [
            (users["alice"].id, products["NovaBook Pro 14"].id, UserBehavior.ACTION_VIEW),
            (users["alice"].id, products["NovaBook Pro 14"].id, UserBehavior.ACTION_ADD_TO_CART),
            (users["alice"].id, products["AeroSound Wireless Headphones"].id, UserBehavior.ACTION_CLICK),
            (users["bob"].id, products["Clean Architecture"].id, UserBehavior.ACTION_VIEW),
            (users["bob"].id, products["Django for APIs"].id, UserBehavior.ACTION_CLICK),
            (users["bob"].id, products["Urban Runner Sneakers"].id, UserBehavior.ACTION_VIEW),
        ]
        UserBehavior.objects.using("default").bulk_create(
            [
                UserBehavior(
                    user_id=user_id,
                    product_id=product_id,
                    action=action,
                    timestamp=now,
                )
                for user_id, product_id, action in behavior_specs
            ]
        )
