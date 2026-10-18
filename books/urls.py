from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    BookListView, DashboardTemplateView, SaleDetailsView,
    SystemLoginView, SellerRegisterView, SalesListView,
    HomeView, BookCreateView, BookUpdateView, SaleCreateView,
    ToggleThemeView
)

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("register/", SellerRegisterView.as_view(), name="register"),
    path("login/", SystemLoginView.as_view(), name="login"),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout"
    ),
    path("dashboard/", DashboardTemplateView.as_view(), name="dashboard"),
    path("books/", BookListView.as_view(), name="book_list"),
    path("books/add/", BookCreateView.as_view(), name="book_create"),
    path(
        "books/<int:pk>/edit/",
        BookUpdateView.as_view(),
        name="book_edit"
    ),
    path("sales/", SalesListView.as_view(), name="sales_list"),
    path("sales/add/", SaleCreateView.as_view(), name="sale_create"),
    path(
        "sales/<int:pk>/",
        SaleDetailsView.as_view(),
        name="sale_detail"
    ),
    path("toggle-theme/", ToggleThemeView.as_view(), name="toggle_theme"),
]
