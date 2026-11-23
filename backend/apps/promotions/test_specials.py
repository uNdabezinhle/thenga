"""Flash prices, bundles, loyalty, referrals, and customer reviews."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import CartItem, Coupon
from apps.catalogue.models import (
    Brand,
    Category,
    FlashPrice,
    Inventory,
    Product,
    ProductVariant,
    Review,
)
from apps.core.exceptions import BundleLocked
from apps.orders.services import cancel_order, place_order
from apps.promotions.models import Bundle, BundleItem, LoyaltyAccount, Voucher
from apps.promotions.specials import attach_referrer, ensure_referral


class SpecialFeatureTests(TestCase):
    def setUp(self):
        self.jordan = User.objects.create_user(
            email="jordan@northbound.test",
            username="jordan",
            password="correct-horse-42",
            email_verified=True,
        )
        self.friend = User.objects.create_user(
            email="friend@northbound.test",
            username="friend",
            password="correct-horse-42",
            email_verified=True,
        )
        brand = Brand.objects.create(name="Northbound", slug="nb-special")
        cat = Category.objects.create(name="Packs", slug="packs-special")
        self.pack = Product.objects.create(
            sku="SP-PACK",
            name="Special Pack",
            slug="special-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("100.00"),
        )
        self.shell = Product.objects.create(
            sku="SP-SHELL",
            name="Special Shell",
            slug="special-shell",
            brand=brand,
            category=cat,
            base_price=Decimal("80.00"),
        )
        self.pack_variant = ProductVariant.objects.create(
            product=self.pack, sku="SP-PACK-A", label="One"
        )
        self.shell_variant = ProductVariant.objects.create(
            product=self.shell, sku="SP-SHELL-A", label="One"
        )
        Inventory.objects.create(variant=self.pack_variant, quantity=5)
        Inventory.objects.create(variant=self.shell_variant, quantity=5)
        Coupon.objects.create(
            code="DISCOUNT20",
            discount_type="percentage",
            amount=Decimal("20.00"),
            is_active=True,
        )
        self.client = Client()

    def _auth(self, user):
        tokens = issue_token_pair(user)
        return {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}

    def _add(self, user, product, variant):
        return self.client.post(
            "/api/v1/cart/cart/add_item/",
            data=json.dumps(
                {"product": product.id, "variant": variant.id, "quantity": 1}
            ),
            content_type="application/json",
            **self._auth(user),
        )

    def _pay(self, user):
        from apps.cart.models import Cart

        cart = Cart.objects.get(user=user, is_active=True)
        return place_order(
            user=user,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )

    def test_live_flash_is_snapshotted_and_an_ended_flash_is_not(self):
        FlashPrice.objects.create(
            product=self.pack, sale_price=Decimal("70.00"), is_active=True
        )
        added = self._add(self.jordan, self.pack, self.pack_variant)
        self.assertEqual(added.status_code, 200, added.content)
        line = CartItem.objects.get(cart__user=self.jordan)
        self.assertEqual(line.unit_price_snapshot, Decimal("70.00"))
        listed = self.client.get("/api/v1/products/")
        payload = listed.json()
        rows = payload["results"] if isinstance(payload, dict) else payload
        row = next(item for item in rows if item["sku"] == "SP-PACK")
        self.assertEqual(row["price"], "70.00")
        self.assertEqual(row["compare_at"], "100.00")

        line.unit_price_snapshot = Decimal("100.00")
        line.save(update_fields=["unit_price_snapshot"])
        FlashPrice.objects.filter(product=self.pack).update(sale_price=Decimal("60.00"))
        line.refresh_from_db()
        self.assertEqual(line.unit_price_snapshot, Decimal("100.00"))

        CartItem.objects.filter(cart__user=self.friend).delete()
        FlashPrice.objects.filter(product=self.pack).update(
            ends_at=timezone.now() - timedelta(hours=1)
        )
        ended = self._add(self.friend, self.pack, self.pack_variant)
        self.assertEqual(ended.status_code, 200, ended.content)
        friend_line = CartItem.objects.get(cart__user=self.friend)
        self.assertEqual(friend_line.unit_price_snapshot, Decimal("100.00"))

    def test_bundle_lines_sum_to_the_price_and_block_a_second_deal(self):
        bundle = Bundle.objects.create(title="Weekend kit", price=Decimal("150.00"))
        BundleItem.objects.create(
            bundle=bundle, product=self.pack, variant=self.pack_variant, quantity=1
        )
        BundleItem.objects.create(
            bundle=bundle, product=self.shell, variant=self.shell_variant, quantity=1
        )
        other = Bundle.objects.create(title="Second kit", price=Decimal("90.00"))
        BundleItem.objects.create(
            bundle=other, product=self.pack, variant=self.pack_variant, quantity=1
        )
        added = self.client.post(
            f"/api/v1/promotions/bundles/{bundle.id}/add/",
            data="{}",
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(added.status_code, 200, added.content)
        lines = list(CartItem.objects.filter(cart__user=self.jordan))
        self.assertEqual(len(lines), 2)
        total = sum(line.unit_price_snapshot * line.quantity for line in lines)
        self.assertEqual(total, Decimal("150.00"))
        again = self.client.post(
            f"/api/v1/promotions/bundles/{other.id}/add/",
            data="{}",
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(again.status_code, 409, again.content)
        coded = self.client.post(
            "/api/v1/cart/cart/apply_discount/",
            data='{"code":"DISCOUNT20"}',
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(coded.status_code, 409, coded.content)
        removed = self.client.delete(
            f"/api/v1/cart/cart/items/{lines[0].id}/remove/",
            **self._auth(self.jordan),
        )
        self.assertEqual(removed.status_code, 200, removed.content)
        self.assertEqual(CartItem.objects.filter(cart__user=self.jordan).count(), 0)

    def test_short_stock_adds_nothing(self):
        Inventory.objects.filter(variant=self.shell_variant).update(quantity=0)
        bundle = Bundle.objects.create(title="Dry kit", price=Decimal("50.00"))
        BundleItem.objects.create(
            bundle=bundle, product=self.pack, variant=self.pack_variant, quantity=1
        )
        BundleItem.objects.create(
            bundle=bundle, product=self.shell, variant=self.shell_variant, quantity=1
        )
        added = self.client.post(
            f"/api/v1/promotions/bundles/{bundle.id}/add/",
            data="{}",
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(added.status_code, 409, added.content)
        self.assertEqual(CartItem.objects.filter(cart__user=self.jordan).count(), 0)

    def test_paid_order_awards_points_and_cancel_removes_them(self):
        added = self._add(self.jordan, self.pack, self.pack_variant)
        self.assertEqual(added.status_code, 200, added.content)
        order, _, _ = self._pay(self.jordan)
        account = LoyaltyAccount.objects.get(user=self.jordan)
        self.assertEqual(account.points, 10)
        order.refresh_from_db()
        self.assertEqual(order.loyalty_points, 10)
        cancel_order(order, actor=self.jordan)
        account.refresh_from_db()
        self.assertEqual(account.points, 0)

    def test_redeeming_100_points_creates_a_ten_rand_voucher(self):
        LoyaltyAccount.objects.create(user=self.jordan, points=120)
        short = LoyaltyAccount.objects.create(user=self.friend, points=40)
        denied = self.client.post(
            "/api/v1/promotions/loyalty/redeem/",
            data="{}",
            content_type="application/json",
            **self._auth(self.friend),
        )
        self.assertEqual(denied.status_code, 409, denied.content)
        short.refresh_from_db()
        self.assertEqual(short.points, 40)
        redeemed = self.client.post(
            "/api/v1/promotions/loyalty/redeem/",
            data="{}",
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(redeemed.status_code, 200, redeemed.content)
        body = redeemed.json()
        self.assertEqual(body["points"], 20)
        self.assertEqual(body["amount"], "10.00")
        voucher = Voucher.objects.get(code=body["voucher_code"])
        self.assertEqual(voucher.owner, self.jordan)
        self.assertEqual(voucher.amount, Decimal("10.00"))
        self.assertTrue(voucher.code.startswith("PTS"))

    def test_self_referral_is_rejected_and_a_friend_is_rewarded_once(self):
        code = ensure_referral(self.jordan).code
        with self.assertRaises(BundleLocked):
            attach_referrer(self.jordan, code)
        denied = self.client.post(
            "/api/v1/promotions/referrals/",
            data=json.dumps({"code": code}),
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(denied.status_code, 409, denied.content)
        attached = self.client.post(
            "/api/v1/promotions/referrals/",
            data=json.dumps({"code": code}),
            content_type="application/json",
            **self._auth(self.friend),
        )
        self.assertEqual(attached.status_code, 200, attached.content)
        self._add(self.friend, self.pack, self.pack_variant)
        order, _, _ = self._pay(self.friend)
        referrer = LoyaltyAccount.objects.get(user=self.jordan)
        self.assertEqual(referrer.points, 50)
        voucher = Voucher.objects.get(owner=self.friend, amount=Decimal("20.00"))
        self.assertEqual(voucher.remaining_amount, Decimal("20.00"))
        profile = self.friend.referral
        self.assertTrue(profile.settled)
        cancel_order(order, actor=self.friend)
        referrer.refresh_from_db()
        self.assertEqual(referrer.points, 0)
        self.assertFalse(Voucher.objects.filter(pk=voucher.pk).exists())
        profile.refresh_from_db()
        self.assertFalse(profile.settled)

    def test_customer_review_replaces_the_previous_one(self):
        first = self.client.post(
            f"/api/v1/products/{self.pack.id}/reviews/",
            data=json.dumps({"rating": 5, "body": "Held up on the coast."}),
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(first.status_code, 200, first.content)
        guest = self.client.get(f"/api/v1/products/{self.pack.id}/")
        self.assertIn("Held up on the coast.", guest.content.decode())
        second = self.client.post(
            f"/api/v1/products/{self.pack.id}/reviews/",
            data=json.dumps({"rating": 4, "body": "Lid pocket is small."}),
            content_type="application/json",
            **self._auth(self.jordan),
        )
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(Review.objects.filter(product=self.pack, user=self.jordan).count(), 1)
        review = Review.objects.get(product=self.pack, user=self.jordan)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.body, "Lid pocket is small.")
        self.assertTrue(review.is_approved)
