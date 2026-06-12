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
    help = "Seed extra catalog, users, orders, carts, and behavior data."

    def handle(self, *args, **options):
        products = self.seed_products()
        users = self.seed_users()
        self.seed_carts(users, products)
        self.seed_orders(users, products)
        self.seed_behavior(users, products)

        self.stdout.write(self.style.SUCCESS("Extra seed data completed."))
        self.stdout.write(f"Extra products available: {len(products)}")
        self.stdout.write(f"Extra users available: {len(users)}")
        self.stdout.write("Restart ai-service after seeding so chatbot reloads catalog/index.")

    def seed_products(self):
        category_names = ["Books", "Electronics", "Fashion"]
        categories = {
            name: Category.objects.using("product").update_or_create(name=name)[0]
            for name in category_names
        }

        product_specs = [
            {
                "name": "Python Crash Course",
                "price": 39.9,
                "stock": 55,
                "image_url": "https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=900&q=80",
                "category": "Books",
                "type": "book",
                "details": {
                    "author": "Eric Matthes",
                    "publisher": "No Starch Press",
                    "isbn": "9781718502703",
                },
            },
            {
                "name": "Designing Data Intensive Applications",
                "price": 54.0,
                "stock": 22,
                "image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=900&q=80",
                "category": "Books",
                "type": "book",
                "details": {
                    "author": "Martin Kleppmann",
                    "publisher": "OReilly Media",
                    "isbn": "9781449373320",
                },
            },
            {
                "name": "Effective Python",
                "price": 45.0,
                "stock": 34,
                "image_url": "https://images.unsplash.com/photo-1541963463532-d68292c34b19?auto=format&fit=crop&w=900&q=80",
                "category": "Books",
                "type": "book",
                "details": {
                    "author": "Brett Slatkin",
                    "publisher": "Addison-Wesley",
                    "isbn": "9780134853987",
                },
            },
            {
                "name": "React in Action",
                "price": 38.5,
                "stock": 28,
                "image_url": "https://images.unsplash.com/photo-1495446815901-a7297e633e8d?auto=format&fit=crop&w=900&q=80",
                "category": "Books",
                "type": "book",
                "details": {
                    "author": "Mark Tielens Thomas",
                    "publisher": "Manning",
                    "isbn": "9781617293856",
                },
            },
            {
                "name": "ThinkPad X1 Carbon",
                "price": 1499.0,
                "stock": 10,
                "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=80",
                "category": "Electronics",
                "type": "electronics",
                "details": {
                    "brand": "Lenovo",
                    "warranty": 36,
                },
            },
            {
                "name": "Galaxy Tab S9",
                "price": 799.0,
                "stock": 18,
                "image_url": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=900&q=80",
                "category": "Electronics",
                "type": "electronics",
                "details": {
                    "brand": "Samsung",
                    "warranty": 24,
                },
            },
            {
                "name": "Magic Keyboard Pro",
                "price": 129.0,
                "stock": 42,
                "image_url": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=80",
                "category": "Electronics",
                "type": "electronics",
                "details": {
                    "brand": "Apple",
                    "warranty": 12,
                },
            },
            {
                "name": "Dell UltraSharp Monitor 27",
                "price": 399.0,
                "stock": 16,
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=80",
                "category": "Electronics",
                "type": "electronics",
                "details": {
                    "brand": "Dell",
                    "warranty": 36,
                },
            },
            {
                "name": "Sony Noise Canceling Earbuds",
                "price": 199.0,
                "stock": 31,
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80",
                "category": "Electronics",
                "type": "electronics",
                "details": {
                    "brand": "Sony",
                    "warranty": 18,
                },
            },
            {
                "name": "Classic Oxford Shirt",
                "price": 59.0,
                "stock": 70,
                "image_url": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=80",
                "category": "Fashion",
                "type": "fashion",
                "details": {
                    "size": "L",
                    "color": "White",
                },
            },
            {
                "name": "Slim Fit Chinos",
                "price": 69.0,
                "stock": 64,
                "image_url": "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=900&q=80",
                "category": "Fashion",
                "type": "fashion",
                "details": {
                    "size": "32",
                    "color": "Khaki",
                },
            },
            {
                "name": "Waterproof Travel Jacket",
                "price": 119.0,
                "stock": 24,
                "image_url": "https://images.unsplash.com/photo-1543076447-215ad9ba6923?auto=format&fit=crop&w=900&q=80",
                "category": "Fashion",
                "type": "fashion",
                "details": {
                    "size": "M",
                    "color": "Black",
                },
            },
            {
                "name": "Minimal Leather Wallet",
                "price": 35.0,
                "stock": 95,
                "image_url": "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=80",
                "category": "Fashion",
                "type": "fashion",
                "details": {
                    "size": "One",
                    "color": "Brown",
                },
            },
            {
                "name": "Performance Running Tee",
                "price": 29.0,
                "stock": 88,
                "image_url": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=80",
                "category": "Fashion",
                "type": "fashion",
                "details": {
                    "size": "M",
                    "color": "Blue",
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
                "username": "charlie",
                "email": "charlie@example.com",
                "password": "charlie123",
                "role": User.ROLE_CUSTOMER,
            },
            {
                "username": "diana",
                "email": "diana@example.com",
                "password": "diana123",
                "role": User.ROLE_CUSTOMER,
            },
            {
                "username": "minh",
                "email": "minh@example.com",
                "password": "minh123",
                "role": User.ROLE_CUSTOMER,
            },
            {
                "username": "sara",
                "email": "sara@example.com",
                "password": "sara123",
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
        cart_specs = {
            "charlie": [
                ("ThinkPad X1 Carbon", 1),
                ("Magic Keyboard Pro", 1),
            ],
            "diana": [
                ("Classic Oxford Shirt", 2),
                ("Minimal Leather Wallet", 1),
            ],
            "minh": [
                ("Python Crash Course", 1),
                ("Effective Python", 1),
            ],
            "sara": [
                ("Sony Noise Canceling Earbuds", 1),
                ("Performance Running Tee", 2),
            ],
        }

        for username, items in cart_specs.items():
            cart, _ = Cart.objects.using("default").get_or_create(user_id=users[username].id)
            CartItem.objects.using("default").filter(cart=cart).delete()
            for product_name, quantity in items:
                CartItem.objects.using("default").create(
                    cart=cart,
                    product_id=products[product_name].id,
                    quantity=quantity,
                )

    def seed_orders(self, users, products):
        sample_user_ids = [user.id for user in users.values()]
        existing_order_ids = list(
            Order.objects.using("default")
            .filter(user_id__in=sample_user_ids)
            .values_list("id", flat=True)
        )
        Payment.objects.using("default").filter(order_id__in=existing_order_ids).delete()
        Shipment.objects.using("default").filter(order_id__in=existing_order_ids).delete()
        Order.objects.using("default").filter(id__in=existing_order_ids).delete()

        order_specs = [
            {
                "username": "charlie",
                "status": "delivered",
                "payment": Payment.STATUS_SUCCESS,
                "shipment": Shipment.STATUS_DELIVERED,
                "address": "21 Nguyen Hue, District 1, Ho Chi Minh City",
                "items": [("ThinkPad X1 Carbon", 1), ("Dell UltraSharp Monitor 27", 1)],
            },
            {
                "username": "diana",
                "status": "shipping",
                "payment": Payment.STATUS_SUCCESS,
                "shipment": Shipment.STATUS_IN_TRANSIT,
                "address": "88 Le Loi, District 3, Ho Chi Minh City",
                "items": [("Classic Oxford Shirt", 2), ("Slim Fit Chinos", 1)],
            },
            {
                "username": "minh",
                "status": "pending",
                "payment": Payment.STATUS_PENDING,
                "shipment": Shipment.STATUS_PROCESSING,
                "address": "12 Tran Hung Dao, Hanoi",
                "items": [("Python Crash Course", 1), ("Designing Data Intensive Applications", 1)],
            },
            {
                "username": "sara",
                "status": "shipping",
                "payment": Payment.STATUS_SUCCESS,
                "shipment": Shipment.STATUS_SHIPPED,
                "address": "5 Vo Van Kiet, Da Nang",
                "items": [("Sony Noise Canceling Earbuds", 1), ("Waterproof Travel Jacket", 1)],
            },
        ]

        for spec in order_specs:
            total_price = sum(products[name].price * quantity for name, quantity in spec["items"])
            order = Order.objects.using("default").create(
                user_id=users[spec["username"]].id,
                total_price=total_price,
                status=spec["status"],
            )
            OrderItem.objects.using("default").bulk_create(
                [
                    OrderItem(
                        order=order,
                        product_id=products[name].id,
                        quantity=quantity,
                    )
                    for name, quantity in spec["items"]
                ]
            )
            Payment.objects.using("default").create(
                order_id=order.id,
                amount=total_price,
                status=spec["payment"],
            )
            Shipment.objects.using("default").create(
                order_id=order.id,
                address=spec["address"],
                status=spec["shipment"],
            )

    def seed_behavior(self, users, products):
        sample_user_ids = [user.id for user in users.values()]
        UserBehavior.objects.using("default").filter(user_id__in=sample_user_ids).delete()

        now = timezone.now()
        behavior_specs = [
            ("charlie", "ThinkPad X1 Carbon", UserBehavior.ACTION_VIEW),
            ("charlie", "ThinkPad X1 Carbon", UserBehavior.ACTION_ADD_TO_CART),
            ("charlie", "Dell UltraSharp Monitor 27", UserBehavior.ACTION_CLICK),
            ("charlie", "Magic Keyboard Pro", UserBehavior.ACTION_VIEW),
            ("diana", "Classic Oxford Shirt", UserBehavior.ACTION_VIEW),
            ("diana", "Slim Fit Chinos", UserBehavior.ACTION_ADD_TO_CART),
            ("diana", "Minimal Leather Wallet", UserBehavior.ACTION_CLICK),
            ("diana", "Waterproof Travel Jacket", UserBehavior.ACTION_VIEW),
            ("minh", "Python Crash Course", UserBehavior.ACTION_VIEW),
            ("minh", "Effective Python", UserBehavior.ACTION_CLICK),
            ("minh", "Designing Data Intensive Applications", UserBehavior.ACTION_ADD_TO_CART),
            ("minh", "React in Action", UserBehavior.ACTION_VIEW),
            ("sara", "Sony Noise Canceling Earbuds", UserBehavior.ACTION_VIEW),
            ("sara", "Sony Noise Canceling Earbuds", UserBehavior.ACTION_ADD_TO_CART),
            ("sara", "Performance Running Tee", UserBehavior.ACTION_CLICK),
            ("sara", "Galaxy Tab S9", UserBehavior.ACTION_VIEW),
        ]

        UserBehavior.objects.using("default").bulk_create(
            [
                UserBehavior(
                    user_id=users[username].id,
                    product_id=products[product_name].id,
                    action=action,
                    timestamp=now,
                )
                for username, product_name, action in behavior_specs
            ]
        )
