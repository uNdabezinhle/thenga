"""Seed Northbound catalogue, demo user, and DISCOUNT20 coupon."""
from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import MFADevice, Role, User, UserProfile, UserRole
from apps.cart.models import Coupon
from apps.catalogue.models import (
    Brand,
    Category,
    Inventory,
    Product,
    ProductAttribute,
    ProductVariant,
    Review,
)


CATALOGUE = [
    {
        "sku": "NB-RDG45",
        "name": "Ridgeline 45 Pack",
        "brand": "Northbound",
        "cat": "packs",
        "price": "289.00",
        "hue": 150,
        "blurb": "Forty-five litres, one hipbelt that actually transfers load, and a lid that comes off to become a summit pack.",
        "specs": [
            ("Volume", "45 L"),
            ("Weight", "1.42 kg"),
            ("Fabric", "210D ripstop nylon"),
            ("Frame", "Alloy perimeter"),
        ],
        "variants": [
            ("45L / Moss", 6),
            ("45L / Basalt", 0),
            ("55L / Moss", 3),
        ],
        "reviews": [
            ("Marta K.", 5, "Carried it for eleven days on the coast trail. Hipbelt never once needed readjusting."),
            ("Dev A.", 4, "Excellent build. Docked one star because the lid pocket is smaller than it photographs."),
            ("Ronan T.", 5, "Third season on mine. Still no wear at the stress points."),
        ],
    },
    {
        "sku": "NB-STRM",
        "name": "Stormline 3L Shell",
        "brand": "Northbound",
        "cat": "shells",
        "price": "410.00",
        "hue": 196,
        "blurb": "A three-layer hardshell cut for movement. Pit zips, a helmet-compatible hood, and taped seams throughout.",
        "specs": [
            ("Layers", "3L membrane"),
            ("Weight", "385 g"),
            ("Waterproof", "20,000 mm"),
            ("Seams", "Fully taped"),
        ],
        "variants": [
            ("S / Slate", 4),
            ("M / Slate", 9),
            ("M / Ember", 2),
            ("L / Slate", 0),
        ],
        "reviews": [],
    },
    {
        "sku": "FL-QLT20",
        "name": "Fell Quilt 20",
        "brand": "Fell",
        "cat": "sleep",
        "price": "365.00",
        "hue": 38,
        "blurb": "850-fill down in a quilt that pairs to your pad, so you stop carrying insulation you only ever compress.",
        "specs": [
            ("Rating", "-7 °C"),
            ("Fill", "850 FP down"),
            ("Weight", "620 g"),
            ("Packed", "8 L"),
        ],
        "variants": [("Regular", 7), ("Long", 1)],
        "reviews": [],
    },
    {
        "sku": "KC-JETB",
        "name": "Kettle Jetbox Stove",
        "brand": "Kettle & Coil",
        "cat": "tools",
        "price": "129.00",
        "hue": 12,
        "blurb": "Boils half a litre in ninety seconds and nests inside its own pot. The regulator holds output in the cold.",
        "specs": [
            ("Boil time", "90 s / 0.5 L"),
            ("Weight", "345 g"),
            ("Fuel", "Iso-butane"),
            ("Output", "7,700 BTU"),
        ],
        "variants": [("Stove only", 12), ("Stove + pot set", 5)],
        "reviews": [],
    },
    {
        "sku": "AU-TRL30",
        "name": "Auran Trail 30",
        "brand": "Auran",
        "cat": "packs",
        "price": "174.00",
        "hue": 270,
        "blurb": "A day pack that carries like a bigger one. Vented back panel, two litres of hipbelt storage, rolltop closure.",
        "specs": [
            ("Volume", "30 L"),
            ("Weight", "790 g"),
            ("Fabric", "Recycled 100D"),
            ("Closure", "Rolltop"),
        ],
        "variants": [("30L / Chalk", 8), ("30L / Ink", 4)],
        "reviews": [],
    },
    {
        "sku": "NB-BSLY",
        "name": "Basecamp Merino Layer",
        "brand": "Northbound",
        "cat": "shells",
        "price": "98.00",
        "hue": 330,
        "blurb": "170gsm merino with flatlock seams and a longer tail. The one layer you can wear four days running.",
        "specs": [
            ("Weight", "170 gsm"),
            ("Fibre", "Merino / nylon"),
            ("Seams", "Flatlock"),
            ("Fit", "Regular"),
        ],
        "variants": [("S / Fog", 3), ("M / Fog", 11), ("L / Fog", 6)],
        "reviews": [],
    },
    {
        "sku": "FL-PADX",
        "name": "Fell Insulated Pad",
        "brand": "Fell",
        "cat": "sleep",
        "price": "212.00",
        "hue": 172,
        "blurb": "R-value 5.4 in under half a kilo, with a valve that inflates in fifteen breaths and deflates in one pull.",
        "specs": [
            ("R-value", "5.4"),
            ("Weight", "455 g"),
            ("Thickness", "7.6 cm"),
            ("Packed", "2.1 L"),
        ],
        "variants": [("Regular", 9), ("Wide", 2)],
        "reviews": [],
    },
    {
        "sku": "KC-HDLM",
        "name": "Coil Headlamp 600",
        "brand": "Kettle & Coil",
        "cat": "tools",
        "price": "76.00",
        "hue": 56,
        "blurb": "Six hundred lumens with a red night mode that stays selected between sessions. Charges over USB-C.",
        "specs": [
            ("Output", "600 lm"),
            ("Runtime", "9 h high"),
            ("Weight", "88 g"),
            ("Charging", "USB-C"),
        ],
        "variants": [("Standard", 15), ("Rechargeable pack", 6)],
        "reviews": [],
    },
    {
        "sku": "NB-CUSTOM",
        "name": "Custom Embroidered Cap",
        "brand": "Northbound",
        "cat": "tools",
        "price": "45.00",
        "hue": 90,
        "blurb": "Made to order with your trail name. Excluded from the statutory 7-day cooling-off right (ECTA s42(2) custom goods).",
        "specs": [
            ("Fit", "One size"),
            ("Lead time", "10 days"),
            ("Cooling-off", "Excluded (custom)"),
        ],
        "variants": [("Charcoal", 20), ("Moss", 20)],
        "reviews": [],
        "cooling_off_excluded": True,
    },
]


