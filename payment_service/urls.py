from django.urls import path

from . import views


urlpatterns = [
    path("payment/pay/", views.pay, name="payment-pay"),
    path("payment/status/<int:order_id>/", views.payment_status, name="payment-status"),
    path("payment/refund/<int:payment_id>/", views.refund, name="payment-refund"),
    path("payment/history/", views.payment_history, name="payment-history"),
]
