from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def version_check(request):
    """GET /api/v1/app/version-check/ — ADR-0006 cold-start gate."""
    return Response(
        {
            "min_supported": settings.APP_MIN_SUPPORTED,
            "latest": settings.APP_LATEST,
            "force_update": settings.APP_FORCE_UPDATE,
            "message": None,
        }
    )
