"""Notification email + preference tests."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.accounts.models import User
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.cart.models import Cart, CartItem
from apps.notifications.models import NotificationLog, NotificationPreference
from apps.notifications.services import (
    notify_email_verification,
    notify_order_confirmation,
    send_email,
)
from apps.orders.services import place_order
from apps.payments.services import simulate_sandbox_success


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_BROKER_URL="",
)
class NotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="note@test.local",
            username="noter",
            password="correct-horse-42",
            email_verified=True,
        )

    def test_send_verification_email(self):
        log = notify_email_verification(self.user, "tok-abc")
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Verify", mail.outbox[0].subject)
        self.assertIn("tok-abc", mail.outbox[0].body)

    def test_marketing_skipped_without_consent(self):
        NotificationPreference.objects.create(
            user=self.user, email_marketing=False
        )
        log = send_email(
            to=self.user.email,
            subject="Sale!",
            template="email_verification",
            context={"token": "x", "link": "http://x", "user": self.user},
            user=self.user,
            transactional=False,
        )
        self.assertEqual(log.status, NotificationLog.Status.SKIPPED)
        self.assertEqual(len(mail.outbox), 0)

    def test_order_confirmation_on_payment(self):
        brand = Brand.objects.create(name="N", slug="n-note")
        cat = Category.objects.create(name="C", slug="c-note")
        product = Product.objects.create(
            sku="N-1",
            name="Note Pack",
            slug="note-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("40.00"),
        )
        variant = ProductVariant.objects.create(
            product=product, sku="N-1-A", label="One"
        )
        Inventory.objects.create(variant=variant, quantity=3)
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=product,
            variant=variant,
            quantity=1,
            unit_price_snapshot=Decimal("40.00"),
        )
        order, payment, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="card",
            idempotency_key="note-pay-1",
        )
        mail.outbox.clear()
        simulate_sandbox_success(payment)
        self.assertTrue(
            any("confirmed" in m.subject.lower() for m in mail.outbox),
            [m.subject for m in mail.outbox],
        )

    def test_preferences_api(self):
        from apps.accounts.tokens import issue_token_pair

        tokens = issue_token_pair(self.user)
        c = Client()
        r = c.get(
            "/api/v1/notifications/preferences/",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["email_marketing"])

        r2 = c.patch(
            "/api/v1/notifications/preferences/",
            data=json.dumps({"email_marketing": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["email_marketing"])
        # transactional cannot be disabled
        self.assertTrue(r2.json()["email_transactional"])

    def test_device_register(self):
        from apps.accounts.tokens import issue_token_pair

        tokens = issue_token_pair(self.user)
        c = Client()
        r = c.post(
            "/api/v1/notifications/devices/",
            data=json.dumps({"token": "fcm-device-token-1", "platform": "android"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["platform"], "android")
