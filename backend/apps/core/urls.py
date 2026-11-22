from django.urls import path

from .views import version_check

urlpatterns = [
    path("version-check/", version_check, name="version-check"),
]
