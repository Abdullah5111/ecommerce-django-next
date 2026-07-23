from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product, ProductVariant

from .models import Cart, CartItem
from .serializers import CartSerializer


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _resolve_variant(product, variant_id):
    """Return (variant, error). A variant product requires a valid variant of
    itself; a non-variant product must not be given one.
    """
    has_variants = product.variants.filter(is_active=True).exists()
    if variant_id in (None, "", 0, "0"):
        if has_variants:
            return None, "This product requires selecting a variant."
        return None, None
    variant = ProductVariant.objects.filter(
        pk=variant_id, product=product, is_active=True
    ).first()
    if variant is None:
        return None, "Invalid variant for this product."
    return variant, None


def _stock_of(product, variant):
    return variant.stock if variant is not None else product.stock


def _cap(product, variant, qty):
    """Clamp a desired quantity to [0, stock] of the chosen SKU."""
    return max(0, min(qty, _stock_of(product, variant)))


def _set_quantity(cart, product, variant, quantity):
    """Upsert a (product, variant) line to an absolute (capped) quantity;
    remove it when <= 0."""
    if quantity <= 0:
        CartItem.objects.filter(cart=cart, product=product, variant=variant).delete()
        return
    item, _ = CartItem.objects.get_or_create(
        cart=cart, product=product, variant=variant, defaults={"quantity": quantity}
    )
    if item.quantity != quantity:
        item.quantity = quantity
        item.save(update_fields=["quantity"])


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CartSerializer(get_cart(request.user)).data)

    def delete(self, request):
        cart = get_cart(request.user)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data)


class CartItemsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product = get_object_or_404(Product, pk=request.data.get("product"))
        variant, error = _resolve_variant(product, request.data.get("variant"))
        if error:
            return Response({"detail": error}, status=400)
        try:
            qty = int(request.data.get("quantity", 1))
        except (TypeError, ValueError):
            qty = 1
        cart = get_cart(request.user)
        existing = CartItem.objects.filter(
            cart=cart, product=product, variant=variant
        ).first()
        current = existing.quantity if existing else 0
        _set_quantity(cart, product, variant, _cap(product, variant, current + qty))
        return Response(CartSerializer(cart).data, status=201)


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, product_id):
        cart = get_cart(request.user)
        product = get_object_or_404(Product, pk=product_id)
        variant, error = _resolve_variant(product, request.data.get("variant"))
        if error:
            return Response({"detail": error}, status=400)
        try:
            qty = int(request.data.get("quantity", 0))
        except (TypeError, ValueError):
            qty = 0
        _set_quantity(cart, product, variant, _cap(product, variant, qty))
        return Response(CartSerializer(cart).data)

    def delete(self, request, product_id):
        cart = get_cart(request.user)
        # variant disambiguates when the same product sits in the cart under
        # more than one variant; omitted → the no-variant line.
        variant_id = request.query_params.get("variant")
        if variant_id in (None, "", "0"):
            CartItem.objects.filter(
                cart=cart, product_id=product_id, variant__isnull=True
            ).delete()
        else:
            CartItem.objects.filter(
                cart=cart, product_id=product_id, variant_id=variant_id
            ).delete()
        return Response(CartSerializer(cart).data)


class CartMergeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart = get_cart(request.user)
        for line in request.data.get("items", []):
            product = Product.objects.filter(pk=line.get("product")).first()
            if product is None:
                continue
            variant, error = _resolve_variant(product, line.get("variant"))
            if error:
                continue  # skip bad guest lines rather than fail the whole merge
            try:
                qty = int(line.get("quantity", 1))
            except (TypeError, ValueError):
                continue
            existing = CartItem.objects.filter(
                cart=cart, product=product, variant=variant
            ).first()
            current = existing.quantity if existing else 0
            _set_quantity(
                cart, product, variant, _cap(product, variant, current + qty)
            )  # sum, capped at stock
        return Response(CartSerializer(cart).data)
