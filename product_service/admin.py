from django.contrib import admin

from .models import Book, Category, Electronics, Fashion, Product


admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Book)
admin.site.register(Electronics)
admin.site.register(Fashion)
