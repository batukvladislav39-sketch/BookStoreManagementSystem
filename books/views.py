from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from .forms import SellerRegistrationForm, BookForm, SaleForm, BookSearchForm
from .models import Book, Customer, Sale, SaleItem
from django.views.generic import ListView, TemplateView, CreateView, UpdateView, DetailView, View
from django.urls import reverse_lazy
from django.db.models import Q
from decimal import Decimal
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F, DecimalField
from django.core.mail import send_mail

def sale_complete_message(mail, full_name, book_name, unit_price, quantity, total_amount):
    send_mail(
        subject=f'Вітаємо {full_name}! 🎉 (BookAbyss)',
        message=f'''
Ви придбали книгу {book_name}.
Кількість книг: {quantity}.
Ціна за шт. {unit_price}, загальна вартість: {total_amount}.
''',
        from_email=None,
        recipient_list=[ mail ],
        fail_silently=False,
    )

def calc_percents(part, whole):
    return min(100, round(float(part) / float(whole) * 100)) if whole else 0

def top_books(items, limit=5):
    rows = list(
        items.values("book_id", title=F("book__title"), author=F("book__author__full_name"))
             .annotate(
                 total_qty=Sum("quantity"),
                 revenue=Sum(
                     F("quantity") * F("unit_price"),
                     output_field=DecimalField(max_digits=12, decimal_places=2),
                 ),
             )
             .order_by("-total_qty", "-revenue", "title")[:limit]
    )
    top_qty = rows[0]["total_qty"] if rows else 0
    for row in rows:
        row["percent"] = calc_percents(row["total_qty"], top_qty)
    return rows

def is_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.is_staff
    )

class AdminRequireMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)


class HomeView(TemplateView):
    template_name = 'books/home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)


class SellerRegisterView(CreateView):
    form_class = SellerRegistrationForm
    template_name = 'books/register.html'
    success_url = reverse_lazy('dashboard')

    def dispatch(self, req, *args, **kwargs):
        if req.user.is_authenticated:
            return redirect('dashboard')

        return super().dispatch(req, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)

        login(self.request, self.object)
        messages.success(
            self.request,
            "Обліковий запис створено."
        )

        return response


class SystemLoginView(LoginView):
    template_name = "books/login.html"
    redirect_authenticated_user = True
    next_page = "dashboard"


class DashboardTemplateView(LoginRequiredMixin, TemplateView):
    template_name = 'books/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        is_administrator = is_admin(user)

        active_books = Book.objects.filter(is_active=True)
        book_count = active_books.count()
        total_book_count = Book.objects.count()
        low_stock_count = active_books.filter(stock_quantity__lte=5).count()

        sales = (
            Sale.objects
                .select_related('seller', 'customer')
                .prefetch_related('items__book')
        )
        if not is_administrator:
            sales = sales.filter(seller=user)

        sales_count = sales.count()
        sales_total = sales.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        card_sales_count = sales.filter(
            payment_method=Sale.PaymentMethod.CARD
        ).count()

        now = timezone.now()
        if timezone.is_aware(now):
            now = timezone.localtime(now)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_total = (
            sales.filter(sold_at__gte=month_start)
                 .aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        )

        items = SaleItem.objects.all()
        if not is_administrator:
            items = items.filter(sale__seller=user)

        top_books_all = top_books(items)
        top_books_month = top_books(items.filter(sale__sold_at__gte=month_start))

        context.update({
            "is_administrator": is_administrator,

            "book_count": book_count,
            "total_book_count": total_book_count,
            "active_percent": calc_percents(book_count, total_book_count),

            "low_stock_count": low_stock_count,
            "low_stock_percent": calc_percents(low_stock_count, book_count),

            "sales_count": sales_count,
            "card_sales_count": card_sales_count,
            "card_percent": calc_percents(card_sales_count, sales_count),

            "sales_total": sales_total,
            "month_total": month_total,
            "month_percent": calc_percents(month_total, sales_total),

            "recent_sales": sales.order_by("-pk")[:8],

            "top_books_month": top_books_month,
            "top_books_all": top_books_all,
        })
        return context


