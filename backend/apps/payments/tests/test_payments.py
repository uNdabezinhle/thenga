"""Payment webhook + SAQ A sandbox tests (REKA-FR-PAY-003/004)."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase, override_settings

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.models import Order, Payment
from apps.orders.services import place_order
from apps.notifications.models import NotificationLog
from apps.payments.providers import SandboxProvider
from apps.payments.services import process_sandbox_webhook, simulate_sandbox_success


class PaymentWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="pay@test.local",
            username="payer",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="P", slug="p")
        cat = Category.objects.create(name="C", slug="c-pay")
        self.product = Product.objects.create(
            sku="PAY-1",
            name="Pay Pack",
            slug="pay-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("80.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="PAY-1-A", label="Std"
        )
        self.inv = Inventory.objects.create(variant=self.variant, quantity=4)

    def _order(self, method="card"):
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("80.00"),
        )
        return place_order(
            user=self.user,
            cart=cart,
            payment_method=method,
            idempotency_key=str(uuid.uuid4()),
        )

    def test_card_order_awaits_webhook(self):
        order, payment, redirect = self._order("card")
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(redirect)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.reserved_quantity, 1)
        self.assertEqual(self.inv.quantity, 4)

    def test_webhook_confirms_and_commits_stock(self):
        order, payment, _ = self._order("card")
        payment = simulate_sandbox_success(payment)
        order.refresh_from_db()
        self.inv.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(order.status, Order.Status.PAYMENT_CONFIRMED)
        self.assertEqual(self.inv.quantity, 3)
        self.assertEqual(self.inv.reserved_quantity, 0)

    def test_webhook_idempotent(self):
        order, payment, _ = self._order("card")
        p1 = simulate_sandbox_success(payment)
        p2 = simulate_sandbox_success(payment)
        self.assertEqual(p1.id, p2.id)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 3)  # only once

    def test_failed_webhook_sends_one_mail(self):
        order, payment, _ = self._order("card")
        body = json.dumps(
            {
                "provider_reference": payment.provider_reference,
                "status": "failed",
                "amount": "80.00",
                "event_id": str(uuid.uuid4()),
            }
        ).encode()
        sig = SandboxProvider().sign(body)
        process_sandbox_webhook(body, sig)
        process_sandbox_webhook(body, sig)
        logs = NotificationLog.objects.filter(template="payment_failed")
        self.assertEqual(logs.count(), 1)
        self.assertIn(order.reference, logs.get().subject)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)

    def test_webhook_rejects_bad_signature(self):
        order, payment, _ = self._order("card")
        body = json.dumps(
            {
                "provider_reference": payment.provider_reference,
                "status": "succeeded",
                "amount": "80.00",
            }
        ).encode()
        with self.assertRaises(Exception):
            process_sandbox_webhook(body, "not-a-real-signature")

    def test_webhook_http_endpoint(self):
        order, payment, _ = self._order("card")
        body = json.dumps(
            {
                "provider_reference": payment.provider_reference,
                "status": "succeeded",
                "amount": "80.00",
                "card_last4": "4242",
                "card_brand": "Visa",
                "event_id": str(uuid.uuid4()),
            }
        ).encode()
        sig = SandboxProvider().sign(body)
        c = Client()
        r = c.post(
            "/api/v1/payments/webhooks/sandbox/",
            data=body,
            content_type="application/json",
            HTTP_X_SANDBOX_SIGNATURE=sig,
        )
        self.assertEqual(r.status_code, 200, r.content)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYMENT_CONFIRMED)

    def test_cod_confirms_immediately(self):
        order, payment, redirect = self._order("cod")
        self.assertEqual(order.status, Order.Status.PAYMENT_CONFIRMED)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(redirect, "")
