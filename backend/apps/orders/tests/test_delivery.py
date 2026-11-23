"""Sandbox courier booking and the shipment payload on an order."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import Role, User, UserRole
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.couriers import get_courier
from apps.orders.models import Order, Shipment
from apps.orders.services import advance_order, place_order


class DeliveryTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="buyer@test.local",
            username="buyer",
            password="correct-horse-42",
            email_verified=True,
        )
        self.staff = User.objects.create_user(
            email="ops@test.local",
            username="ops",
            password="correct-horse-42",
            email_verified=True,
            is_staff=True,
        )
        role, _ = Role.objects.get_or_create(name="Staff")
        UserRole.objects.get_or_create(user=self.staff, role=role)
        brand = Brand.objects.create(name="B", slug="b-del")
        cat = Category.objects.create(name="C", slug="c-del")
        self.product = Product.objects.create(
            sku="DL-1",
            name="Delivery Pack",
            slug="delivery-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("80.00"),
        )
        variant = ProductVariant.objects.create(product=self.product, sku="DL-1-A", label="One")
        Inventory.objects.create(variant=variant, quantity=5)
        self.variant = variant

    def _packed_order(self):
        cart = Cart.objects.create(user=self.customer, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("80.00"),
        )
        order, _, _ = place_order(
            user=self.customer,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        order = advance_order(order, actor=self.staff)
        self.assertEqual(order.status, Order.Status.PACKED)
        return order

    def _auth(self, user):
        tokens = issue_token_pair(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

    def test_sandbox_quotes_keep_the_domestic_rates(self):
        quotes = get_courier().quote()
        self.assertEqual(
            [(q.method_name, q.price) for q in quotes],
            [
                ("Standard", Decimal("0.00")),
                ("Express", Decimal("14.50")),
                ("Next day", Decimal("29.00")),
            ],
        )

    def test_dispatch_is_idempotent_and_visible_to_the_customer(self):
        order = self._packed_order()
        client = Client()
        first = client.post(
            f"/api/v1/orders/staff/{order.reference}/dispatch/",
            **self._auth(self.staff),
        )
        self.assertEqual(first.status_code, 200, first.content)
        tracking = first.json()["shipment"]["tracking_number"]
        self.assertTrue(tracking.startswith("SBX"))
        self.assertEqual(first.json()["shipment"]["carrier"], "Northbound Courier")
        self.assertEqual(first.json()["status"], Order.Status.OUT_FOR_DELIVERY)
        self.assertEqual(first.json()["shipment"]["events"][0]["status"], "dispatched")

        second = client.post(
            f"/api/v1/orders/staff/{order.reference}/dispatch/",
            **self._auth(self.staff),
        )
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(second.json()["shipment"]["tracking_number"], tracking)
        self.assertEqual(
            Shipment.objects.filter(order__reference=order.reference).count(),
            1,
        )

        denied = client.post(
            f"/api/v1/orders/staff/{order.reference}/dispatch/",
            **self._auth(self.customer),
        )
        self.assertEqual(denied.status_code, 403)

        own = client.get(
            f"/api/v1/orders/{order.reference}/",
            **self._auth(self.customer),
        )
        self.assertEqual(own.status_code, 200, own.content)
        self.assertEqual(own.json()["shipment"]["tracking_number"], tracking)

    def test_courier_delivered_completes_the_order(self):
        order = self._packed_order()
        client = Client()
        booked = client.post(
            f"/api/v1/orders/staff/{order.reference}/dispatch/",
            **self._auth(self.staff),
        )
        self.assertEqual(booked.status_code, 200, booked.content)
        moving = client.post(
            f"/api/v1/orders/staff/{order.reference}/courier/",
            data=json.dumps({"status": "in_transit"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(moving.status_code, 200, moving.content)
        self.assertEqual(moving.json()["shipment"]["status"], "in_transit")
        self.assertEqual(moving.json()["status"], Order.Status.OUT_FOR_DELIVERY)

        done = client.post(
            f"/api/v1/orders/staff/{order.reference}/courier/",
            data=json.dumps({"status": "delivered"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(done.status_code, 200, done.content)
        body = done.json()
        self.assertEqual(body["status"], Order.Status.DELIVERED)
        self.assertEqual(body["shipment"]["status"], "delivered")
        self.assertIsNotNone(body["shipment"]["delivered_at"])
