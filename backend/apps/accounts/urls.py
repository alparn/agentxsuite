"""
URLs for accounts app.
"""
from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import ServiceAccountViewSet, login, logout, me, my_organizations, register

router = DefaultRouter()
router.register(r"service-accounts", ServiceAccountViewSet, basename="serviceaccount")

urlpatterns = [
    path("register/", register, name="register"),
    path("login/", login, name="login"),
    path("logout/", logout, name="logout"),
    path("me/", me, name="me"),
    path("me/orgs/", my_organizations, name="my_organizations"),
    path("", include(router.urls)),
]

