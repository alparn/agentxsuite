"""Registry for selecting tool curators."""
from __future__ import annotations

import importlib
import logging
from collections.abc import Sequence

from django.conf import settings

from apps.tools.curators.base import BaseCurator
from apps.tools.curators.passthrough import PassthroughCurator

logger = logging.getLogger(__name__)


class CuratorsRegistry:
    """Select and instantiate configured curators."""

    default_curator_paths = [
        "apps.tools.curators.passthrough.PassthroughCurator",
    ]

    @classmethod
    def get_curator(cls, connection, raw_tools: Sequence) -> BaseCurator:
        """Return the first configured curator that can handle the connection."""
        for curator in cls.iter_curators():
            if curator.can_curate(connection, raw_tools):
                logger.info(
                    "Selected tool curator",
                    extra={
                        "connection_id": str(connection.id),
                        "curator_type": curator.curator_type,
                    },
                )
                return curator

        return PassthroughCurator()

    @classmethod
    def get_curator_by_type(cls, curator_type: str) -> BaseCurator:
        """Return a configured curator by type, falling back to passthrough."""
        for curator in cls.iter_curators():
            if curator.curator_type == curator_type:
                return curator

        logger.warning("Unknown curator type '%s'; using passthrough", curator_type)
        return PassthroughCurator()

    @classmethod
    def iter_curators(cls) -> list[BaseCurator]:
        """Instantiate configured curators in priority order."""
        curator_paths = getattr(settings, "TOOL_CURATORS", cls.default_curator_paths)
        curators: list[BaseCurator] = []

        for path in curator_paths:
            try:
                module_path, class_name = path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                curator_class = getattr(module, class_name)
                curator = curator_class()
            except (ImportError, AttributeError, ValueError, TypeError) as exc:
                logger.warning("Could not load tool curator '%s': %s", path, exc)
                continue

            if not isinstance(curator, BaseCurator):
                logger.warning("Configured tool curator '%s' is not a BaseCurator", path)
                continue
            curators.append(curator)

        if not any(isinstance(curator, PassthroughCurator) for curator in curators):
            curators.append(PassthroughCurator())

        return curators

