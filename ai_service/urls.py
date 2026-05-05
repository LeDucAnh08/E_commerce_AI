from django.urls import path

from . import views


urlpatterns = [
    path("ai/behavior/", views.collect_behavior, name="ai-behavior"),
    path("recommend", views.recommend, name="recommend"),
    path("recommend/", views.recommend, name="recommend-slash"),
    path("ai/recommendations/", views.recommend, name="ai-recommendations"),
    path("ai/chat/", views.chat, name="ai-chat"),
]
