from django.urls import path

from .views import (
    PaymentMethodDetailView,
    PaymentMethodsView,
    SetupIntentView,
    StripeWebhookView,
)

urlpatterns = [
    path("payments/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("payments/methods/", PaymentMethodsView.as_view(), name="payment-methods"),
    path(
        "payments/methods/setup-intent/", SetupIntentView.as_view(), name="payment-setup-intent"
    ),
    path(
        "payments/methods/<str:payment_method_id>/",
        PaymentMethodDetailView.as_view(),
        name="payment-method-detail",
    ),
]
