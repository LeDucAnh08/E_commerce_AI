from django.urls import path

from . import views


urlpatterns = [
    path("", views.shop_home, name="shop-home"),
    path("login/", views.login_page, name="login-page"),
    path("cart/ui/", views.cart_page, name="cart-page"),
    path("checkout/", views.checkout_page, name="checkout-page"),
    path("shipping/track/", views.shipping_tracking_page, name="shipping-tracking-page"),
    path("products/<int:product_id>/ui/", views.product_detail_page, name="product-detail-page"),
    path("products/", views.products_collection, name="products-collection"),
    path("products/<int:product_id>/", views.product_detail, name="product-detail"),
    path("categories/", views.categories_collection, name="categories-collection"),
]
