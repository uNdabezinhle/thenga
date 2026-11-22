"""Stale pending payment release tests."""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.models import Order, Payment
from apps.orders.services import place_order
from apps.payments.tasks import release_stale_pending_payments


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class StalePaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="stale@test.local",
            username="staler",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="S", slug="s-stale")
        cat = Category.objects.create(name="S", slug="s-stale-c")
        self.product = Product.objects.create(
            sku="ST-1",
            name="Stale Pack",
            slug="stale-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("100.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="ST-1-A", label="Std"
        )
        self.inv = Inventory.objects.create(variant=self.variant, quantity=5)

    def test_releases_reserved_stock(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=2,
            unit_price_snapshot=Decimal("100.00"),
        )
        order, payment, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="card",
            idempotency_key=str(uuid.uuid4()),
        )
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.reserved_quantity, 2)

        # Age the payment
        old = timezone.now() - timedelta(hours=3)
        Payment.objects.filter(pk=payment.pk).update(created_at=old)
        Order.objects.filter(pk=order.pk).update(placed_at=old)

        result = release_stale_pending_payments(hours=2)
        self.assertEqual(result["cancelled_orders"], 1)
        order.refresh_from_db()
        payment.refresh_from_db()
        self.inv.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(self.inv.reserved_quantity, 0)
        self.assertEqual(self.inv.quantity, 5)

    def test_ignores_fresh_pending(self):
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("100.00"),
        )
        place_order(
            user=self.user,
            cart=cart,
            payment_method="card",
            idempotency_key=str(uuid.uuid4()),
        )
        result = release_stale_pending_payments(hours=2)
        self.assertEqual(result["cancelled_orders"], 0)
