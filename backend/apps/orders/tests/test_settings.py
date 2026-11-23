"""Staff store settings: delivery prices, banners, and the shared promotion."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem, Coupon
from apps.cart.services import ensure_shipping_estimates
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.couriers import get_courier
from apps.orders.models import Order, ShippingRate
from apps.orders.services import place_order
from apps.promotions.models import ShopAd


class StoreSettingsTests(TestCase):
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
        brand = Brand.objects.create(name="B", slug="b-set")
        cat = Category.objects.create(name="C", slug="c-set")
        self.product = Product.objects.create(
            sku="SET-1",
            name="Settings Pack",
            slug="settings-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("100.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="SET-1-A", label="One"
        )
        Inventory.objects.create(variant=self.variant, quantity=5)
        Coupon.objects.create(
            code="DISCOUNT20",
            discount_type="percentage",
            amount=Decimal("20.00"),
            is_active=True,
            title="20% off",
        )
        self.ad = ShopAd.objects.create(
            title="Trail week",
            body="Walk further.",
            product_slug="settings-pack",
            is_active=True,
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

    def test_customer_cannot_change_store_settings(self):
        client = Client()
        headers = self._auth(self.customer)
        rates = client.get("/api/v1/orders/staff/shipping-rates/", **headers)
        self.assertEqual(rates.status_code, 403, rates.content)
        ads = client.patch(
            f"/api/v1/ads/staff/{self.ad.id}/",
            data='{"is_active": false}',
            content_type="application/json",
            **headers,
        )
        self.assertEqual(ads.status_code, 403, ads.content)
        promo = client.patch(
            "/api/v1/promotions/staff/DISCOUNT20/",
            data='{"amount": "5.00"}',
            content_type="application/json",
            **headers,
        )
        self.assertEqual(promo.status_code, 403, promo.content)

    def test_staff_price_change_updates_new_quotes_only(self):
        cart = self._cart(self.customer)
        estimates = ensure_shipping_estimates(cart)
        express = next(row for row in estimates if row.method_name == "Express")
        cart.shipping_estimates.update(is_selected=False)
        express.is_selected = True
        express.save(update_fields=["is_selected"])
        order, _, _ = place_order(
            user=self.customer,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        charged = order.shipping_total
        rate = ShippingRate.objects.get(method_name="Express")
        client = Client()
        saved = client.patch(
            f"/api/v1/orders/staff/shipping-rates/{rate.id}/",
            data=json.dumps({"price": "20.00", "estimated_days": "2 days"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        order.refresh_from_db()
        self.assertEqual(order.shipping_total, charged)
        self.assertEqual(order.status, Order.Status.PAYMENT_CONFIRMED)
        quoted = {row.method_name: row.price for row in get_courier().quote()}
        self.assertEqual(quoted["Express"], Decimal("20.00"))
        fresh = self._cart(self.customer)
        fresh_express = next(
            row for row in ensure_shipping_estimates(fresh) if row.method_name == "Express"
        )
        self.assertEqual(fresh_express.price, Decimal("20.00"))

    def test_deactivating_a_banner_hides_it(self):
        client = Client()
        saved = client.patch(
            f"/api/v1/ads/staff/{self.ad.id}/",
            data='{"is_active": false}',
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        public = client.get("/api/v1/ads/?placement=shop_top")
        self.assertEqual(public.json()["results"], [])
        staff_list = client.get("/api/v1/ads/staff/", **self._auth(self.staff))
        self.assertEqual(staff_list.json()["results"][0]["title"], "Trail week")
        self.assertFalse(staff_list.json()["results"][0]["is_active"])

    def test_promotion_amount_changes_the_cart_discount(self):
        client = Client()
        saved = client.patch(
            "/api/v1/promotions/staff/DISCOUNT20/",
            data='{"amount": "10.00", "title": "10% off the trail shop"}',
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self._cart(self.customer)
        applied = client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"DISCOUNT20"}',
            content_type="application/json",
            **self._auth(self.customer),
        )
        self.assertEqual(applied.status_code, 200, applied.content)
        self.assertEqual(applied.json()["totals"]["discount_total"], "10.00")
        closed = client.patch(
            "/api/v1/promotions/staff/DISCOUNT20/",
            data='{"ends_at": "2020-01-01T00:00:00Z"}',
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(closed.status_code, 200, closed.content)
        public = client.get("/api/v1/promotions/")
        self.assertEqual(public.json()["results"], [])
