"""Catalogue search falls back to a close match when the literal query misses."""
from __future__ import annotations

from decimal import Decimal

from django.test import Client, TestCase

from apps.catalogue.models import Brand, Category, Product


class CatalogueSearchTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="Northbound", slug="northbound")
        cat = Category.objects.create(name="Packs", slug="packs")
        Product.objects.create(
            sku="NB-RDG45",
            name="Ridgeline 45 Pack",
            slug="ridgeline-45",
            brand=brand,
            category=cat,
            base_price=Decimal("289.00"),
            hue=150,
        )
        self.client = Client()

    def test_typo_matches_product_name(self):
        response = self.client.get("/api/v1/products/?q=Ridgelne")
        self.assertEqual(response.status_code, 200)
        names = [row["name"] for row in response.json()["results"]]
        self.assertIn("Ridgeline 45 Pack", names)

    def test_unrelated_query_stays_empty(self):
        response = self.client.get("/api/v1/products/?q=zzzzqqqq")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_image_is_svg(self):
        product_id = Product.objects.get(sku="NB-RDG45").pk
        response = self.client.get(f"/api/v1/products/{product_id}/image/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<svg", response.content)
        listed = self.client.get("/api/v1/products/").json()["results"][0]
        self.assertIn("/image/", listed["image_url"])
