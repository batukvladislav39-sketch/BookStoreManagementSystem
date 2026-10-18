from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import redirect
from .forms import SellerRegistrationForm, BookForm, SaleForm
from .models import Book, Customer, Sale, SaleItem
from django.views.generic import ListView, TemplateView, CreateView, UpdateView, DetailView, View
from django.urls import reverse_lazy
from django.db.models import Q
from decimal import Decimal
from django.contrib.auth.views import LoginView
from django.db import transaction

def is_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.is_staff
    )

class AdminRequireMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_admin(self.request.user)


class HomeView(TemplateView):
    template_name = "books/home.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")

        return super().dispatch(request, *args, **kwargs)


class SellerRegisterView(CreateView):
    form_class = SellerRegistrationForm
    template_name = "books/register.html"
    success_url = "/dashboard/"

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

        active_books = Book.objects.filter(is_active= True)

        sales = (
            Sale.objects
                .select_related('seller', 'customer')
                .prefetch_related('items__book')
        )

        if not is_administrator:
            sales = sales.filter(seller= user)

        sales_stats = sales.aggregate(
            total = Sum('total_amount')
        )

        context.update({
            "is_administrator": is_administrator,

            "book_count": active_books.count(),

            "low_stock_count": active_books.filter(
                stock_quantity__lte=5
            ).count(),

            "sales_count": sales.count(),

            "sales_total": (
                    sales_stats["total"] or Decimal("0.00")
            ),

            "recent_sales": sales.order_by("-pk")[:8],
        })

        return context


class BookListView(LoginRequiredMixin, ListView):
    model = Book
    template_name = 'books/book_list.html'
    context_object_name = 'books'

    def get_queryset(self):
        queryset = Book.objects.select_related(
            'author', 'category', 'publisher'
        )

        user = self.request.user

        if not (user.is_superuser or user.is_staff):
            queryset = queryset.filter(is_active=True)

        query = self.request.GET.get("q", "").strip()

        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(author__full_name__icontains=query)
            )

        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()

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
            customer_name = form.cleaned_data.get('customer_name', '').strip()
            customer_phone = form.cleaned_data.get('customer_phone', '').strip()

            if customer_name:
                customer = Customer.objects.create(
                    full_name = customer_name,
                    phone = customer_phone
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

        return super().form_valid(form)


class SalesListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'books/sales_list.html'
    context_object_name = 'sales'

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


