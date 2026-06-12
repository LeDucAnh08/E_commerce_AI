from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.FloatField()
    stock = models.IntegerField()
    image_url = models.URLField(blank=True, default="")
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Book(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="book_details",
    )
    author = models.CharField(max_length=255)
    publisher = models.CharField(max_length=255)
    isbn = models.CharField(max_length=20)

    def __str__(self):
        return f"Book: {self.product.name}"


class Electronics(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="electronics_details",
    )
    brand = models.CharField(max_length=100)
    warranty = models.IntegerField()

    def __str__(self):
        return f"Electronics: {self.product.name}"


class Fashion(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="fashion_details",
    )
    size = models.CharField(max_length=10)
    color = models.CharField(max_length=50)

    def __str__(self):
        return f"Fashion: {self.product.name}"
