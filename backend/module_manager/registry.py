"""Centralized Module Registry for the CITADEL multi-tool platform.

New tools can be registered independently by creating a ModuleDefinition and
adding it in ``backend/module_manager/modules_config.py`` without modifying the
core platform routing, frontend dashboard layout, or existing modules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Dict, List, Optional

from fastapi import APIRouter, FastAPI


@dataclass(frozen=True)
class ModuleBackendConfig:
    """Backend integration metadata for a registered CITADEL module."""

    api_prefix: str
    router_factory: Optional[Callable[[], APIRouter]] = field(default=None, repr=False)
    legacy_api_prefix: Optional[str] = None
    health_endpoint: Optional[str] = None

    def to_public_dict(self) -> Dict[str, Optional[str]]:
        return {
            "api_prefix": self.api_prefix,
            "health_endpoint": self.health_endpoint,
        }


@dataclass(frozen=True)
class ModuleDefinition:
    """Metadata and integration descriptor for a single CITADEL tool module."""

    module_id: str
    code: str
    name: str
    description: str
    category: str
    icon: str
    entry_route: str
    status: str  # e.g., "Available"
    version: str
    backend: ModuleBackendConfig
    capabilities: List[str] = field(default_factory=list)

    def to_public_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["backend"] = self.backend.to_public_dict()
        return data


class ModuleRegistry:
    """Stores, validates, and mounts independent tool modules onto FastAPI."""

    def __init__(self) -> None:
        self._modules: Dict[str, ModuleDefinition] = {}

    def register(self, module: ModuleDefinition) -> None:
        if module.module_id in self._modules:
            raise ValueError(f"Duplicate module_id registered: {module.module_id}")
        self._modules[module.module_id] = module

    def list_modules(self) -> List[ModuleDefinition]:
        return list(self._modules.values())

    def get(self, module_id: str) -> Optional[ModuleDefinition]:
        return self._modules.get(module_id)

    def mount_all(self, app: FastAPI) -> None:
        """Mount every registered module's FastAPI router onto the main platform app."""
        for module in self._modules.values():
            if module.backend.router_factory is None:
                continue
            router = module.backend.router_factory()
            app.include_router(router, prefix=module.backend.api_prefix, tags=[module.name])
            if module.backend.legacy_api_prefix:
                app.include_router(
                    router,
                    prefix=module.backend.legacy_api_prefix,
                    include_in_schema=False,
                )


registry = ModuleRegistry()
