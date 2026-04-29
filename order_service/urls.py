from django.urls import path

from . import views


urlpatterns = [
    path("orders/from-cart/", views.create_order_from_cart, name="orders-from-cart"),
    path("orders/", views.orders_collection, name="orders-collection"),
    path("orders/<int:order_id>/", views.order_detail, name="order-detail"),
    path("orders/<int:order_id>/mark-paid/", views.mark_order_paid, name="order-mark-paid"),
]
