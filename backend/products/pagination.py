from rest_framework.pagination import CursorPagination


class ProductCursorPagination(CursorPagination):
    """Opt-in cursor pagination for deep-paginating large catalogs (avoids OFFSET
    scans). Not wired by default; the catalog uses PageNumberPagination globally.
    """

    ordering = "-created_at"
    page_size = 12
    cursor_query_param = "cursor"
