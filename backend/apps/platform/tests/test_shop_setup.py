"""Order scope, catalogue import, staff invite, a second store, and PayFast keys."""
from __future__ import annotations

import json
from decimal import Decimal

from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.catalogue.models import Product
from apps.orders.models import Order
from apps.platform.models import Merchant


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ShopSetupTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            email="owner@kiosk.test",
            username="kiosk",
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
        return {"HTTP_AUTHORIZATION": f"Bearer {issue_token_pair(user)['access']}"}

    def _open(self, addons=None, package="shop"):
        response = self.client.post(
            "/api/v1/platform/onboarding/",
            data=json.dumps(
                {
                    "trading_name": "Kiosk",
                    "package": package,
                    "privacy_accepted": True,
                    "empty_catalogue_ok": True,
                    "addons": addons or [],
                }
            ),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(response.status_code, 201, response.content)
        return Merchant.objects.get(slug=response.json()["slug"])

    def test_staff_orders_stay_on_their_merchant(self):
        merchant = self._open()
        Order.objects.create(
            reference="NB-100001",
            user=self.owner,
            merchant=merchant,
            subtotal=Decimal("10.00"),
            grand_total=Decimal("10.00"),
        )
        Order.objects.create(
            reference="NB-100002",
            user=self.owner,
            subtotal=Decimal("10.00"),
            grand_total=Decimal("10.00"),
        )
        own = self.client.get("/api/v1/orders/staff/?channel=all", **self._auth(self.owner))
        self.assertEqual(own.status_code, 200)
        self.assertEqual([row["reference"] for row in own.json()["results"]], ["NB-100001"])
        sample = self.client.get("/api/v1/orders/staff/?channel=all", **self._auth(self.staff))
        self.assertEqual([row["reference"] for row in sample.json()["results"]], ["NB-100002"])
        hidden = self.client.get("/api/v1/orders/staff/NB-100002/", **self._auth(self.owner))
        self.assertEqual(hidden.status_code, 404)

    def test_import_invite_store_and_payfast(self):
        merchant = self._open(["extra_store", "live_payfast"])
        imported = self.client.post(
            "/api/v1/platform/catalogue/",
            data=json.dumps({"sample": True}),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(imported.status_code, 201, imported.content)
        self.assertEqual(Product.objects.filter(merchant=merchant).count(), 2)
        public = self.client.get("/api/v1/products/")
        body = public.json()
        rows = body["results"] if isinstance(body, dict) else body
        self.assertFalse(any(row["sku"].startswith(merchant.slug) for row in rows))
        invited = self.client.post(
            "/api/v1/platform/staff/",
            data=json.dumps({"email": "till@kiosk.test"}),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(invited.status_code, 201, invited.content)
        person = User.objects.get(email="till@kiosk.test")
        self.assertFalse(person.is_staff)
        self.assertEqual(len(mail.outbox), 1)
        denied = self.client.post(
            "/api/v1/platform/stores/",
            data=json.dumps({"name": "Second till"}),
            content_type="application/json",
            **self._auth(person),
        )
        self.assertEqual(denied.status_code, 400)
        opened = self.client.post(
            "/api/v1/platform/stores/",
            data=json.dumps({"name": "Second till", "sells_online": False}),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(opened.status_code, 201, opened.content)
        saved = self.client.post(
            "/api/v1/platform/payfast/",
            data=json.dumps({"merchant_id": "10000100", "merchant_key": "secret-key"}),
            content_type="application/json",
            **self._auth(self.owner),
        )
        self.assertEqual(saved.status_code, 200)
        self.assertNotIn("secret-key", saved.content.decode())
        self.assertTrue(saved.json()["configured"])
        merchant.refresh_from_db()
        self.assertEqual(merchant.payfast_merchant_key, "secret-key")
