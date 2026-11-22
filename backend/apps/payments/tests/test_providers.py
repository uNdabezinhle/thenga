"""Payfast signature + reconciliation tests."""
from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.test import Client, TestCase, override_settings

from apps.accounts.models import Role, User, UserRole
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.services import place_order
from apps.payments.providers import payfast_signature, payfast_verify_itn
from apps.payments.reconciliation import build_reconciliation


class PayfastSignatureTests(TestCase):
    def test_signature_stable(self):
        data = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "amount": "100.00",
            "item_name": "Test",
            "m_payment_id": "NB-1",
        }
        sig1 = payfast_signature(data, passphrase="")
        sig2 = payfast_signature(data, passphrase="")
        self.assertEqual(sig1, sig2)
        self.assertEqual(len(sig1), 32)

    def test_verify_itn(self):
        data = {
            "merchant_id": "10000100",
            "merchant_key": "46f0cd694581a",
            "amount": "50.00",
            "item_name": "Item",
            "m_payment_id": "NB-99",
            "payment_status": "COMPLETE",
        }
        data["signature"] = payfast_signature(
            {k: v for k, v in data.items() if k != "signature"}
        )
        self.assertTrue(payfast_verify_itn(data))
        data["signature"] = "deadbeef"
        self.assertFalse(payfast_verify_itn(data))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ReconciliationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="rec@test.local",
            username="recops",
            password="correct-horse-42",
            email_verified=True,
            is_staff=True,
        )
        role, _ = Role.objects.get_or_create(name="Staff")
        UserRole.objects.get_or_create(user=self.staff, role=role)
        self.user = User.objects.create_user(
            email="recbuy@test.local",
            username="recbuy",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="Rec", slug="rec-b")
        cat = Category.objects.create(name="Rec", slug="rec-c")
        self.product = Product.objects.create(
            sku="REC-1",
            name="Rec Pack",
            slug="rec-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("90.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="REC-1-A", label="Std"
        )
        Inventory.objects.create(variant=self.variant, quantity=5)

    def test_report_counts_paid_orders(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("90.00"),
        )
        place_order(
            user=self.user,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        report = build_reconciliation(date.today())
        self.assertGreaterEqual(report.payments_succeeded, 1)
        self.assertGreaterEqual(report.order_count_paid, 1)
        d = report.as_dict()
        self.assertIn("gross_captured", d)
        self.assertEqual(d["currency"], "ZAR")

    def test_staff_api(self):
        tokens = issue_token_pair(self.staff)
        c = Client()
        r = c.get(
            "/api/v1/payments/reconciliation/",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("exception_count", r.json())
