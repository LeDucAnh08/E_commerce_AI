from django.db import models


class Shipment(models.Model):
    METHOD_STANDARD = "standard"
    METHOD_EXPRESS = "express"
    METHOD_SAME_DAY = "same_day"

    METHOD_CHOICES = (
        (METHOD_STANDARD, "Standard"),
        (METHOD_EXPRESS, "Express"),
        (METHOD_SAME_DAY, "Same day"),
    )

    STATUS_PROCESSING = "processing"
    STATUS_SHIPPED = "shipped"
    STATUS_IN_TRANSIT = "in_transit"
    STATUS_DELIVERED = "delivered"
    STATUS_RETURNED = "returned"

    STATUS_CHOICES = (
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_IN_TRANSIT, "In transit"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_RETURNED, "Returned"),
    )

    order_id = models.IntegerField()
    address = models.TextField()
    shipping_method = models.CharField(
        max_length=50,
        choices=METHOD_CHOICES,
        default=METHOD_STANDARD,
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_PROCESSING)

    def __str__(self):
        return f"Shipment {self.id} (order {self.order_id})"
