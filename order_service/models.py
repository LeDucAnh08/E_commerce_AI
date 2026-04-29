from django.db import models


class Order(models.Model):
    user_id = models.IntegerField()
    total_price = models.FloatField()
    status = models.CharField(max_length=50)

    def __str__(self):
        return f"Order {self.id} (user {self.user_id})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_id = models.IntegerField()
    quantity = models.IntegerField()

    def __str__(self):
        return f"OrderItem {self.product_id} x {self.quantity}"
