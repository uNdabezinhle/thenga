"""Merchant onboarding, packages, and till-only shops."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.catalogue.models import Inventory, Product, ProductVariant
from apps.pos.models import Store, StoreStock
from apps.platform.models import Merchant
from apps.promotions.models import ShopAd


class PlatformTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            email="owner@shop.test",
            username="owner",
            password="correct-horse-42",
            email_verified=True,
        )
        self.staff = User.objects.create_user(
            email="staff@northbound.test",
            username="staff",
            password="staff-ops-42",
            email_verified=True,
            is_staff=True,
        )

    def _auth(self, user):
        tokens = issue_token_pair(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

    def _open(self, package="till"):
        return self.client.post(
            "/api/v1/platform/onboarding/",
            data=json.dumps(
                {
                    "trading_name": "Kiosk",
                    "package": package,
                    "city": "Cape Town",
                    "privacy_accepted": True,
                    "empty_catalogue_ok": True,
                    "addons": ["loyalty"],
                }
            ),
            content_type="application/json",
            **self._auth(self.owner),
        )

    def test_packages_are_public_and_marked_illustrative(self):
        response = self.client.get("/api/v1/platform/packages/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["prices_are_illustrative"])
        codes = [row["code"] for row in body["packages"]]
        self.assertEqual(codes, ["till", "shop", "shop_till"])
        self.assertEqual(body["ads"]["merchant_share_percent"], "30.00")

    def test_onboarding_starts_an_empty_shop(self):
        response = self._open()
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["trading_name"], "Kiosk")
        self.assertTrue(body["pos"])
        self.assertTrue(body["shop"])
        self.assertEqual(Product.objects.filter(merchant__slug=body["slug"]).count(), 0)
        page = self.client.get("/welcome/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"One shop. Counter and web.", page.content)

    def test_till_package_hides_the_public_shop_and_still_sells(self):
        opened = self._open("till")
        slug = opened.json()["slug"]
        merchant = Merchant.objects.get(slug=slug)
        merchant.status = Merchant.Status.ACTIVE
        merchant.save(update_fields=["status"])
        product = Product.objects.create(
            merchant=merchant,
            sku="KIOSK-1",
            name="Kiosk mug",
            slug="kiosk-mug",
            base_price=Decimal("40.00"),
        )
        variant = ProductVariant.objects.create(product=product, sku="KIOSK-1-A", label="One")
        StoreStock.objects.create(
            store=Store.objects.get(code=slug), variant=variant, quantity=3
        )

        public = self.client.get(f"/api/v1/products/?merchant={slug}")
        payload = public.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        self.assertEqual(rows, [])

        sample = self.client.get("/api/v1/products/")
        sample_rows = sample.json()
        sample_rows = sample_rows["results"] if isinstance(sample_rows, dict) else sample_rows
        self.assertNotIn("kiosk-mug", [row["slug"] for row in sample_rows])

        sale = self.client.post(
            "/api/v1/pos/sales/",
            data=json.dumps(
                {
                    "lines": [{"variant_id": variant.pk, "quantity": 1}],
                    "tender": "cash",
                    "idempotency_key": str(uuid.uuid4()),
                    "store_code": slug,
                }
            ),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(sale.status_code, 201, sale.content)
        self.assertEqual(sale.json()["status"], "payment_confirmed")

    def test_expired_trial_cannot_sell(self):
        self._open("shop_till")
        merchant = Merchant.objects.get(trading_name="Kiosk")
        merchant.trial_ends = timezone.now() - timezone.timedelta(days=1)
        merchant.save(update_fields=["trial_ends"])
        product = Product.objects.create(
            merchant=merchant,
            sku="LATE-1",
            name="Late mug",
            slug="late-mug",
            base_price=Decimal("10.00"),
        )
        variant = ProductVariant.objects.create(product=product, sku="LATE-1-A", label="One")
        Inventory.objects.create(variant=variant, quantity=2)
        sale = self.client.post(
            "/api/v1/pos/sales/",
            data=json.dumps(
                {
                    "lines": [{"variant_id": variant.pk, "quantity": 1}],
                    "tender": "cash",
                    "idempotency_key": str(uuid.uuid4()),
                }
            ),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(sale.status_code, 400)
        self.assertEqual(sale.json()["error"]["code"], "package_excluded")

    def test_choosing_a_package_ends_the_trial_and_keeps_the_catalogue(self):
        self._open("shop_till")
        merchant = Merchant.objects.get(trading_name="Kiosk")
        merchant.trial_ends = timezone.now() - timezone.timedelta(days=1)
        merchant.save(update_fields=["trial_ends"])
        product = Product.objects.create(
            merchant=merchant,
            sku="KEEP-1",
            name="Kept mug",
            slug="kept-mug",
            base_price=Decimal("15.00"),
        )
        variant = ProductVariant.objects.create(product=product, sku="KEEP-1-A", label="One")
        Inventory.objects.create(variant=variant, quantity=4)
        self.staff.merchant_memberships.create(merchant=merchant, role="staff")
        denied = self.client.post(
            "/api/v1/platform/package/",
            data=json.dumps({"package": "shop"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(denied.json()["error"]["code"], "permission_denied")
        guest = self.client.post(
            "/api/v1/platform/package/",
            data=json.dumps({"package": "shop"}),
            content_type="application/json",
        )
        self.assertEqual(guest.status_code, 401)

        chosen = self.client.post(
            "/api/v1/platform/package/",
            data=json.dumps({"package": "shop", "addons": ["reviews"]}),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(chosen.status_code, 200, chosen.content)
        body = chosen.json()
        self.assertEqual(body["status"], "active")
        self.assertTrue(body["shop"])
        self.assertFalse(body["pos"])
        self.assertTrue(body["prices_are_illustrative"])
        self.assertEqual(body["addons"], ["reviews"])
        self.assertTrue(Product.objects.filter(pk=product.pk, is_active=True).exists())
        sale = self.client.post(
            "/api/v1/pos/sales/",
            data=json.dumps(
                {
                    "lines": [{"variant_id": variant.pk, "quantity": 1}],
                    "tender": "cash",
                    "idempotency_key": str(uuid.uuid4()),
                }
            ),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(sale.status_code, 400)
        self.assertEqual(sale.json()["error"]["code"], "package_excluded")

        ShopAd.objects.create(title="Sample banner", body="North", is_active=True)
        ShopAd.objects.create(
            title="Kiosk banner",
            body="Own",
            is_active=True,
            merchant=merchant,
            source="self_serve",
        )
        sample = self.client.get("/api/v1/ads/?placement=shop_top")
        sample_titles = [row["title"] for row in sample.json()["results"]]
        self.assertIn("Sample banner", sample_titles)
        self.assertNotIn("Kiosk banner", sample_titles)
        own = self.client.get(f"/api/v1/ads/?placement=shop_top&merchant={merchant.slug}")
        self.assertEqual([row["title"] for row in own.json()["results"]], ["Kiosk banner"])

    def test_self_serve_ads_need_the_extra(self):
        self._open("shop")
        merchant = Merchant.objects.get(trading_name="Kiosk")
        self.staff.merchant_memberships.create(merchant=merchant, role="staff")
        ad = ShopAd.objects.create(title="Trail", body="Week", is_active=True)
        denied = self.client.patch(
            f"/api/v1/ads/staff/{ad.pk}/",
            data=json.dumps({"title": "Changed"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["error"]["code"], "package_excluded")
