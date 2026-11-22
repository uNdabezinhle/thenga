from decimal import Decimal

from django.test import SimpleTestCase

from apps.pricing.services import Line, apply_discounts, compute_totals, q


class PricingServiceTests(SimpleTestCase):
    """Mandatory money tests — docs/05-test-strategy.md §4.1."""

    def test_percentage_discount_rounds_half_up(self):
        # 20% of R33.33 → R6.67
        totals = compute_totals(
            lines=[Line(unit_price=Decimal("33.33"), quantity=1)],
            discounts=[("percentage", Decimal("20"))],
        )
        self.assertEqual(totals.discount_total, Decimal("6.67"))

    def test_percentage_quantised(self):
        totals = compute_totals(
            lines=[Line(unit_price=Decimal("289.00"), quantity=1)],
            discounts=[("percentage", Decimal("20"))],
        )
        self.assertEqual(totals.discount_total, Decimal("57.80"))
        self.assertEqual(totals.grand_total, Decimal("231.20"))

    def test_total_never_negative(self):
        totals = compute_totals(
            lines=[Line(unit_price=Decimal("10.00"), quantity=1)],
            discounts=[("fixed", Decimal("999.00"))],
            shipping=Decimal("0"),
        )
        self.assertEqual(totals.grand_total, Decimal("0.00"))
        self.assertEqual(totals.discount_total, Decimal("10.00"))

    def test_shipping_excluded_from_percentage_discount(self):
        totals = compute_totals(
            lines=[Line(unit_price=Decimal("100.00"), quantity=1)],
            discounts=[("percentage", Decimal("10"))],
            shipping=Decimal("25.00"),
        )
        self.assertEqual(totals.discount_total, Decimal("10.00"))
        self.assertEqual(totals.shipping_total, Decimal("25.00"))
        self.assertEqual(totals.grand_total, Decimal("115.00"))

    def test_percentage_discount_capped_at_100(self):
        totals = compute_totals(
            lines=[Line(unit_price=Decimal("50.00"), quantity=1)],
            discounts=[("percentage", Decimal("150"))],
        )
        self.assertEqual(totals.discount_total, Decimal("50.00"))
        self.assertEqual(totals.grand_total, Decimal("0.00"))

    def test_sequential_discounts_never_exceed_subtotal(self):
        applied = apply_discounts(
            Decimal("100.00"),
            [("percentage", Decimal("60")), ("percentage", Decimal("60"))],
        )
        self.assertEqual(applied, Decimal("84.00"))
        self.assertLessEqual(applied, Decimal("100.00"))

    def test_line_totals_sum_to_subtotal(self):
        lines = [
            Line(unit_price=Decimal("10.00"), quantity=2),
            Line(unit_price=Decimal("7.50"), quantity=3),
        ]
        totals = compute_totals(lines=lines)
        self.assertEqual(totals.subtotal, Decimal("42.50"))

    def test_q_rounds_half_up(self):
        self.assertEqual(q("1.005"), Decimal("1.01"))

    def test_money_as_string_in_dict(self):
        totals = compute_totals(
            lines=[Line(unit_price=Decimal("12.50"), quantity=2)],
            shipping=Decimal("5"),
        )
        d = totals.as_dict()
        self.assertIsInstance(d["subtotal"], str)
        self.assertEqual(d["subtotal"], "25.00")
        self.assertEqual(d["grand_total"], "30.00")
