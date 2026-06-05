from rest_framework.pagination import CursorPagination


class ProductCursorPagination(CursorPagination):
    """Opt-in cursor pagination for product listings.

    Not wired by default — the project uses ``PageNumberPagination`` globally
    for the standard catalog list. Set ``pagination_class = ProductCursorPagination``
    on a viewset when deep-paginating large catalogs to avoid the cost of
    ``OFFSET`` scans on big offsets.
    """

    ordering = "-created_at"
    page_size = 12
    cursor_query_param = "cursor"
