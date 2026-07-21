from django.urls import path

from .views import AddOnListView, CarePackageListView, CheckoutCreateView, OrderDetailView

urlpatterns = [
    path("catalog/packages/", CarePackageListView.as_view(), name="catalog_packages"),
    path("catalog/addons/", AddOnListView.as_view(), name="catalog_addons"),
    path("checkout/", CheckoutCreateView.as_view(), name="checkout_create"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order_detail"),
]
