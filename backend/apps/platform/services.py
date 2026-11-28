"""Packages, trials, and which merchant a staff user belongs to."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from apps.orders.services import OrderError

from .catalog import ADDON_BY_CODE, PACKAGE_BY_CODE, SAMPLE_SLUG, TRIAL_DAYS
from .models import Merchant, MerchantAddOn, MerchantMembership


def merchant_for(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    row = (
        MerchantMembership.objects.select_related("merchant")
        .filter(user=user)
        .order_by("id")
        .first()
    )
    return row.merchant if row else None


def selling_features(merchant: Merchant | None) -> dict:
    """Sample and unaffiliated demo users keep shop and till. A trial has both."""
    if merchant is None or merchant.slug == SAMPLE_SLUG:
        return {"shop": True, "pos": True, "reason": ""}
    now = timezone.now()
    if merchant.status == Merchant.Status.READ_ONLY or (
        merchant.status == Merchant.Status.TRIALING
        and merchant.trial_ends
        and merchant.trial_ends <= now
    ):
        return {"shop": False, "pos": False, "reason": "trial_ended"}
    if merchant.status == Merchant.Status.TRIALING and merchant.trial_ends and merchant.trial_ends > now:
        return {"shop": True, "pos": True, "reason": "trial"}
    package = PACKAGE_BY_CODE.get(merchant.package)
    if package is None:
        return {"shop": False, "pos": False, "reason": "package"}
    return {"shop": package["shop"], "pos": package["pos"], "reason": "package"}


def require_feature(merchant, feature: str) -> None:
    flags = selling_features(merchant)
    if flags.get(feature):
        return
    if flags.get("reason") == "trial_ended":
        raise OrderError(
            "The trial has ended. Choose a package before selling again.",
            code="package_excluded",
        )
    raise OrderError("That feature is not on this package.", code="package_excluded")


def has_addon(merchant, code: str) -> bool:
    if merchant is None or merchant.slug == SAMPLE_SLUG:
        return True
    return MerchantAddOn.objects.filter(merchant=merchant, code=code).exists()


def require_addon(merchant, code: str) -> None:
    if has_addon(merchant, code):
        return
    raise OrderError("That feature is not on this package.", code="package_excluded")


def order_scope(user) -> Q:
    """Sample staff see unaffiliated orders. A member sees only that merchant."""
    merchant = merchant_for(user)
    if merchant is None or merchant.slug == SAMPLE_SLUG:
        return Q(merchant__isnull=True) | Q(merchant__slug=SAMPLE_SLUG)
    return Q(merchant=merchant)


def single_merchant(products):
    found = []
    for product in products:
        merchant = getattr(product, "merchant", None)
        if merchant is not None and merchant.pk not in {row.pk for row in found}:
            found.append(merchant)
    if len(found) > 1:
        raise OrderError("One shop per order.", code="mixed_merchant")
    return found[0] if found else None


def merchants_on_order(order):
    seen = []
    for item in order.items.select_related("product"):
        merchant = item.product.merchant
        if merchant is not None and merchant.id not in {row.id for row in seen}:
            seen.append(merchant)
    return seen


def shop_profile(slug: str) -> dict | None:
    """Public face of a shop. No keys, no mail addresses."""
    from django.conf import settings

    cleaned = (slug or SAMPLE_SLUG).strip().lower() or SAMPLE_SLUG
    if cleaned == SAMPLE_SLUG:
        merchant = Merchant.objects.filter(slug=SAMPLE_SLUG).first()
        name = merchant.trading_name if merchant is not None else ""
        return {
            "slug": SAMPLE_SLUG,
            "trading_name": name or getattr(settings, "REKA_SITE_BRAND_NAME", "Northbound"),
            "shop": True,
            "pos": True,
            "read_only": False,
        }
    merchant = Merchant.objects.filter(slug=cleaned).first()
    if merchant is None:
        return None
    flags = selling_features(merchant)
    return {
        "slug": merchant.slug,
        "trading_name": merchant.trading_name,
        "shop": flags["shop"],
        "pos": flags["pos"],
        "read_only": flags["reason"] == "trial_ended",
    }


def shop_is_public(slug: str) -> bool:
    if slug == SAMPLE_SLUG:
        return True
    merchant = Merchant.objects.filter(slug=slug).first()
    if merchant is None:
        return False
    return bool(selling_features(merchant)["shop"])


def product_scope(user) -> Q:
    merchant = merchant_for(user)
    if merchant is None or merchant.slug == SAMPLE_SLUG:
        return Q(merchant__isnull=True) | Q(merchant__slug=SAMPLE_SLUG)
    return Q(merchant=merchant)


def variant_scope(user) -> Q:
    merchant = merchant_for(user)
    if merchant is None or merchant.slug == SAMPLE_SLUG:
        return Q(product__merchant__isnull=True) | Q(product__merchant__slug=SAMPLE_SLUG)
    return Q(product__merchant=merchant)


def public_product_scope(slug: str) -> Q:
    if slug == SAMPLE_SLUG:
        return Q(merchant__isnull=True) | Q(merchant__slug=SAMPLE_SLUG)
    return Q(merchant__slug=slug)


def _unique_slug(trading_name: str) -> str:
    base = slugify(trading_name)[:40] or "shop"
    slug = base
    suffix = 2
    while Merchant.objects.filter(slug=slug).exists():
        slug = f"{base[:36]}-{suffix}"
        suffix += 1
    return slug


def open_merchant(*, user, payload: dict) -> Merchant:
    trading = str(payload.get("trading_name") or "").strip()
    if len(trading) < 2:
        raise OrderError("Enter the shop name.", code="validation_failed")
    if not payload.get("privacy_accepted"):
        raise OrderError("Accept the privacy notice to open a shop.", code="validation_failed")
    package = str(payload.get("package") or "shop_till").strip()
    if package not in PACKAGE_BY_CODE:
        raise OrderError("Choose Till, Shop, or Shop + Till.", code="validation_failed")
    existing = merchant_for(user)
    if existing and existing.slug != SAMPLE_SLUG:
        raise OrderError("This account already has a shop.", code="merchant_exists")
    addons = payload.get("addons") or []
    if not isinstance(addons, list):
        raise OrderError("Extras must be a list.", code="validation_failed")
    unknown = [code for code in addons if code not in ADDON_BY_CODE]
    if unknown:
        raise OrderError("Unknown extra.", code="validation_failed")
    if not payload.get("empty_catalogue_ok"):
        raise OrderError(
            "Confirm an empty catalogue, or add products after setup.",
            code="validation_failed",
        )

    merchant = Merchant.objects.create(
        slug=_unique_slug(str(payload.get("slug") or trading)),
        trading_name=trading[:120],
        legal_name=str(payload.get("legal_name") or "")[:160],
        vat_number=str(payload.get("vat_number") or "")[:32],
        city=str(payload.get("city") or "")[:120],
        support_email=str(payload.get("support_email") or user.email)[:254],
        package=package,
        status=Merchant.Status.TRIALING,
        trial_ends=timezone.now() + timedelta(days=TRIAL_DAYS),
        empty_catalogue_ok=True,
        privacy_accepted=True,
    )
    MerchantMembership.objects.create(
        merchant=merchant, user=user, role=MerchantMembership.Role.OWNER
    )
    for code in dict.fromkeys(addons):
        MerchantAddOn.objects.create(merchant=merchant, code=code)

    store_name = str(payload.get("store_name") or trading)[:120]
    from apps.pos.models import Store

    Store.objects.get_or_create(
        code=merchant.slug[:32],
        defaults={
            "name": store_name,
            "sells_online": package != "till",
            "is_active": True,
            "merchant": merchant,
        },
    )
    return merchant


def checklist(merchant: Merchant, user) -> dict:
    from apps.catalogue.models import Product

    has_product = Product.objects.filter(merchant=merchant, is_active=True).exists()
    flags = selling_features(merchant)
    items = [
        {"key": "email", "label": "Email verified", "done": bool(user.email_verified)},
        {"key": "privacy", "label": "Privacy notice accepted", "done": merchant.privacy_accepted},
        {"key": "package", "label": "Package chosen", "done": merchant.package in PACKAGE_BY_CODE},
        {
            "key": "catalogue",
            "label": "Catalogue started or skipped",
            "done": has_product or merchant.empty_catalogue_ok,
        },
    ]
    return {
        "slug": merchant.slug,
        "trading_name": merchant.trading_name,
        "package": merchant.package,
        "status": merchant.status if flags["reason"] != "trial_ended" else "read_only",
        "trial_ends": merchant.trial_ends.isoformat() if merchant.trial_ends else None,
        "shop": flags["shop"],
        "pos": flags["pos"],
        "ready": all(item["done"] for item in items) and flags["reason"] != "trial_ended",
        "items": items,
        "addons": list(merchant.addons.values_list("code", flat=True)),
        "payfast_configured": bool(merchant.payfast_merchant_id and merchant.payfast_merchant_key),
    }


def choose_package(user, payload: dict) -> Merchant:
    """Mark the chosen package active. Illustrative prices are not collected."""
    merchant = _owner_merchant(user)
    package = str((payload or {}).get("package") or merchant.package).strip()
    if package not in PACKAGE_BY_CODE:
        raise OrderError("Choose Till, Shop, or Shop + Till.", code="validation_failed")
    addons = None
    if isinstance(payload, dict) and "addons" in payload:
        addons = payload.get("addons") or []
        if not isinstance(addons, list):
            raise OrderError("Extras must be a list.", code="validation_failed")
        unknown = [code for code in addons if code not in ADDON_BY_CODE]
        if unknown:
            raise OrderError("Unknown extra.", code="validation_failed")
        addons = list(dict.fromkeys(addons))
    merchant.package = package
    merchant.status = Merchant.Status.ACTIVE
    merchant.save(update_fields=["package", "status"])
    if addons is not None:
        merchant.addons.exclude(code__in=addons).delete()
        have = set(merchant.addons.values_list("code", flat=True))
        for code in addons:
            if code not in have:
                MerchantAddOn.objects.create(merchant=merchant, code=code)
    return merchant


def _owner_merchant(user) -> Merchant:
    merchant = merchant_for(user)
    if merchant is None or merchant.slug == SAMPLE_SLUG:
        raise OrderError("Open a shop first.", code="permission_denied")
    role = (
        MerchantMembership.objects.filter(merchant=merchant, user=user)
        .values_list("role", flat=True)
        .first()
    )
    if role != MerchantMembership.Role.OWNER:
        raise OrderError("Only the owner can change the shop.", code="permission_denied")
    return merchant


def invite_staff(user, payload: dict) -> dict:
    merchant = _owner_merchant(user)
    email = payload.get("email") if isinstance(payload, dict) else payload
    cleaned = str(email or "").strip().lower()
    if "@" not in cleaned:
        raise OrderError("Enter a staff email.", code="validation_failed")
    from django.contrib.auth import get_user_model

    from apps.accounts.models import PasswordResetToken
    from apps.notifications.services import notify_password_reset

    User = get_user_model()
    staff = User.objects.filter(email__iexact=cleaned).first()
    invited = False
    if staff is None:
        username = cleaned.split("@", 1)[0][:30] or "staff"
        base = username
        suffix = 2
        while User.objects.filter(username=username).exists():
            username = f"{base[:24]}{suffix}"
            suffix += 1
        staff = User.objects.create_user(
            email=cleaned,
            username=username,
            password=None,
            email_verified=False,
        )
        staff.set_unusable_password()
        staff.save(update_fields=["password"])
        token = PasswordResetToken.create_for(staff)
        notify_password_reset(staff, token.token)
        invited = True
    if MerchantMembership.objects.filter(merchant=merchant, user=staff).exists():
        raise OrderError("That person is already on this shop.", code="merchant_exists")
    MerchantMembership.objects.create(
        merchant=merchant, user=staff, role=MerchantMembership.Role.STAFF
    )
    return {"email": staff.email, "invited": invited, "role": "staff"}


def add_store(user, payload: dict):
    from apps.pos.models import Store

    merchant = _owner_merchant(user)
    existing = Store.objects.filter(merchant=merchant).count()
    if existing >= 1:
        require_addon(merchant, "extra_store")
    name = str(payload.get("name") or "").strip()
    if len(name) < 2:
        raise OrderError("Enter the store name.", code="validation_failed")
    code = slugify(str(payload.get("code") or name))[:32] or "store"
    if Store.objects.filter(code=code).exists():
        raise OrderError("That store code is taken.", code="validation_failed")
    sells_online = payload.get("sells_online")
    if sells_online is None:
        sells_online = merchant.package != "till"
    return Store.objects.create(
        merchant=merchant,
        code=code,
        name=name[:120],
        sells_online=bool(sells_online) and merchant.package != "till",
        is_active=True,
    )


def import_catalogue(user, payload: dict) -> list:
    from decimal import Decimal

    from django.utils.text import slugify as slug

    from apps.catalogue.models import Brand, Category, Inventory, Product, ProductVariant
    from apps.pos.models import Store, StoreStock

    merchant = _owner_merchant(user)
    rows = payload.get("rows")
    if payload.get("sample") is True:
        rows = [
            {"name": "Shop bag", "sku": f"{merchant.slug}-bag", "price": "50.00", "quantity": 10},
            {"name": "Counter item", "sku": f"{merchant.slug}-item", "price": "20.00", "quantity": 10},
        ]
    elif isinstance(payload.get("csv"), str) and payload.get("csv").strip():
        rows = []
        lines = [line.strip() for line in payload["csv"].splitlines() if line.strip()]
        start = 1 if lines and lines[0].lower().startswith("name") else 0
        for line in lines[start:]:
            parts = [part.strip() for part in line.split(",")]
            if len(parts) < 4:
                raise OrderError("Each CSV row needs name, sku, price, and quantity.", code="validation_failed")
            rows.append(
                {"name": parts[0], "sku": parts[1], "price": parts[2], "quantity": parts[3]}
            )
    if not isinstance(rows, list) or not rows:
        raise OrderError("Send rows, a csv, or sample: true.", code="validation_failed")

    brand, _ = Brand.objects.get_or_create(
        slug=f"{merchant.slug}-house"[:50],
        defaults={"name": merchant.trading_name[:120]},
    )
    category, _ = Category.objects.get_or_create(
        slug=f"{merchant.slug}-general"[:50],
        defaults={"name": "General"},
    )
    store = Store.objects.filter(merchant=merchant).order_by("id").first()
    created = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        sku = str(row.get("sku") or "").strip()[:64]
        if len(name) < 2 or not sku:
            raise OrderError("Each product needs a name and a SKU.", code="validation_failed")
        if Product.objects.filter(sku=sku).exists() or ProductVariant.objects.filter(sku=sku).exists():
            raise OrderError(f"{sku} is already used.", code="validation_failed")
        try:
            price = Decimal(str(row.get("price")))
            quantity = int(row.get("quantity"))
        except Exception:
            raise OrderError("Price and quantity must be numbers.", code="validation_failed")
        if price < 0 or quantity < 0:
            raise OrderError("Price and quantity cannot be negative.", code="validation_failed")
        base_slug = (slug(f"{merchant.slug}-{sku}") or sku.lower())[:46]
        product_slug = base_slug
        suffix = 2
        while Product.objects.filter(slug=product_slug).exists():
            product_slug = f"{base_slug}-{suffix}"[:50]
            suffix += 1
        product = Product.objects.create(
            merchant=merchant,
            sku=sku,
            name=name[:255],
            slug=product_slug,
            brand=brand,
            category=category,
            base_price=price,
            sale_channel="both" if merchant.package != "till" else "pos",
        )
        variant = ProductVariant.objects.create(product=product, sku=sku, label="One")
        if store is not None and not store.sells_online:
            StoreStock.objects.create(store=store, variant=variant, quantity=quantity)
        else:
            Inventory.objects.create(variant=variant, quantity=quantity)
        created.append({"sku": sku, "name": product.name, "quantity": quantity})
    return created


def save_payfast(user, payload: dict) -> dict:
    merchant = _owner_merchant(user)
    require_addon(merchant, "live_payfast")
    merchant_id = str(payload.get("merchant_id") or "").strip()
    merchant_key = str(payload.get("merchant_key") or "").strip()
    if len(merchant_id) < 4 or len(merchant_key) < 4:
        raise OrderError("Paste the PayFast merchant id and key.", code="validation_failed")
    merchant.payfast_merchant_id = merchant_id[:64]
    merchant.payfast_merchant_key = merchant_key[:64]
    if "passphrase" in payload:
        merchant.payfast_passphrase = str(payload.get("passphrase") or "")[:128]
    if "sandbox" in payload:
        merchant.payfast_sandbox = bool(payload.get("sandbox"))
    merchant.save(
        update_fields=[
            "payfast_merchant_id",
            "payfast_merchant_key",
            "payfast_passphrase",
            "payfast_sandbox",
        ]
    )
    return {"configured": True, "sandbox": merchant.payfast_sandbox}
