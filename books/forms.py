from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Book, Sale


class SellerRegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Електронна пошта")

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
        labels = {"username": "Логін"}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ця електронна пошта вже використовується."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = False
        user.is_superuser = False

        if commit:
            user.save()

        return user


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = [
            "title", "author", "category", "publisher",
            "isbn", "price", "stock_quantity", "is_active"
        ]


class SaleForm(forms.ModelForm):
    book = forms.ModelChoiceField(
        queryset=Book.objects.none(),
        label="Книга",
        required=True
    )
    quantity = forms.IntegerField(
        label="Кількість",
        min_value=1,
        initial=1,
        required=True
    )
    customer_name = forms.CharField(
        label="ПІБ покупця",
        max_length=180,
        required=True
    )
    customer_phone = forms.CharField(
        label="Телефон покупця",
        max_length=30,
        required=True
    )
    customer_email =  forms.CharField(
        label="Email покупця",
        max_length=55,
        required=False
    )

    class Meta:
        model = Sale
        fields = ["payment_method"]
        widgets = {
            "payment_method": forms.RadioSelect(attrs={"class": "choice-group"}),
        }
        labels = {"payment_method": "Спосіб оплати"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["book"].queryset = Book.objects.filter(
            is_active=True,
            stock_quantity__gt=0
        ).select_related("author")

    def clean_customer_phone(self):
        phone = self.cleaned_data.get("customer_phone", "").strip()
        allowed = set("0123456789+() -")

        if phone and (
            any(char not in allowed for char in phone)
            or sum(char.isdigit() for char in phone) < 7
        ):
            raise forms.ValidationError(
                "Введіть коректний номер телефону."
            )

        return phone

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["book"].queryset = Book.objects.filter(
            is_active=True,
            stock_quantity__gt=0
        ).select_related("author")

    def clean_customer_phone(self):
        phone = self.cleaned_data.get("customer_phone", "").strip()
        allowed = set("0123456789+() -")

        if phone and (
            any(char not in allowed for char in phone)
            or sum(char.isdigit() for char in phone) < 7
        ):
            raise forms.ValidationError(
                "Введіть коректний номер телефону."
            )

        return phone

class BookSearchForm(forms.Form):
    q = forms.CharField(
        label="Пошук за назвою або автором",
        max_length=100,
        required=False,
        widget=forms.SearchInput(
            attrs={
                "placeholder": "Введіть назву книги або автора",
                "class": "book-search-input",
            }
        ),
    )
