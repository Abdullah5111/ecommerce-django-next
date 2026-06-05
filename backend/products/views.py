import django_filters
from django.core.cache import cache
from django.db import connection
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Category, Product
from .serializers import (
    CategorySerializer,
    CategoryTreeSerializer,
    CategoryDetailSerializer,
    ProductSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        roots = Category.objects.filter(parent__isnull=True)
        serializer = CategoryTreeSerializer(roots, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="by-path")
    def by_path(self, request):
        path = request.query_params.get("path", "")
        try:
            cat = Category.objects.get(full_slug=path)
        except Category.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        return Response(CategoryDetailSerializer(cat).data)


class ProductFilter(django_filters.FilterSet):
    category__slug = django_filters.CharFilter(
        field_name="category__slug", lookup_expr="exact"
    )
    category_path = django_filters.CharFilter(method="filter_category_path")
    price__gte = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price__lte = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ["category__slug", "category_path", "price__gte", "price__lte", "in_stock"]

    def filter_category_path(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(category__full_slug=value)
            | Q(category__full_slug__startswith=value + "/")
        )

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__gt=0)
        return queryset


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_active=True).select_related("category")
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "created_at"]

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).select_related("category")
        # Postgres full-text search path: only when on PG and ?search= is set.
        if connection.vendor == "postgresql":
            q = self.request.query_params.get("search") if hasattr(self, "request") and self.request else None
            if q:
                from django.contrib.postgres.search import (
                    SearchQuery,
                    SearchRank,
                    SearchVector,
                )
                vector = SearchVector("name", "description")
                query = SearchQuery(q)
                qs = (
                    qs.annotate(rank=SearchRank(vector, query))
                    .filter(rank__gt=0)
                    .order_by("-rank")
                )
        return qs

    @action(detail=False, methods=["get"], url_path="featured")
    def featured(self, request):
        cache_key = "products:featured:v1"
        data = cache.get(cache_key)
        if data is None:
            qs = self.get_queryset().filter(is_featured=True).order_by("-created_at")[:12]
            data = self.get_serializer(qs, many=True).data
            cache.set(cache_key, data, timeout=300)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="bestsellers")
    def bestsellers(self, request):
        cache_key = "products:bestsellers:v1"
        data = cache.get(cache_key)
        if data is None:
            qs = (
                self.get_queryset()
                .annotate(
                    sales=Coalesce(
                        Sum(
                            "orderitem__quantity",
                            filter=Q(orderitem__order__status="paid"),
                        ),
                        0,
                    )
                )
                .order_by("-sales", "-created_at")[:12]
            )
            data = self.get_serializer(qs, many=True).data
            cache.set(cache_key, data, timeout=300)
        return Response(data)
