from django.db import models


class UserBehavior(models.Model):
    ACTION_VIEW = "view"
    ACTION_CLICK = "click"
    ACTION_ADD_TO_CART = "add_to_cart"

    ACTION_CHOICES = (
        (ACTION_VIEW, "View"),
        (ACTION_CLICK, "Click"),
        (ACTION_ADD_TO_CART, "Add to cart"),
    )

    user_id = models.IntegerField()
    product_id = models.IntegerField()
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField()

    def __str__(self):
        return f"Behavior {self.user_id}:{self.product_id}:{self.action}"
