"""Counter sales share stock, loyalty, and payment with the shop."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Inventory, Product, ProductVariant
from apps.orders.models import Order, Shipment
from apps.orders.services import place_order
from apps.payments.services import simulate_sandbox_success
from apps.pos.models import Store, StoreCatalogItem, StoreStock
from apps.promotions.models import Bundle, BundleItem, Voucher
from apps.promotions.specials import loyalty_account


class PosSaleTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email="staff@northbound.test",
            username="staff",
            password="staff-ops-42",
            email_verified=True,
            is_staff=True,
        )
        self.customer = User.objects.create_user(
            email="jordan@northbound.test",
            username="jordan",
            password="correct-horse-42",
            email_verified=True,
        )
        self.other = User.objects.create_user(
            email="other@northbound.test",
            username="other",
            password="correct-horse-42",
            email_verified=True,
        )
        self.product = Product.objects.create(
            sku="TILL-1",
            name="Trail mug",
            slug="trail-mug",
            base_price=Decimal("100.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="TILL-1-A",
            label="Moss",
            barcode="6001234567890",
        )
        self.inv = Inventory.objects.create(variant=self.variant, quantity=5)
        self.side = Product.objects.create(
            sku="TILL-2",
            name="Trail cap",
            slug="trail-cap",
            base_price=Decimal("40.00"),
        )
        self.side_variant = ProductVariant.objects.create(
            product=self.side, sku="TILL-2-A", label="One"
        )
        self.side_inv = Inventory.objects.create(variant=self.side_variant, quantity=5)
        self.client = Client()

    def _auth(self, user):
        tokens = issue_token_pair(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

    def _sale(self, user, **extra):
        body = {
            "lines": [{"variant_id": self.variant.pk, "quantity": 1}],
            "tender": "cash",
            "idempotency_key": str(uuid.uuid4()),
        }
        body.update(extra)
        return self.client.post(
            "/api/v1/pos/sales/",
            data=json.dumps(body),
            content_type="application/json",
            **self._auth(user),
        )

    def test_cash_sale_is_paid_without_a_shipment(self):
        response = self._sale(self.staff)
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["status"], Order.Status.PAYMENT_CONFIRMED)
        self.assertTrue(body["drawer_kick"])
        self.assertEqual(body["drawer_pulse"], "1B700019FA")
        self.assertFalse(body["redirect_url"])
        order = Order.objects.get(reference=body["reference"])
        self.assertEqual(order.channel, Order.Channel.POS)
        self.assertEqual(order.shipments.count(), 0)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 4)
        self.assertEqual(self.inv.reserved_quantity, 0)
        receipt = self.client.get(
            f"/api/v1/orders/{order.reference}/invoice/",
            **self._auth(self.staff),
        )
        self.assertEqual(receipt.status_code, 200)
        self.assertIn(b"Counter sale", receipt.content)

    def test_same_key_does_not_sell_twice(self):
        key = str(uuid.uuid4())
        first = self._sale(self.staff, idempotency_key=key)
        second = self._sale(self.staff, idempotency_key=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["replayed"])
        self.assertEqual(first.json()["reference"], second.json()["reference"])
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 4)

    def test_card_tender_confirms_without_a_hosted_page(self):
        response = self._sale(self.staff, tender="card")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["status"], Order.Status.PAYMENT_CONFIRMED)
        self.assertFalse(response.json()["drawer_kick"])
        self.assertFalse(response.json()["redirect_url"])
        self.assertEqual(Shipment.objects.count(), 0)

    def test_online_order_still_dispatches_and_pos_does_not(self):
        cart = Cart.objects.create(user=self.customer, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("100.00"),
        )
        online, _, _ = place_order(
            user=self.customer,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        self.assertTrue(online.shipments.filter(status=Shipment.Status.PENDING).exists())
        pos = self._sale(self.staff)
        reference = pos.json()["reference"]
        listing = self.client.get("/api/v1/orders/staff/", **self._auth(self.staff))
        refs = [row["reference"] for row in listing.json()["results"]]
        self.assertIn(online.reference, refs)
        self.assertNotIn(reference, refs)
        till = self.client.get(
            "/api/v1/orders/staff/?channel=pos", **self._auth(self.staff)
        )
        self.assertEqual(
            [row["reference"] for row in till.json()["results"]],
            [reference],
        )
        blocked = self.client.post(
            f"/api/v1/orders/staff/{reference}/dispatch/",
            **self._auth(self.staff),
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["error"]["code"], "pos_not_dispatchable")

    def test_walk_in_earns_nothing_and_a_named_customer_earns_points(self):
        walk = self._sale(self.staff)
        order = Order.objects.get(reference=walk.json()["reference"])
        self.assertEqual(order.user.email, "counter@northbound.test")
        self.assertEqual(order.loyalty_points, 0)
        self.assertTrue(order.specials_awarded)
        named = self._sale(self.staff, customer_email="jordan@northbound.test")
        paid = Order.objects.get(reference=named.json()["reference"])
        self.assertEqual(paid.user, self.customer)
        self.assertEqual(paid.loyalty_points, 10)
        self.assertEqual(loyalty_account(self.customer).points, 10)

    def test_voucher_is_personal(self):
        Voucher.objects.create(
            code="TRAIL50",
            owner=self.customer,
            amount=Decimal("10.00"),
            remaining_amount=Decimal("10.00"),
        )
        foreign = Voucher.objects.create(
            code="OTHER10",
            owner=self.other,
            amount=Decimal("10.00"),
            remaining_amount=Decimal("10.00"),
        )
        bad = self._sale(
            self.staff,
            customer_email="jordan@northbound.test",
            discount_code=foreign.code,
        )
        self.assertEqual(bad.status_code, 400)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 5)
        good = self._sale(
            self.staff,
            customer_email="jordan@northbound.test",
            discount_code="TRAIL50",
        )
        self.assertEqual(good.status_code, 201, good.content)
        self.assertEqual(good.json()["grand_total"], "90.00")
        voucher = Voucher.objects.get(code="TRAIL50")
        self.assertEqual(voucher.remaining_amount, Decimal("0"))
        self.assertEqual(voucher.redeemed_order.reference, good.json()["reference"])
        walk = self._sale(self.staff, discount_code="TRAIL50")
        self.assertEqual(walk.status_code, 400)

    def test_customer_cannot_open_the_till(self):
        denied = self._sale(self.customer)
        self.assertEqual(denied.status_code, 403)
        anonymous = self.client.post(
            "/api/v1/pos/sales/",
            data=json.dumps({"lines": [], "idempotency_key": "x"}),
            content_type="application/json",
        )
        self.assertEqual(anonymous.status_code, 401)

    def test_payfast_waits_and_a_separate_store_keeps_its_own_stock(self):
        waiting = self._sale(self.staff, tender="payfast")
        self.assertEqual(waiting.status_code, 201, waiting.content)
        self.assertTrue(waiting.json()["awaiting_payment"])
        self.assertTrue(waiting.json()["redirect_url"])
        self.assertFalse(waiting.json()["receipt_url"])
        order = Order.objects.get(reference=waiting.json()["reference"])
        self.assertEqual(order.shipments.count(), 0)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 5)
        self.assertEqual(self.inv.reserved_quantity, 1)
        simulate_sandbox_success(order.payments.get())
        order.refresh_from_db()
        self.inv.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAYMENT_CONFIRMED)
        self.assertEqual(order.shipments.count(), 0)
        self.assertEqual(self.inv.quantity, 4)
        self.assertEqual(self.inv.reserved_quantity, 0)

        trail = Store.objects.get(code="trail")
        StoreStock.objects.create(store=trail, variant=self.variant, quantity=3)
        response = self._sale(self.staff, store_code="trail")
        self.assertEqual(response.status_code, 201, response.content)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 4)
        stock = StoreStock.objects.get(store=trail, variant=self.variant)
        self.assertEqual(stock.quantity, 2)

    def test_bundle_is_one_key_and_blocks_a_code(self):
        bundle = Bundle.objects.create(title="Mug kit", price=Decimal("120.00"))
        BundleItem.objects.create(
            bundle=bundle, product=self.product, variant=self.variant, quantity=1
        )
        BundleItem.objects.create(
            bundle=bundle, product=self.side, variant=self.side_variant, quantity=1
        )
        blocked = self._sale(
            self.staff,
            lines=[{"bundle_id": bundle.pk, "quantity": 1}],
            discount_code="TRAIL50",
        )
        self.assertEqual(blocked.status_code, 409)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 5)
        sold = self._sale(self.staff, lines=[{"bundle_id": bundle.pk, "quantity": 1}])
        self.assertEqual(sold.status_code, 201, sold.content)
        self.assertEqual(sold.json()["grand_total"], "120.00")
        self.inv.refresh_from_db()
        self.side_inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 4)
        self.assertEqual(self.side_inv.quantity, 4)

    def test_scan_catalogue_and_drawer(self):
        till_only = Product.objects.create(
            sku="TILL-ONLY",
            name="Counter bell",
            slug="counter-bell",
            base_price=Decimal("15.00"),
            sale_channel=Product.SaleChannel.POS,
        )
        bell = ProductVariant.objects.create(
            product=till_only, sku="TILL-ONLY-A", label="Brass", barcode="BELL1"
        )
        Inventory.objects.create(variant=bell, quantity=2)
        online_only = Product.objects.create(
            sku="WEB-ONLY",
            name="Web poster",
            slug="web-poster",
            base_price=Decimal("30.00"),
            sale_channel=Product.SaleChannel.ONLINE,
        )
        poster = ProductVariant.objects.create(
            product=online_only, sku="WEB-ONLY-A", label="A3"
        )
        Inventory.objects.create(variant=poster, quantity=2)

        public = self.client.get("/api/v1/products/")
        payload = public.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        slugs = [row["slug"] for row in rows]
        self.assertIn("trail-mug", slugs)
        self.assertNotIn("counter-bell", slugs)

        catalog = self.client.get(
            "/api/v1/pos/catalog/?q=bell", **self._auth(self.staff)
        )
        self.assertEqual(catalog.status_code, 200, catalog.content)
        self.assertEqual(catalog.json()["variants"][0]["sku"], "TILL-ONLY-A")
        hidden = self.client.get(
            "/api/v1/pos/catalog/?q=poster", **self._auth(self.staff)
        )
        self.assertEqual(hidden.json()["variants"], [])

        scan = self.client.post(
            "/api/v1/pos/scan/",
            data=json.dumps({"code": "6001234567890"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(scan.status_code, 200, scan.content)
        self.assertEqual(scan.json()["variant_id"], self.variant.pk)

        trail = Store.objects.get(code="trail")
        StoreCatalogItem.objects.create(store=trail, variant=bell, price_override=Decimal("9.00"))
        StoreStock.objects.create(store=trail, variant=bell, quantity=2)
        limited = self.client.get(
            "/api/v1/pos/catalog/?store=trail", **self._auth(self.staff)
        )
        self.assertEqual(
            [row["sku"] for row in limited.json()["variants"]],
            ["TILL-ONLY-A"],
        )
        self.assertEqual(limited.json()["variants"][0]["unit_price"], "9.00")

        opened = self.client.post(
            "/api/v1/pos/drawer/",
            data=json.dumps({"action": "open", "opening_float": "20.00"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(opened.status_code, 200, opened.content)
        self.assertEqual(opened.json()["opening_float"], "20.00")
        self._sale(self.staff)
        state = self.client.get("/api/v1/pos/drawer/", **self._auth(self.staff))
        self.assertEqual(state.json()["expected"], "120.00")
        closed = self.client.post(
            "/api/v1/pos/drawer/",
            data=json.dumps({"action": "close", "closing_count": "120.00"}),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(closed.json()["expected"], "120.00")
        self.assertEqual(closed.json()["closing_count"], "120.00")

    def test_sync_keeps_each_sale_in_its_own_transaction(self):
        good = str(uuid.uuid4())
        bad = str(uuid.uuid4())
        response = self.client.post(
            "/api/v1/pos/sales/sync/",
            data=json.dumps(
                {
                    "sales": [
                        {
                            "lines": [{"variant_id": self.variant.pk, "quantity": 1}],
                            "tender": "cash",
                            "idempotency_key": good,
                        },
                        {
                            "lines": [{"variant_id": self.variant.pk, "quantity": 99}],
                            "tender": "cash",
                            "idempotency_key": bad,
                        },
                    ]
                }
            ),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertEqual(response.status_code, 200, response.content)
        results = response.json()["results"]
        self.assertTrue(results[0]["ok"])
        self.assertFalse(results[1]["ok"])
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 4)
        again = self.client.post(
            "/api/v1/pos/sales/sync/",
            data=json.dumps(
                {
                    "sales": [
                        {
                            "lines": [{"variant_id": self.variant.pk, "quantity": 1}],
                            "tender": "cash",
                            "idempotency_key": good,
                        }
                    ]
                }
            ),
            content_type="application/json",
            **self._auth(self.staff),
        )
        self.assertTrue(again.json()["results"][0]["replayed"])
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 4)
