from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product

from .models import WishlistItem
from .serializers import WishlistItemSerializer


def _wishlist_data(user):
    qs = WishlistItem.objects.filter(user=user).select_related("product__category").prefetch_related("product__images")
    return WishlistItemSerializer(qs, many=True).data


class WishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_wishlist_data(request.user))


class WishlistItemsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product = get_object_or_404(Product, pk=request.data.get("product"))
        WishlistItem.objects.get_or_create(user=request.user, product=product)
        return Response(_wishlist_data(request.user), status=201)


class WishlistItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        WishlistItem.objects.filter(user=request.user, product_id=product_id).delete()
        return Response(_wishlist_data(request.user))


class WishlistMergeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("product_ids", [])
        for pid in Product.objects.filter(pk__in=ids).values_list("pk", flat=True):
            WishlistItem.objects.get_or_create(user=request.user, product_id=pid)
        return Response(_wishlist_data(request.user))
