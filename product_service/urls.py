from django.urls import path

from . import views


urlpatterns = [
    path("products/", views.products_collection, name="products-collection"),
    path("products/<int:product_id>/", views.product_detail, name="product-detail"),
    path("categories/", views.categories_collection, name="categories-collection"),
]
