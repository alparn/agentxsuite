"""
URLs for canvas app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.canvas.views import CanvasStateViewSet

router = DefaultRouter()
router.register(r"canvas", CanvasStateViewSet, basename="canvas")

urlpatterns = [
    path("orgs/<uuid:org_id>/", include(router.urls)),
]

