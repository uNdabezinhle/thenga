from __future__ import annotations

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.exceptions import CartSessionInvalid

from .models import CartItem, SavedForLater, ShippingEstimate
from .serializers import (
    AddItemSerializer,
    ApplyDiscountSerializer,
    CartSerializer,
    SavedForLaterSerializer,
    SelectShippingSerializer,
    TransferCartSerializer,
    UpdateItemSerializer,
)
from .services import (
    apply_coupon,
    assert_stock,
    cart_queryset,
    ensure_shipping_estimates,
    get_or_create_cart,
    merge_carts,
)


class CartPermission(AllowAny):
    """Cart is dual-identity: auth user or valid guest session."""

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True
        return bool(getattr(request, "cart_session_valid", False))


class CartViewSet(viewsets.ViewSet):
    permission_classes = [CartPermission]

    def _cart(self, request):
        return get_or_create_cart(request)

    def list(self, request):
        cart = self._cart(request)
        ensure_shipping_estimates(cart)
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"], url_path="add_item")
    def add_item(self, request):
        ser = AddItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cart = self._cart(request)
        product = ser.validated_data["product_obj"]
        variant = ser.validated_data["variant_obj"]
        qty = ser.validated_data["quantity"]

        with transaction.atomic():
            item = (
                CartItem.objects.select_for_update()
                .filter(cart=cart, product=product, variant=variant)
                .first()
            )
            resulting = (item.quantity if item else 0) + qty
            assert_stock(product, variant, resulting)
            price = variant.unit_price if variant else product.base_price
            if item:
                item.quantity = resulting
                item.save(update_fields=["quantity"])
            else:
                CartItem.objects.create(
                    cart=cart,
                    product=product,
                    variant=variant,
                    quantity=qty,
                    unit_price_snapshot=price,
                )
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path=r"items/(?P<item_id>[0-9]+)/update",
    )
    def update_item(self, request, item_id=None):
        ser = UpdateItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cart = self._cart(request)
        try:
            item = CartItem.objects.select_related("product", "variant", "variant__inventory").get(
                pk=item_id, cart=cart
            )
        except CartItem.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Cart item not found.", "request_id": getattr(request, "request_id", "-")}},
                status=404,
            )
        qty = ser.validated_data["quantity"]
        assert_stock(item.product, item.variant, qty)
        item.quantity = qty
        item.save(update_fields=["quantity"])
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"items/(?P<item_id>[0-9]+)/remove",
    )
    def remove_item(self, request, item_id=None):
        cart = self._cart(request)
        deleted, _ = CartItem.objects.filter(pk=item_id, cart=cart).delete()
        # DELETE is idempotent — 204 even if already gone
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @action(
        detail=False,
        methods=["post"],
        url_path=r"items/(?P<item_id>[0-9]+)/save-for-later",
    )
    def save_for_later(self, request, item_id=None):
        if not request.user.is_authenticated:
            return Response(
                {
                    "error": {
                        "code": "authentication_failed",
                        "message": "Sign in to save items for later.",
                        "request_id": getattr(request, "request_id", "-"),
                    }
                },
                status=401,
            )
        cart = self._cart(request)
        try:
            item = CartItem.objects.select_related("product", "variant").get(
                pk=item_id, cart=cart
            )
        except CartItem.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Cart item not found.", "request_id": getattr(request, "request_id", "-")}},
                status=404,
            )
        saved, _ = SavedForLater.objects.update_or_create(
            user=request.user,
            product=item.product,
            variant=item.variant,
            defaults={"unit_price_snapshot": item.unit_price_snapshot},
        )
        item.delete()
        return Response(SavedForLaterSerializer(saved).data, status=201)

    @action(detail=False, methods=["post"], url_path="apply_discount")
    def apply_discount(self, request):
        ser = ApplyDiscountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cart = self._cart(request)
        apply_coupon(cart, ser.validated_data["code"])
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"], url_path="remove_discount")
    def remove_discount(self, request):
        code = request.data.get("code")
        cart = self._cart(request)
        qs = cart.discounts.all()
        if code:
            qs = qs.filter(code__iexact=code)
        qs.delete()
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"], url_path="select_shipping")
    def select_shipping(self, request):
        ser = SelectShippingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cart = self._cart(request)
        ensure_shipping_estimates(cart)
        try:
            estimate = ShippingEstimate.objects.get(
                pk=ser.validated_data["shipping_method_id"], cart=cart
            )
        except ShippingEstimate.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Shipping method not found.", "request_id": getattr(request, "request_id", "-")}},
                status=404,
            )
        cart.shipping_estimates.update(is_selected=False)
        estimate.is_selected = True
        estimate.save(update_fields=["is_selected"])
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        cart = self._cart(request)
        cart.items.all().delete()
        cart.discounts.all().delete()
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)

    @action(
        detail=False,
        methods=["post"],
        url_path="transfer_cart",
        permission_classes=[IsAuthenticated],
    )
    def transfer_cart(self, request):
        """Merge guest cart. Session must match X-Cart-Session (ownership proof)."""
        ser = TransferCartSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        session_id = str(ser.validated_data["session_id"])
        header_sid = getattr(request, "cart_session_id", None)
        if not header_sid or header_sid != session_id:
            raise CartSessionInvalid(
                "Session identifier does not match the X-Cart-Session header."
            )
        if not getattr(request, "cart_session_valid", False):
            raise CartSessionInvalid()
        cart = merge_carts(request.user, session_id)
        return Response(CartSerializer(cart).data)


class SavedItemsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def list(self, request):
        qs = SavedForLater.objects.filter(user=request.user).select_related(
            "product", "variant"
        )
        return Response(SavedForLaterSerializer(qs, many=True).data)

    @action(
        detail=False,
        methods=["post"],
        url_path=r"(?P<item_id>[0-9]+)/move_to_cart",
    )
    def move_to_cart(self, request, item_id=None):
        try:
            saved = SavedForLater.objects.select_related("product", "variant").get(
                pk=item_id, user=request.user
            )
        except SavedForLater.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "Saved item not found.", "request_id": getattr(request, "request_id", "-")}},
                status=404,
            )
        cart = get_or_create_cart(request)
        product, variant = saved.product, saved.variant
        item = CartItem.objects.filter(cart=cart, product=product, variant=variant).first()
        resulting = (item.quantity if item else 0) + 1
        assert_stock(product, variant, resulting)
        if item:
            item.quantity = resulting
            item.save(update_fields=["quantity"])
        else:
            CartItem.objects.create(
                cart=cart,
                product=product,
                variant=variant,
                quantity=1,
                unit_price_snapshot=saved.unit_price_snapshot,
            )
        saved.delete()
        cart = cart_queryset().get(pk=cart.pk)
        return Response(CartSerializer(cart).data)
