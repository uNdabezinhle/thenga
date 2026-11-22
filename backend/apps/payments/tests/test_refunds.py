"""Staff refund tests — REKA-FR-PAY-006."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.accounts.models import Role, User, UserRole
from apps.accounts.tokens import issue_token_pair
from apps.cart.models import Cart, CartItem
from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
from apps.orders.models import Order, Payment, Refund
from apps.orders.services import place_order
from apps.payments.refunds import RefundError, issue_refund


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RefundTests(TestCase):
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

        brand = Brand.objects.create(name="R", slug="r-ref")
        cat = Category.objects.create(name="C", slug="c-ref")
        self.product = Product.objects.create(
            sku="RF-1",
            name="Refund Pack",
            slug="refund-pack",
            brand=brand,
            category=cat,
            base_price=Decimal("200.00"),
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, sku="RF-1-A", label="Std"
        )
        Inventory.objects.create(variant=self.variant, quantity=10)

    def _paid_order(self, qty=1):
        cart = Cart.objects.create(user=self.customer, is_active=True)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            variant=self.variant,
            quantity=qty,
            unit_price_snapshot=Decimal("200.00"),
        )
        order, payment, _ = place_order(
            user=self.customer,
            cart=cart,
            payment_method="cod",
            idempotency_key=str(uuid.uuid4()),
        )
        return order, payment

    def test_full_refund(self):
        order, payment = self._paid_order()
        refund = issue_refund(
            order=order, reason="Damaged", staff_user=self.staff
        )
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(refund.amount, Decimal("200.00"))
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(order.status, Order.Status.REFUNDED)

    def test_partial_then_full(self):
        order, payment = self._paid_order()
        r1 = issue_refund(
            order=order, amount=Decimal("50.00"), reason="Partial", staff_user=self.staff
        )
        payment.refresh_from_db()
        self.assertEqual(r1.amount, Decimal("50.00"))
        self.assertEqual(payment.status, Payment.Status.PARTIALLY_REFUNDED)
        order.refresh_from_db()
        self.assertNotEqual(order.status, Order.Status.REFUNDED)

        r2 = issue_refund(order=order, reason="Rest", staff_user=self.staff)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(r2.amount, Decimal("150.00"))
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(order.status, Order.Status.REFUNDED)

    def test_cannot_over_refund(self):
        order, _ = self._paid_order()
        with self.assertRaises(RefundError):
            issue_refund(
                order=order, amount=Decimal("999.00"), staff_user=self.staff
            )

    def test_idempotent_refund(self):
        order, _ = self._paid_order()
        key = str(uuid.uuid4())
        a = issue_refund(
            order=order, amount=Decimal("20.00"), idempotency_key=key, staff_user=self.staff
        )
        b = issue_refund(
            order=order, amount=Decimal("20.00"), idempotency_key=key, staff_user=self.staff
        )
        self.assertEqual(a.id, b.id)
        self.assertEqual(Refund.objects.filter(payment__order=order).count(), 1)

    def test_customer_cannot_refund(self):
        order, _ = self._paid_order()
        tokens = issue_token_pair(self.customer)
        c = Client()
        r = c.post(
            "/api/v1/payments/refunds/",
            data=json.dumps(
                {"order_reference": order.reference, "amount": "10.00"}
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertIn(r.status_code, (403, 401))

    def test_staff_api_refund(self):
        order, _ = self._paid_order()
        tokens = issue_token_pair(self.staff)
        c = Client()
        r = c.post(
            "/api/v1/payments/refunds/",
            data=json.dumps(
                {
                    "order_reference": order.reference,
                    "amount": "75.00",
                    "reason": "Customer request",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["amount"], "75.00")
        self.assertEqual(r.json()["payment_status"], "partially_refunded")

    def test_staff_can_list_all_orders(self):
        self._paid_order()
        tokens = issue_token_pair(self.staff)
        c = Client()
        r = c.get(
            "/api/v1/orders/staff/",
            HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
        )
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(len(r.json()["results"]), 1)
