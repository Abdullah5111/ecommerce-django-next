from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product

from .models import Cart, CartItem
from .serializers import CartSerializer


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _cap(product, qty):
    """Clamp a desired quantity to [0, stock]."""
    return max(0, min(qty, product.stock))


def _set_quantity(cart, product, quantity):
    """Upsert a cart line to an absolute (already-capped) quantity; remove if <= 0."""
    if quantity <= 0:
        CartItem.objects.filter(cart=cart, product=product).delete()
        return
    item, _ = CartItem.objects.get_or_create(cart=cart, product=product, defaults={"quantity": quantity})
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
        try:
            qty = int(request.data.get("quantity", 1))
        except (TypeError, ValueError):
            qty = 1
        cart = get_cart(request.user)
        existing = CartItem.objects.filter(cart=cart, product=product).first()
        current = existing.quantity if existing else 0
        _set_quantity(cart, product, _cap(product, current + qty))
        return Response(CartSerializer(cart).data, status=201)


class CartItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, product_id):
        cart = get_cart(request.user)
        product = get_object_or_404(Product, pk=product_id)
        try:
            qty = int(request.data.get("quantity", 0))
        except (TypeError, ValueError):
            qty = 0
        _set_quantity(cart, product, _cap(product, qty))
        return Response(CartSerializer(cart).data)

    def delete(self, request, product_id):
        cart = get_cart(request.user)
        CartItem.objects.filter(cart=cart, product_id=product_id).delete()
        return Response(CartSerializer(cart).data)


class CartMergeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart = get_cart(request.user)
        for line in request.data.get("items", []):
            product = Product.objects.filter(pk=line.get("product")).first()
            if product is None:
                continue
            try:
                qty = int(line.get("quantity", 1))
            except (TypeError, ValueError):
                continue
            existing = CartItem.objects.filter(cart=cart, product=product).first()
            current = existing.quantity if existing else 0
            _set_quantity(cart, product, _cap(product, current + qty))  # sum, capped at stock
        return Response(CartSerializer(cart).data)
