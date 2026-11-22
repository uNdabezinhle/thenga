from rest_framework.pagination import CursorPagination as DRFCursorPagination
from rest_framework.pagination import PageNumberPagination


class CursorPagination(DRFCursorPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    # Prefer a universal field so models without created_at still paginate.
    ordering = "-id"


class PagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
