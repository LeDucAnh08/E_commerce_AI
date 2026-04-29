from django.urls import path

from . import views


urlpatterns = [
    path("auth/register/", views.register, name="register"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/refresh/", views.refresh_token, name="refresh"),
    path("users/", views.users_collection, name="users-collection"),
    path("users/<int:user_id>/", views.user_detail, name="user-detail"),
]
