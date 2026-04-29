from django.urls import path

from . import views


urlpatterns = [
    path("cart/", views.cart_detail, name="cart-detail"),
    path("cart/add/", views.add_to_cart, name="cart-add"),
    path("cart/items/<int:item_id>/", views.update_cart_item, name="cart-item-update"),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="cart-remove"),
    path("cart/clear/", views.clear_cart, name="cart-clear"),
]
