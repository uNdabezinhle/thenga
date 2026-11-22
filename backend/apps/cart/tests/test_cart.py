"""Mandatory cart tests — docs/05-test-strategy.md §4.2 / §4.4."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartDiscount, CartItem, Coupon
from apps.cart.services import merge_carts
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.core.exceptions import CartItemOutOfStock, DiscountAlreadyApplied
from apps.pricing.services import Line, compute_totals


class CartAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="shopper@test.local",
            username="shopper",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="NB", slug="nb")
        cat = Category.objects.create(name="Packs", slug="packs")
        self.product = Product.objects.create(
            sku="T-1",
            name="Test Pack",
            slug="test-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("100.00"),
            hue=10,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="T-1-A",
            label="Regular",
        )
        Inventory.objects.create(variant=self.variant, quantity=6)
        Coupon.objects.create(
            code="DISCOUNT20",
            discount_type="percentage",
            amount=Decimal("20"),
            is_active=True,
        )
        self.session = str(uuid.uuid4())

    def _guest_headers(self, session=None):
        return {"HTTP_X_CART_SESSION": session or self.session}

    def _auth_headers(self, session=None):
        tokens = issue_token_pair(self.user, mfa_verified=False)
        h = self._guest_headers(session)
        h["HTTP_AUTHORIZATION"] = f"Bearer {tokens['access']}"
        return h

    def _post(self, url, payload, **headers):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def test_guest_can_add_and_update_own_cart_item(self):
        h = self._guest_headers()
        r = self._post(
            "/api/v1/cart/cart/add_item/",
            {"product": self.product.id, "variant": self.variant.id, "quantity": 1},
            **h,
        )
        self.assertEqual(r.status_code, 200)
        item_id = r.json()["items"][0]["id"]

        r2 = self._post(
            f"/api/v1/cart/cart/items/{item_id}/update/",
            {"quantity": 3},
            **h,
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["total_items"], 3)

    def test_guest_cannot_update_foreign_cart_item(self):
        h = self._guest_headers()
        r = self._post(
            "/api/v1/cart/cart/add_item/",
            {"product": self.product.id, "variant": self.variant.id, "quantity": 1},
            **h,
        )
        item_id = r.json()["items"][0]["id"]
        other = self._guest_headers(str(uuid.uuid4()))
        r2 = self._post(
            f"/api/v1/cart/cart/items/{item_id}/update/",
            {"quantity": 2},
            **other,
        )
        self.assertEqual(r2.status_code, 404)

    def test_repeated_add_respects_stock(self):
        h = self._guest_headers()
        r1 = self._post(
            "/api/v1/cart/cart/add_item/",
            {"product": self.product.id, "variant": self.variant.id, "quantity": 5},
            **h,
        )
        self.assertEqual(r1.status_code, 200)
        r2 = self._post(
            "/api/v1/cart/cart/add_item/",
            {"product": self.product.id, "variant": self.variant.id, "quantity": 5},
            **h,
        )
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.json()["error"]["code"], "cart_item_out_of_stock")

    def test_discount_cannot_stack(self):
        h = self._guest_headers()
        self._post(
            "/api/v1/cart/cart/add_item/",
            {"product": self.product.id, "variant": self.variant.id, "quantity": 1},
            **h,
        )
        r1 = self._post(
            "/api/v1/cart/cart/apply_discount/",
            {"code": "DISCOUNT20"},
            **h,
        )
        self.assertEqual(r1.status_code, 200)
        r2 = self._post(
            "/api/v1/cart/cart/apply_discount/",
            {"code": "DISCOUNT20"},
            **h,
        )
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(len(r1.json()["discounts"]), 1)

    def test_transfer_cart_rejects_foreign_session(self):
        h = self._auth_headers(session=self.session)
        r = self._post(
            "/api/v1/cart/cart/transfer_cart/",
            {"session_id": str(uuid.uuid4())},
            **h,
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"]["code"], "cart_session_invalid")

    def test_merge_carts_revalidates_stock(self):
        guest_sid = str(uuid.uuid4())
        guest = Cart.objects.create(session_id=guest_sid, is_active=True)
        CartItem.objects.create(
            cart=guest,
            product=self.product,
            variant=self.variant,
            quantity=4,
            unit_price_snapshot=Decimal("100.00"),
        )
        user_cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=user_cart,
            product=self.product,
            variant=self.variant,
            quantity=3,
            unit_price_snapshot=Decimal("100.00"),
        )
        with self.assertRaises(CartItemOutOfStock):
            merge_carts(self.user, guest_sid)

    def test_cart_total_equals_order_total(self):
        """Same basket priced as cart and as order produces identical figures."""
        from apps.cart.services import cart_totals, ensure_shipping_estimates
        from apps.orders.services import place_order

        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=2,
            unit_price_snapshot=Decimal("100.00"),
        )
        CartDiscount.objects.create(
            cart=cart,
            code="DISCOUNT20",
            discount_type="percentage",
            amount=Decimal("20"),
        )
        ensure_shipping_estimates(cart)
        cart.shipping_estimates.update(is_selected=False)
        express = cart.shipping_estimates.get(method_name="Express")
        express.is_selected = True
        express.save()

        before = cart_totals(cart)
        order, payment, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="cod",
            address_text="1 Test St",
            idempotency_key=str(uuid.uuid4()),
        )
        self.assertEqual(order.subtotal, before.subtotal)
        self.assertEqual(order.discount_total, before.discount_total)
        self.assertEqual(order.shipping_total, before.shipping_total)
        self.assertEqual(order.grand_total, before.grand_total)
