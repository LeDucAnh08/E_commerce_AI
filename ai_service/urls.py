from django.urls import path

from . import views


urlpatterns = [
    path("ai/behavior/", views.collect_behavior, name="ai-behavior"),
    path("ai/search-products/", views.search_products, name="ai-search-products"),
    path(
        "ai/frequently-bought-together/",
        views.frequently_bought_together,
        name="ai-frequently-bought-together",
    ),
    path(
        "ai/similar-products/<int:product_id>/",
        views.similar_products,
        name="ai-similar-products",
    ),
    path("recommend", views.recommend, name="recommend"),
    path("recommend/", views.recommend, name="recommend-slash"),
    path("ai/recommendations/", views.recommend, name="ai-recommendations"),
    path("ai/chat/", views.chat, name="ai-chat"),
]
