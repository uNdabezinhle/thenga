"""Inbox, promotion windows, vouchers, and shop ads."""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem, Coupon
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.notifications.inbox import record_marketing_notice
from apps.notifications.models import InAppNotification
from apps.orders.services import place_order
from apps.promotions.models import ShopAd, Voucher


class OfferTests(TestCase):
    def setUp(self):
        self.jordan = User.objects.create_user(
            email="jordan@northbound.test",
            username="jordan",
            password="correct-horse-42",
            email_verified=True,
        )
        self.other = User.objects.create_user(
            email="other@test.local",
            username="other",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="B", slug="b-offer")
        cat = Category.objects.create(name="C", slug="c-offer")
        self.product = Product.objects.create(
            sku="OF-1",
            name="Offer Pack",
            slug="offer-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("100.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="OF-1-A", label="One"
        )
        Inventory.objects.create(variant=self.variant, quantity=5)
        Coupon.objects.create(
            code="DISCOUNT20",
            discount_type="percentage",
            amount=Decimal("20.00"),
            is_active=True,
            title="20% off",
        )
        self.voucher = Voucher.objects.create(
            code="TRAIL50",
            owner=self.jordan,
            amount=Decimal("50.00"),
            remaining_amount=Decimal("50.00"),
        )

    def _auth(self, user):
        tokens = issue_token_pair(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

    def _cart(self, user):
        cart = Cart.objects.create(user=user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("100.00"),
        )
        return cart

    def test_paid_order_lands_in_the_inbox(self):
        cart = self._cart(self.jordan)
        place_order(
            user=self.jordan,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        note = InAppNotification.objects.get(user=self.jordan, kind="order")
        self.assertEqual(note.title, "Payment confirmed")
        skipped = record_marketing_notice(self.jordan, "Sale", "Opt in first")
        self.assertIsNone(skipped)
        self.assertFalse(
            InAppNotification.objects.filter(user=self.jordan, kind="promotion").exists()
        )

    def test_discount20_applies_and_a_closed_window_does_not(self):
        Coupon.objects.create(
            code="OLD10",
            discount_type="percentage",
            amount=Decimal("10.00"),
            is_active=True,
            ends_at=timezone.now() - timedelta(days=1),
        )
        client = Client()
        headers = self._auth(self.jordan)
        cart = self._cart(self.jordan)
        ok = client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"DISCOUNT20"}',
            content_type="application/json",
            HTTP_X_CART_SESSION="sess-offer",
            **headers,
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()["discounts"][0]["code"], "DISCOUNT20")
        cart.discounts.all().delete()
        closed = client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"OLD10"}',
            content_type="application/json",
            HTTP_X_CART_SESSION="sess-offer",
            **headers,
        )
        self.assertEqual(closed.status_code, 400, closed.content)
        again = client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"DISCOUNT20"}',
            content_type="application/json",
            HTTP_X_CART_SESSION="sess-offer",
            **headers,
        )
        self.assertEqual(again.status_code, 200, again.content)
        stacked = client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"TRAIL50"}',
            content_type="application/json",
            HTTP_X_CART_SESSION="sess-offer",
            **headers,
        )
        self.assertEqual(stacked.status_code, 409, stacked.content)

    def test_trail50_is_personal_and_spent_on_payment(self):
        client = Client()
        denied = client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"TRAIL50"}',
            content_type="application/json",
            **self._auth(self.other),
        )
        self.assertEqual(denied.status_code, 400, denied.content)
        self._cart(self.jordan)
        applied = client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"TRAIL50"}',
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(applied.status_code, 200, applied.content)
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.remaining_amount, Decimal("50.00"))
        place_order(
            user=self.jordan,
            cart=Cart.objects.get(user=self.jordan, is_active=True),
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.remaining_amount, Decimal("0.00"))
        self.assertIsNotNone(self.voucher.redeemed_order_id)

    def test_ads_hide_inactive_banners(self):
        ShopAd.objects.create(
            title="Trail week",
            body="Walk further.",
            product_slug="offer-pack",
            is_active=True,
        )
        ShopAd.objects.create(title="Hidden", body="No", is_active=False)
        response = Client().get("/api/v1/ads/?placement=shop_top")
        self.assertEqual(response.status_code, 200, response.content)
        titles = [row["title"] for row in response.json()["results"]]
        self.assertEqual(titles, ["Trail week"])
        self.assertEqual(response.json()["results"][0]["product_id"], self.product.id)