class BookListView(LoginRequiredMixin, ListView):
    model = Book
    template_name = "books/book_list.html"
    context_object_name = "books"
    paginate_by = 10

    def get_queryset(self):
        queryset = Book.objects.select_related(
            "author",
            "category",
            "publisher",
        )

        user = self.request.user

        if not (user.is_superuser or user.is_staff):
            queryset = queryset.filter(is_active=True)

        self.search_form = BookSearchForm(self.request.GET)

        if self.search_form.is_valid():
            query = self.search_form.cleaned_data["q"].strip()

            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query)
                    | Q(author__full_name__icontains=query)
                )

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["search_form"] = getattr(
            self,
            "search_form",
            BookSearchForm(self.request.GET),
        )

        return context


class BookCreateView(AdminRequireMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = 'books/book_form.html'
    success_url = reverse_lazy('book_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Додати книгу'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Книгу додано')
        return super().form_valid(form)


class BookUpdateView(AdminRequireMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = 'books/book_form.html'
    success_url = reverse_lazy('book_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Редагувати книгу'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Дані книги оновлено.')
        return super().form_valid(form)

class SaleCreateView(LoginRequiredMixin, CreateView):
    model = Sale
    form_class = SaleForm
    template_name = 'books/sale_form.html'
    success_url = reverse_lazy('sales_list')

    def form_valid(self, form):
        with transaction.atomic():
            book = Book.objects.select_for_update().get(
                pk= form.cleaned_data['book'].pk
            )
            quantity = form.cleaned_data['quantity']

            if not book.is_active:
                form.add_error('book', 'Ця книга наразі неактивна')
                return self.form_invalid(form)

            if quantity > book.stock_quantity:
                form.add_error(
                    'quantity',
                    f'На складі залишилося лише {book.stock_quantity} шт.')
                return self.form_invalid(form)

            customer = None
            customer_name = form.cleaned_data.get('customer_name').strip()
            customer_phone = form.cleaned_data.get('customer_phone').strip()
            customer_email = form.cleaned_data.get('customer_email', '').strip()

            if customer_name:
                customer = Customer.objects.create(
                    full_name = customer_name,
                    phone = customer_phone,
                    email = customer_email
                )

            total = book.price * quantity

            self.object = form.save(commit=False)
            self.object.seller = self.request.user
            self.object.customer = customer
            self.object.total_amount = total
            self.object.save()

            SaleItem.objects.create(
                sale=self.object,
                book=book,
                quantity=quantity,
                unit_price=book.price
            )

            book.stock_quantity -= quantity
            book.save(update_fields=['stock_quantity'])

            messages.success(
                self.request,
                f'Продаж №{self.object.pk} успішно оформлено.'
            )

            sale_complete_message(customer_email, customer.full_name, book.title, book.price, quantity, total)

        return super().form_valid(form)


class SalesListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'books/sales_list.html'
    context_object_name = 'sales'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'seller', 'customer'
        ).prefetch_related('items__book')

        if not is_admin(self.request.user):
            queryset = queryset.filter(seller= self.request.user)

        return queryset


class SaleDetailsView(LoginRequiredMixin, DetailView):
    model = Sale
    template_name = 'books/sale_detail.html'
    context_object_name = 'sale'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'seller', 'customer'
        ).prefetch_related('items__book')

    def get_object(self, queryset=None):
        sale = super().get_object(queryset)

        if not is_admin(self.request.user) and sale.seller_id != self.request.user.id:
            raise PermissionDenied

        return sale


class ToggleThemeView(View):
    def post(self, req):
        current_theme = req.COOKIES.get("theme", "light")

        new_theme = "light" if current_theme == "dark" else "dark"

        response = redirect(
            req.POST.get("next", "/")
        )

        response.set_cookie(
            "theme",
            new_theme,
            max_age=60 * 60 * 24 * 365,
            samesite="Lax",
        )

        return response

@require_POST
def toggle_theme_view(request):
    current_theme = request.COOKIES.get("theme", "light")
    new_theme = "light" if current_theme == "dark" else "dark"
    next_url = request.POST.get("next", "/")
    response = redirect(next_url)
    max_age_seconds = 60 * 60 * 24 * 365

    response.set_cookie(
        "theme",
        new_theme,
        max_age=max_age_seconds,
        samesite="Lax",
    )

    return response

