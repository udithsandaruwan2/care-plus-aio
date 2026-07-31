from django.urls import path

from .views import (
    AddOnListView,
    AdminAddOnDetailView,
    AdminAddOnListCreateView,
    AdminCarePackageDetailView,
    AdminCarePackageListCreateView,
    CarePackageListView,
    CheckoutCreateView,
    MockPaymentConfirmView,
    OrderDetailView,
    OrderReceiptView,
    PayHereWebhookView,
    PaymentIntentView,
)

urlpatterns = [
    path("catalog/packages/", CarePackageListView.as_view(), name="catalog_packages"),
    path("catalog/addons/", AddOnListView.as_view(), name="catalog_addons"),
    path(
        "admin/catalog/packages/",
        AdminCarePackageListCreateView.as_view(),
        name="admin_catalog_packages",
    ),
    path(
        "admin/catalog/packages/<int:pk>/",
        AdminCarePackageDetailView.as_view(),
        name="admin_catalog_package_detail",
    ),
    path(
        "admin/catalog/addons/",
        AdminAddOnListCreateView.as_view(),
        name="admin_catalog_addons",
    ),
    path(
        "admin/catalog/addons/<int:pk>/",
        AdminAddOnDetailView.as_view(),
        name="admin_catalog_addon_detail",
    ),
    path("checkout/", CheckoutCreateView.as_view(), name="checkout_create"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/receipt/", OrderReceiptView.as_view(), name="order_receipt"),
    path(
        "orders/<int:pk>/payment-intent/",
        PaymentIntentView.as_view(),
        name="payment_intent",
    ),
    path(
        "payments/mock/<str:provider_intent_id>/confirm/",
        MockPaymentConfirmView.as_view(),
        name="mock_payment_confirm",
    ),
    path(
        "payments/payhere/webhook/",
        PayHereWebhookView.as_view(),
        name="payhere_webhook",
    ),
]
