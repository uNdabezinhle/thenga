"""Ad share, reminders, merchant mail, and the first-run command."""
from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.notifications.models import NotificationLog
from apps.notifications.reminders import run_reminders
from apps.notifications.services import notify_order_confirmation
from apps.orders.models import Order, OrderItem
from apps.platform.models import Merchant, MerchantAddOn
from apps.pos.models import Store
from apps.promotions.models import AdShareStatement, ShopAd


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RemainingProgrammeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            email="owner@kiosk.test",
            username="kiosk",
            password="correct-horse-42",
            email_verified=True,
        )
        self.buyer = User.objects.create_user(
            email="buyer@kiosk.test",
            username="buyer",
            password="correct-horse-42",
            email_verified=True,
        )

    def _auth(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {issue_token_pair(user)['access']}"}

    def _open(self, addons=None):
        payload = {
            "trading_name": "Kiosk",
            "package": "shop_till",
            "privacy_accepted": True,
            "empty_catalogue_ok": True,
            "addons": addons or [],
        }
        response = self.client.post(
            "/api/v1/platform/onboarding/",
            data=json.dumps(payload),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(response.status_code, 201, response.content)
        return Merchant.objects.get(slug=response.json()["slug"])

    def _product(self, merchant):
        brand = Brand.objects.create(name="K", slug=f"k-{merchant.id}")
        category = Category.objects.create(name="C", slug=f"c-{merchant.id}")
        product = Product.objects.create(
            sku=f"K-{merchant.id}",
            name="Kiosk Mug",
            slug=f"kiosk-mug-{merchant.id}",
            brand=brand,
            category=category,
            base_price=Decimal("40.00"),
            merchant=merchant,
        )
        variant = ProductVariant.objects.create(product=product, sku=f"K-{merchant.id}-A", label="One")
        Inventory.objects.create(variant=variant, quantity=20, reserved_quantity=0)
        return product, variant

    def test_operated_clicks_build_a_share_and_self_serve_does_not(self):
        merchant = self._open(["ads_self_serve"])
        operated = ShopAd.objects.create(
            title="Reka placement",
            source="operated",
            merchant=merchant,
            is_active=True,
        )
        own = ShopAd.objects.create(
            title="Own banner",
            source="self_serve",
            merchant=merchant,
            is_active=True,
        )
        self.assertEqual(self.client.post(f"/api/v1/ads/{operated.id}/click/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/ads/{operated.id}/click/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/ads/{own.id}/click/").status_code, 200)
        desk = self.client.get("/api/v1/platform/ads/", **self._auth(self.owner))
        self.assertEqual(desk.status_code, 200)
        statement = desk.json()["statement"]
        self.assertEqual(statement["clicks"], 2)
        self.assertEqual(statement["gross"], "2.00")
        self.assertEqual(statement["merchant_share"], "0.60")
        self.assertEqual(statement["reka_fee"], "1.40")
        self.assertTrue(statement["prices_are_illustrative"])
        blocked = self.client.patch(
            f"/api/v1/ads/staff/{operated.id}/",
            data=json.dumps({"title": "Mine"}),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(blocked.status_code, 403)
        off = self.client.patch(
            "/api/v1/platform/ads/",
            data=json.dumps({"operated_ads": False}),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(off.status_code, 200)
        self.assertFalse(off.json()["operated_ads"])
        hidden = self.client.post(f"/api/v1/ads/{operated.id}/click/")
        self.assertEqual(hidden.status_code, 404)

    def test_reminder_sends_once_and_the_log_is_merchant_scoped(self):
        merchant = self._open(["reminders"])
        product, variant = self._product(merchant)
        order = Order.objects.create(
            reference="NB-880001",
            user=self.buyer,
            status=Order.Status.AWAITING_PAYMENT,
            subtotal=Decimal("40.00"),
            grand_total=Decimal("40.00"),
        )
        Order.objects.filter(pk=order.pk).update(placed_at=timezone.now() - timedelta(hours=3))
        OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            product_name_snapshot=product.name,
            sku_snapshot=variant.sku,
            unit_price=Decimal("40.00"),
            quantity=1,
            line_total=Decimal("40.00"),
        )
        other = User.objects.create_user(
            email="other@shop.test", username="other", password="correct-horse-42", email_verified=True
        )
        self.client.post(
            "/api/v1/platform/onboarding/",
            data=json.dumps(
                {
                    "trading_name": "Other",
                    "package": "shop",
                    "privacy_accepted": True,
                    "empty_catalogue_ok": True,
                }
            ),
            content_type="application/json",
            **self._auth(other),
        )
        first = run_reminders(timezone.now())
        second = run_reminders(timezone.now())
        self.assertEqual(first["unpaid"], 1)
        self.assertEqual(second["unpaid"], 0)
        self.assertIn("Sent with Reka", mail.outbox[0].body)
        log = self.client.get("/api/v1/notifications/log/", **self._auth(self.owner))
        self.assertEqual(log.status_code, 200)
        self.assertEqual(len(log.json()["results"]), 1)
        other_log = self.client.get("/api/v1/notifications/log/", **self._auth(other))
        self.assertEqual(other_log.json()["results"], [])
        guest = self.client.get("/api/v1/notifications/log/", **self._auth(self.buyer))
        self.assertEqual(guest.status_code, 403)
        self.assertTrue(NotificationLog.objects.filter(template="payment_reminder", merchant=merchant).exists())

    def test_merchant_order_mail_uses_the_trading_name(self):
        merchant = self._open()
        product, variant = self._product(merchant)
        order = Order.objects.create(
            reference="NB-880002",
            user=self.buyer,
            status=Order.Status.PAYMENT_CONFIRMED,
            subtotal=Decimal("40.00"),
            grand_total=Decimal("40.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            product_name_snapshot=product.name,
            sku_snapshot=variant.sku,
            unit_price=Decimal("40.00"),
            quantity=1,
            line_total=Decimal("40.00"),
        )
        notify_order_confirmation(order)
        self.assertIn("Kiosk", mail.outbox[0].subject)
        self.assertIn("Sent with Reka", mail.outbox[0].body)

    def test_reviews_delivery_and_loyalty_stay_off_without_the_extra(self):
        merchant = self._open()
        product, _variant = self._product(merchant)
        review = self.client.post(
            f"/api/v1/products/{product.id}/reviews/?merchant={merchant.slug}",
            data=json.dumps({"rating": 5, "body": "Good mug"}),
            content_type="application/json",
            **self._auth(self.buyer),
        )
        self.assertEqual(review.status_code, 400)
        self.assertEqual(review.json()["error"]["code"], "package_excluded")
        MerchantAddOn.objects.create(merchant=merchant, code="reviews")
        allowed = self.client.post(
            f"/api/v1/products/{product.id}/reviews/?merchant={merchant.slug}",
            data=json.dumps({"rating": 5, "body": "Good mug"}),
            content_type="application/json",
            **self._auth(self.buyer),
        )
        self.assertEqual(allowed.status_code, 200)

    def test_setup_reka_does_not_load_the_sample_catalogue(self):
        out = StringIO()
        call_command(
            "setup_reka",
            "--trading-name",
            "Harbour Goods",
            "--owner-email",
            "ada@harbour.test",
            "--password",
            "correct-horse-42",
            "--package",
            "till",
            stdout=out,
        )
        self.assertFalse(Product.objects.filter(merchant__isnull=True).exists())
        self.assertTrue(Merchant.objects.filter(trading_name="Harbour Goods", package="till").exists())
        self.assertIn("Verify", mail.outbox[0].subject)
        self.assertFalse(AdShareStatement.objects.exists())
        self.assertTrue(Store.objects.filter(merchant__trading_name="Harbour Goods").exists())
