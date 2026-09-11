"""
apps/networks/api_utils.py

A minimal, self-contained implementation of the Appendix E response
envelope, scoped to this app only:

    Success: {"status": "success", "data": {...}, "meta": {...}}
    Error:   {"status": "error", "code": "...", "message": "..."}

If the rest of the codebase already has a shared envelope helper
(likely — Appendix E was written platform-wide, not just for this
module), swap this out for that one. This exists so Aspect 1's views
don't depend on infrastructure I can't see from here.
"""
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_exception_handler


def success(data, status_code=200, meta=None):
    body = {"status": "success", "data": data}
    if meta is not None:
        body["meta"] = meta
    return Response(body, status=status_code)


def error(code, message, status_code=400):
    return Response({"status": "error", "code": code, "message": message}, status=status_code)


class EnvelopePagination(PageNumberPagination):
    """Appendix E: 'List responses: Always paginated — default 25 items per page, max 100.'"""

    page_size = 25
    max_page_size = 100
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        return Response(
            {
                "status": "success",
                "data": data,
                "meta": {"page": self.page.number, "total": self.page.paginator.count},
            }
        )


def envelope_exception_handler(exc, context):
    """
    OPTIONAL. Register as REST_FRAMEWORK["EXCEPTION_HANDLER"] in settings.py
    to make DRF's own validation/404/permission errors match the Appendix E
    error envelope too. Without this registration, the explicit error()
    calls in this app's views are still envelope-compliant on their own —
    only exceptions DRF raises by itself (serializer validation, 404, 403)
    fall back to DRF's default {"detail": "..."} shape until this is wired in.
    """
    response = drf_default_exception_handler(exc, context)
    if response is None:
        return None
    detail = response.data.get("detail", response.data) if isinstance(response.data, dict) else response.data
    code = getattr(exc, "default_code", exc.__class__.__name__.upper()) if isinstance(exc, APIException) else "ERROR"
    response.data = {"status": "error", "code": code, "message": str(detail)}
    return response
