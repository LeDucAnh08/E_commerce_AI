from django.db import models


class Cart(models.Model):
    user_id = models.IntegerField()

    def __str__(self):
        return f"Cart {self.id} (user {self.user_id})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product_id = models.IntegerField()
    quantity = models.IntegerField()

    def __str__(self):
        return f"Item {self.product_id} x {self.quantity}"
