from django.urls import path

from . import staff_views, views

urlpatterns = [
    path("initiate/", views.initiate, name="payment-initiate"),
    path("refunds/", staff_views.create_refund, name="payment-refund-create"),
    path("refunds/list/", staff_views.list_refunds, name="payment-refund-list"),
    path("reconciliation/", staff_views.reconciliation, name="payment-reconciliation"),
    path("sandbox/complete/", views.complete_sandbox, name="payment-sandbox-complete"),
    path("sandbox/checkout/", views.sandbox_checkout_page, name="payment-sandbox-checkout"),
    path("sandbox/simulate/", views.sandbox_simulate, name="payment-sandbox-simulate"),
    path("webhooks/sandbox/", views.sandbox_webhook, name="payment-webhook-sandbox"),
    path("webhooks/payfast/", views.payfast_itn, name="payment-webhook-payfast"),
    path("payfast/redirect/", views.payfast_redirect, name="payment-payfast-redirect"),
]
