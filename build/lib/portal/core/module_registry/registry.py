"""Module registry: modules declare routers; the shell composes them.

A disabled module registers no routes, jobs, navigation or events
(master prompt 2.2). Registration is explicit and additive.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import APIRouter


@dataclass(frozen=True)
class ModuleDescriptor:
    name: str
    enabled: bool = True
    description: str = ""


@dataclass
class ModuleRegistry:
    _modules: dict[str, ModuleDescriptor] = field(default_factory=dict)
    _routers: dict[str, APIRouter] = field(default_factory=dict)

    def register(
        self,
        name: str,
        router: APIRouter | None = None,
        *,
        enabled: bool = True,
        description: str = "",
    ) -> None:
        if name in self._modules:
            msg = f"module '{name}' is already registered"
            raise ValueError(msg)
        self._modules[name] = ModuleDescriptor(
            name=name,
            enabled=enabled,
            description=description,
        )
        if router is not None and enabled:
            self._routers[name] = router

    def routers(self) -> list[APIRouter]:
        return list(self._routers.values())

    def descriptors(self) -> list[ModuleDescriptor]:
        return sorted(self._modules.values(), key=lambda m: m.name)

    def is_enabled(self, name: str) -> bool:
        module = self._modules.get(name)
        return module is not None and module.enabled
