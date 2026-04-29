from django.urls import path

from . import views


urlpatterns = [
    path("shipping/create/", views.create_shipment, name="shipping-create"),
    path("shipping/status/<int:order_id>/", views.shipping_status, name="shipping-status"),
    path(
        "shipping/<int:shipment_id>/status/",
        views.update_shipment_status,
        name="shipping-status-update",
    ),
    path("shipping/", views.shipments_collection, name="shipping-collection"),
]
