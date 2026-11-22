"""ECTA s44 cooling-off tests — REKA-FR-ORD-011."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.cooling_off import cooling_off_status, exercise_cooling_off
from apps.orders.models import Order, OrderEvent
from apps.orders.services import place_order


class CoolingOffTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cool@test.local",
            username="cooler",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="C", slug="c-cool")
        cat = Category.objects.create(name="C", slug="c-cool-cat")
        self.product = Product.objects.create(
            sku="CO-1",
            name="Cool Pack",
            slug="cool-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("150.00"),
            cooling_off_excluded=False,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="CO-1-A", label="Std"
        )
        Inventory.objects.create(variant=self.variant, quantity=5)

    def _order(self, *, excluded=False):
        if excluded:
            self.product.cooling_off_excluded = True
            self.product.save(update_fields=["cooling_off_excluded"])
        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("150.00"),
        )
        order, _, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        return order

    def test_eligible_within_7_days(self):
        order = self._order()
        s = cooling_off_status(order)
        self.assertTrue(s.eligible)
        self.assertIsNotNone(s.deadline)

    def test_excluded_product(self):
        order = self._order(excluded=True)
        s = cooling_off_status(order)
        self.assertFalse(s.eligible)
        self.assertTrue(s.excluded_items)

    def test_expired_window(self):
        order = self._order()
        past = timezone.now() - timedelta(days=10)
        OrderEvent.objects.filter(
            order=order, to_status=Order.Status.PAYMENT_CONFIRMED
        ).update(created_at=past)
        # also age placed_at fallback
        Order.objects.filter(pk=order.pk).update(placed_at=past)
        order.refresh_from_db()
        s = cooling_off_status(order)
        self.assertFalse(s.eligible)
        self.assertIn("ended", (s.reason or "").lower())

    def test_exercise_refunds(self):
        order = self._order()
        order = exercise_cooling_off(order, user=self.user, reason="Changed mind")
        self.assertEqual(order.status, Order.Status.REFUNDED)

    def test_api_exercise(self):
        order = self._order()
        tokens = issue_token_pair(self.user)
        c = Client()
        r = c.get(
            f"/api/v1/orders/{order.reference}/cooling-off/",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["eligible"])

        r2 = c.post(
            f"/api/v1/orders/{order.reference}/cooling-off/exercise/",
            data=json.dumps({"reason": "Changed mind"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(r2.json()["status"], "refunded")
        self.assertFalse(r2.json()["cooling_off"]["eligible"])

    def test_other_user_404(self):
        order = self._order()
        other = User.objects.create_user(
            email="other@test.local",
            username="other",
            password="correct-horse-42",
            email_verified=True,
        )
        tokens = issue_token_pair(other)
        c = Client()
        r = c.post(
            f"/api/v1/orders/{order.reference}/cooling-off/exercise/",
            data="{}",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 404)