class Command(BaseCommand):
    help = "Seed Northbound outdoor gear catalogue and demo accounts"

    @transaction.atomic
    def handle(self, *args, **options):
        # Roles
        customer, _ = Role.objects.get_or_create(
            name="Customer", defaults={"description": "Store customer"}
        )
        staff, _ = Role.objects.get_or_create(
            name="Staff", defaults={"description": "Store operations"}
        )
        admin_role, _ = Role.objects.get_or_create(
            name="Administrator", defaults={"description": "Full control"}
        )

        # Categories
        cats = {}
        for i, (slug, name) in enumerate(
            [
                ("packs", "Packs"),
                ("shells", "Shells"),
                ("sleep", "Sleep"),
                ("tools", "Tools"),
            ]
        ):
            cats[slug], _ = Category.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "sort_order": i, "is_active": True},
            )

        brands = {}
        for name in ("Northbound", "Fell", "Kettle & Coil", "Auran"):
            brands[name], _ = Brand.objects.update_or_create(
                slug=slugify(name),
                defaults={"name": name, "is_active": True},
            )

        for row in CATALOGUE:
            product, _ = Product.objects.update_or_create(
                sku=row["sku"],
                defaults={
                    "name": row["name"],
                    "slug": slugify(row["name"]),
                    "description": row["blurb"],
                    "brand": brands[row["brand"]],
                    "category": cats[row["cat"]],
                    "base_price": Decimal(row["price"]),
                    "currency": "ZAR",
                    "is_active": True,
                    "hue": row["hue"],
                    "cooling_off_excluded": bool(row.get("cooling_off_excluded", False)),
                },
            )
            product.attributes.all().delete()
            for key, value in row["specs"]:
                ProductAttribute.objects.create(product=product, key=key, value=value)

            # Upsert variants — never wipe rows that order history may PROTECT
            seen_labels = set()
            for label, stock in row["variants"]:
                seen_labels.add(label)
                sku = f"{row['sku']}-{slugify(label)[:20].upper()}"
                variant, _ = ProductVariant.objects.update_or_create(
                    product=product,
                    label=label,
                    defaults={"sku": sku, "is_active": True},
                )
                Inventory.objects.update_or_create(
                    variant=variant,
                    defaults={
                        "quantity": stock,
                        "reserved_quantity": 0,
                        "reorder_level": 3,
                    },
                )
            product.variants.exclude(label__in=seen_labels).update(is_active=False)

            product.reviews.all().delete()
            for who, stars, txt in row["reviews"]:
                Review.objects.create(
                    product=product,
                    rating=stars,
                    body=txt,
                    author_display=who,
                    is_approved=True,
                )

        Coupon.objects.update_or_create(
            code="DISCOUNT20",
            defaults={
                "discount_type": "percentage",
                "amount": Decimal("20.00"),
                "is_active": True,
            },
        )

        # Demo customer
        user, created = User.objects.get_or_create(
            email="jordan@northbound.test",
            defaults={
                "username": "jordan.m",
                "email_verified": True,
            },
        )
        if created or not user.has_usable_password():
            user.set_password("correct-horse-42")
            user.email_verified = True
            user.save()
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "first_name": "Jordan",
                "last_name": "Mabaso",
                "address": "14 Harbour Lane, Cape Town 8001",
            },
        )
        UserRole.objects.get_or_create(user=user, role=customer)
        # Enroll MFA so login exercises pre-auth path
        if not MFADevice.objects.filter(user=user).exists():
            import pyotp

            MFADevice.objects.create(
                user=user,
                device_type=MFADevice.DeviceType.AUTHENTICATOR,
                secret=pyotp.random_base32(),
                identifier=user.email,
                is_active=True,
            )

        # Superuser for admin
        if not User.objects.filter(email="admin@northbound.test").exists():
            admin = User.objects.create_superuser(
                email="admin@northbound.test",
                username="admin",
                password="admin-change-me",
            )
            UserRole.objects.get_or_create(user=admin, role=admin_role)
            UserProfile.objects.update_or_create(
                user=admin,
                defaults={"first_name": "Admin", "last_name": "User"},
            )

        # Staff operator (refunds, fulfilment) — no superuser
        staff_user, staff_created = User.objects.get_or_create(
            email="staff@northbound.test",
            defaults={
                "username": "ops.staff",
                "email_verified": True,
                "is_staff": True,
            },
        )
        if staff_created or not staff_user.has_usable_password():
            staff_user.set_password("staff-ops-42")
            staff_user.email_verified = True
            staff_user.is_staff = True
            staff_user.save()
        UserRole.objects.get_or_create(user=staff_user, role=staff)
        UserProfile.objects.update_or_create(
            user=staff_user,
            defaults={"first_name": "Ops", "last_name": "Staff"},
        )
        # Module permissions for staff on orders/payments
        from apps.accounts.models import Module, Permission

        for module in (Module.ORDERS, Module.PAYMENTS):
            Permission.objects.update_or_create(
                role=staff,
                module=module,
                defaults={
                    "can_create": True,
                    "can_read": True,
                    "can_update": True,
                    "can_delete": False,
                },
            )

        self.stdout.write(self.style.SUCCESS("Northbound seed complete."))
        self.stdout.write("  Customer: jordan@northbound.test / correct-horse-42 (MFA enrolled)")
        self.stdout.write("  Staff:    staff@northbound.test / staff-ops-42")
        self.stdout.write("  Admin:    admin@northbound.test / admin-change-me")
        self.stdout.write("  Coupon:   DISCOUNT20 (20%)")
