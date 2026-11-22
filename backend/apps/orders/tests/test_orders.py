"""Order placement, email verification gate, cancel restock."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.models import Order
from apps.orders.services import cancel_order, place_order


class OrderServiceTests(TestCase):
    def setUp(self):
        self.verified = User.objects.create_user(
            email="v@test.local",
            username="verified",
            password="correct-horse-42",
            email_verified=True,
        )
        self.unverified = User.objects.create_user(
            email="u@test.local",
            username="unverified",
            password="correct-horse-42",
            email_verified=False,
        )
        brand = Brand.objects.create(name="B", slug="b")
        cat = Category.objects.create(name="C", slug="c")
        self.product = Product.objects.create(
            sku="O-1",
            name="Order Pack",
            slug="order-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("50.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="O-1-A", label="One"
        )
        self.inv = Inventory.objects.create(variant=self.variant, quantity=5)

    def _cart_for(self, user, qty=1):
        cart = Cart.objects.create(user=user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=qty,
            unit_price_snapshot=Decimal("50.00"),
        )
        return cart

    def test_unverified_cannot_place_order(self):
        from apps.orders.services import OrderError

        cart = self._cart_for(self.unverified)
        with self.assertRaises(OrderError) as ctx:
            place_order(
                user=self.unverified,
                cart=cart,
                idempotency_key=str(uuid.uuid4()),
            )
        self.assertEqual(ctx.exception.default_code, "email_not_verified")

    def test_place_order_reserves_stock_until_payment(self):
        from apps.payments.services import simulate_sandbox_success

        cart = self._cart_for(self.verified, qty=2)
        order, payment, redirect = place_order(
            user=self.verified,
            cart=cart,
            payment_method="card",
            idempotency_key=str(uuid.uuid4()),
        )
        self.inv.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        self.assertEqual(self.inv.quantity, 5)
        self.assertEqual(self.inv.reserved_quantity, 2)
        self.assertEqual(CartItem.objects.filter(cart=cart).count(), 0)
        self.assertTrue(redirect)

        simulate_sandbox_success(payment)
        self.inv.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYMENT_CONFIRMED)
        self.assertEqual(self.inv.quantity, 3)
        self.assertEqual(self.inv.reserved_quantity, 0)

    def test_cancel_releases_reservation(self):
        cart = self._cart_for(self.verified, qty=2)
        order, payment, _ = place_order(
            user=self.verified,
            cart=cart,
            payment_method="card",
            idempotency_key=str(uuid.uuid4()),
        )
        cancel_order(order, actor=self.verified)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 5)
        self.assertEqual(self.inv.reserved_quantity, 0)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    def test_idempotent_order_create(self):
        cart = self._cart_for(self.verified, qty=1)
        key = str(uuid.uuid4())
        o1, _, _ = place_order(
            user=self.verified, cart=cart, payment_method="cod", idempotency_key=key
        )
        o2, _, _ = place_order(
            user=self.verified, cart=cart, payment_method="cod", idempotency_key=key
        )
        self.assertEqual(o1.id, o2.id)
