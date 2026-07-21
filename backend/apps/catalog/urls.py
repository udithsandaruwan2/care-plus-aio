from django.urls import path

from .views import (
    AddOnListView,
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
