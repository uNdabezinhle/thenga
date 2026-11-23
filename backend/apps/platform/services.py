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
    }
