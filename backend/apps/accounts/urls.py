"""
URLs for accounts app.
"""
from __future__ import annotations

from django.urls import path

from apps.accounts.views import login, logout, me, my_organizations, register

urlpatterns = [
    path("register/", register, name="register"),
    path("login/", login, name="login"),
    path("logout/", logout, name="logout"),
    path("me/", me, name="me"),
    path("me/orgs/", my_organizations, name="my_organizations"),
]

