"""Push notification dry-run tests."""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.notifications.models import DeviceRegistration, NotificationLog
from apps.notifications.push import notify_order_status_push, send_push_to_user
from apps.orders.services import place_order


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PushTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="push@test.local",
            username="pusher",
            password="correct-horse-42",
            email_verified=True,
        )
        DeviceRegistration.objects.create(
            user=self.user,
            token="fcm-test-token-abc123",
            platform=DeviceRegistration.Platform.ANDROID,
            is_active=True,
        )
        brand = Brand.objects.create(name="P", slug="p-push")
        cat = Category.objects.create(name="P", slug="p-push-c")
        self.product = Product.objects.create(
            sku="PU-1",
            name="Push Pack",
            slug="push-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("55.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="PU-1-A", label="Std"
        )
        Inventory.objects.create(variant=self.variant, quantity=3)

    def test_dry_run_sends_log(self):
        logs = send_push_to_user(
            self.user,
            title="Hello",
            body="World",
            template="push_test",
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].status, NotificationLog.Status.SENT)
        self.assertEqual(logs[0].channel, NotificationLog.Channel.PUSH)

    def test_no_devices_skipped(self):
        DeviceRegistration.objects.all().delete()
        logs = send_push_to_user(
            self.user, title="X", body="Y", template="push_test"
        )
        self.assertEqual(logs[0].status, NotificationLog.Status.SKIPPED)

    def test_order_advance_emits_push(self):
        from apps.orders.services import advance_order

        cart = Cart.objects.create(user=self.user, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price_snapshot=Decimal("55.00"),
        )
        order, _, _ = place_order(
            user=self.user,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        NotificationLog.objects.filter(channel=NotificationLog.Channel.PUSH).delete()
        advance_order(order, actor=self.user)
        pushes = NotificationLog.objects.filter(channel=NotificationLog.Channel.PUSH)
        self.assertTrue(pushes.exists())
