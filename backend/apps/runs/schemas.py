"""
Pydantic schemas for runs app.
"""
from __future__ import annotations

from pydantic import BaseModel


class RunInputSchema(BaseModel):
    """Input schema for run creation."""

    input_json: dict

