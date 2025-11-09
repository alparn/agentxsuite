"""
Common model mixins and base classes.
"""
from __future__ import annotations

import uuid

from django.db import models


class TimeStamped(models.Model):
    """
    Abstract base model that provides UUID primary key and automatic timestamps.

    All models should inherit from this class to get:
    - UUID primary key (id)
    - created_at (auto_now_add=True)
    - updated_at (auto_now=True)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

