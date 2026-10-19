from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Author(models.Model):
    full_name = models.CharField(
        "Повне ім'я", max_length=160, unique=True
    )

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Автори"
        db_table = 'authors'


class Category(models.Model):
    name = models.CharField(
        "Назва категорії", max_length=100, unique=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категорія"
        verbose_name_plural = "Категорії"
        db_table = 'categories'


class Publisher(models.Model):
    name = models.CharField(
        "Назва видавництва", max_length=160, unique=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Видавництво"
        verbose_name_plural = "Видавництва"
        db_table = 'publishers'


class Book(models.Model):
    title = models.CharField("Назва книги", max_length=200)
    author = models.ForeignKey(
        Author, on_delete=models.PROTECT,
        verbose_name="Автор"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT,
        verbose_name="Категорія"
    )
    publisher = models.ForeignKey(
        Publisher, on_delete=models.PROTECT,
        verbose_name="Видавництво"
    )
    isbn = models.CharField(
        "ISBN", max_length=20, unique=True, blank=True
    )
    price = models.DecimalField(
        "Ціна", max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    stock_quantity = models.PositiveIntegerField(
        "Кількість на складі", default=0
    )
    is_active = models.BooleanField("Активна", default=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        db_table = 'books'


class Customer(models.Model):
    full_name = models.CharField("ПІБ покупця", max_length=180)
    phone = models.CharField("Телефон", max_length=30, blank=True)
    email = models.EmailField("Електронна пошта", blank=True)

    def __str__(self):
        return self.full_name

    class Meta:
        verbose_name = "Покупець"
        verbose_name_plural = "Покупці"
        db_table = 'customers'


class Sale(models.Model):
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales",
        verbose_name="Продавець"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Покупець"
    )
    sold_at = models.DateTimeField(
        "Дата продажу", auto_now_add=True
    )
    total_amount = models.DecimalField(
        "Загальна сума", max_digits=12,
        decimal_places=2, default=0
    )

    def __str__(self):
        return f"Продаж №{self.pk}"

    class Meta:
        verbose_name = "Продаж"
        verbose_name_plural = "Продажі"
        db_table = 'sales'


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE,
        related_name="items", verbose_name="Продаж"
    )
    book = models.ForeignKey(
        Book, on_delete=models.PROTECT,
        verbose_name="Книга"
    )
    quantity = models.PositiveIntegerField(
        "Кількість", validators=[MinValueValidator(1)]
    )
    unit_price = models.DecimalField(
        "Ціна за одиницю", max_digits=10,
        decimal_places=2
    )

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.book} × {self.quantity}"

    class Meta:
        verbose_name = "Позиція продажу"
        verbose_name_plural = "Позиції продажу"
        db_table = 'sale_items'

