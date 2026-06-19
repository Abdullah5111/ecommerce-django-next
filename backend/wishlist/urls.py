from django.urls import path

from .views import WishlistView, WishlistItemsView, WishlistItemDetailView, WishlistMergeView

urlpatterns = [
    path("wishlist/", WishlistView.as_view(), name="wishlist"),
    path("wishlist/items/", WishlistItemsView.as_view(), name="wishlist-items"),
    path("wishlist/items/<int:product_id>/", WishlistItemDetailView.as_view(), name="wishlist-item-detail"),
    path("wishlist/merge/", WishlistMergeView.as_view(), name="wishlist-merge"),
]
