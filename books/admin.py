from django.contrib import admin
from .models import (
    Author, Book, Category, Customer,
    Publisher, Sale, SaleItem
)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title", "author", "category", "publisher",
        "price", "stock_quantity", "is_active"
    )
    list_filter = ("category", "publisher", "is_active")
    search_fields = ("title", "author__full_name", "isbn")


admin.site.register(Author)
admin.site.register(Category)
admin.site.register(Publisher)
admin.site.register(Customer)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "id", "seller", "customer", "sold_at", "total_amount"
    )
    list_filter = ("sold_at",)
    search_fields = ("seller__username", "customer__full_name")
    readonly_fields = (
        "seller", "customer", "sold_at", "total_amount"
    )
    inlines = [SaleItemInline]
