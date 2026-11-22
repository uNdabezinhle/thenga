"""Tax invoice generation tests."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.invoices import invoice_context, render_invoice_html, split_vat_inclusive
from apps.orders.models import Order
from apps.orders.services import place_order


class InvoiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="inv@test.local",
            username="invoicer",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="I", slug="i-brand")
        cat = Category.objects.create(name="C", slug="c-inv")
        self.product = Product.objects.create(
            sku="INV-1",
            name="Invoice Pack",
            slug="invoice-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("115.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="INV-1-A", label="Std"
        )
        Inventory.objects.create(variant=self.variant, quantity=5)

    def test_vat_split(self):
        net, vat = split_vat_inclusive(Decimal("115.00"))
        self.assertEqual(net + vat, Decimal("115.00"))
        self.assertEqual(net, Decimal("100.00"))
        self.assertEqual(vat, Decimal("15.00"))

    def test_invoice_html_contains_reference(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("115.00"),
        )
        order, _, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        html = render_invoice_html(order)
        self.assertIn(order.reference, html)
        self.assertIn("Tax invoice", html)
        self.assertIn("INV-", html)
        ctx = invoice_context(order)
        self.assertEqual(ctx["currency"], "ZAR")

    def test_invoice_endpoint(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("115.00"),
        )
        order, _, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        tokens = issue_token_pair(self.user)
        c = Client()
        r = c.get(
            f"/api/v1/orders/{order.reference}/invoice/",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Tax invoice", r.content)
        self.assertIn(order.reference.encode(), r.content)
        js = c.get(
            f"/api/v1/orders/{order.reference}/invoice/?format=json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(js.status_code, 200)
        body = js.json()
        self.assertTrue(body["invoice_number"].startswith("INV-"))
        self.assertEqual(body["vat_rate_pct"], "15")

    def test_invoice_blocked_when_unpaid(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("115.00"),
        )
        order, _, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="card",
            idempotency_key=str(uuid.uuid4()),
        )
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        tokens = issue_token_pair(self.user)
        c = Client()
        r = c.get(
            f"/api/v1/orders/{order.reference}/invoice/",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 409)
