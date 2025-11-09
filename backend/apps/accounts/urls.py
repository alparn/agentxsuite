"""
URLs for accounts app.
"""
from __future__ import annotations

from django.urls import path

from apps.accounts.views import login, logout, me, register

urlpatterns = [
    path("register/", register, name="register"),
    path("login/", login, name="login"),
    path("logout/", logout, name="logout"),
    path("me/", me, name="me"),
]

