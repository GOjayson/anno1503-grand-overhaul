"""Feature metadata and dependencies, separate from legacy installation code.

Availability here means an imported experimental baseline exists. It does not
certify a new build, arbitrary feature combinations, or a portable installer.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
import re
from types import MappingProxyType


class CatalogError(ValueError):
    """The catalogue contains inconsistent or unsupported metadata."""


@dataclass(frozen=True)
class Feature:
    id: str
    name: str
    description: str
    status: str
    priority: str
    default_enabled: bool = False
    requires: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        """Research targets cannot be selected for an installation profile."""
        return self.status in ("experimental", "stable")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "available": self.available,
            "default_enabled": self.default_enabled,
            "requires": list(self.requires),
            "notes": list(self.notes),
        }


_ID = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


class FeatureCatalog(Mapping[str, Feature]):
    """Immutable catalogue validated before the selector reads any defaults."""

    def __init__(self, features: Iterable[Feature]):
        records = tuple(features)
        by_id: dict[str, Feature] = {}
        for feature in records:
            if not isinstance(feature, Feature):
                raise CatalogError("Catalogue entries must be Feature records.")
            if not isinstance(feature.id, str) or not _ID.fullmatch(feature.id):
                raise CatalogError(f"Invalid feature ID: {feature.id!r}")
            if feature.id in by_id:
                raise CatalogError(f"Duplicate feature ID: {feature.id}")
            if feature.status not in ("experimental", "stable", "research"):
                raise CatalogError(f"Unknown feature status: {feature.id}")
            if feature.priority not in ("priority", "planned"):
                raise CatalogError(f"Unknown feature priority: {feature.id}")
            if type(feature.default_enabled) is not bool:
                raise CatalogError(f"Feature defaults must be booleans: {feature.id}")
            if not feature.available and feature.default_enabled:
                raise CatalogError(f"An unavailable feature cannot be enabled by default: {feature.id}")
            if not isinstance(feature.requires, tuple) or any(
                not isinstance(item, str) or not _ID.fullmatch(item)
                for item in feature.requires
            ):
                raise CatalogError(f"Invalid dependency list: {feature.id}")
            if len(set(feature.requires)) != len(feature.requires):
                raise CatalogError(f"Duplicate dependency: {feature.id}")
            if not isinstance(feature.notes, tuple) or any(not isinstance(item, str) for item in feature.notes):
                raise CatalogError(f"Invalid feature notes: {feature.id}")
            if any(not isinstance(value, str) or not value.strip()
                   for value in (feature.name, feature.description)):
                raise CatalogError(f"Feature name and description are required: {feature.id}")
            by_id[feature.id] = feature

        for feature in records:
            for dependency in feature.requires:
                if dependency not in by_id:
                    raise CatalogError(f"Unknown dependency {dependency!r} required by {feature.id}.")

        visiting: set[str] = set()
        visited: set[str] = set()
        order: list[str] = []

        def visit(feature_id: str) -> None:
            if feature_id in visiting:
                raise CatalogError(f"Feature dependency cycle includes {feature_id}.")
            if feature_id in visited:
                return
            visiting.add(feature_id)
            for dependency in by_id[feature_id].requires:
                visit(dependency)
            visiting.remove(feature_id)
            visited.add(feature_id)
            order.append(feature_id)

        for feature in records:
            visit(feature.id)
        self.features = records
        self.dependency_order = tuple(order)
        self._by_id = MappingProxyType(by_id)

    def __getitem__(self, feature_id: str) -> Feature:
        return self._by_id[feature_id]

    def __iter__(self) -> Iterator[str]:
        return iter(self._by_id)

    def __len__(self) -> int:
        return len(self._by_id)


def default_catalog() -> FeatureCatalog:
    """Describe existing baselines and future targets without enabling targets."""
    return FeatureCatalog((
        Feature(
            id="food_overhaul",
            name="Food overhaul",
            description="The imported Food 0.5.0 overhaul, including its existing gameplay changes.",
            status="experimental",
            priority="priority",
            default_enabled=False,
            notes=("Imported working baseline; the overhaul is unfinished.",),
        ),
        Feature(
            id="world_settings",
            name="World Settings",
            description="In-game world settings with island inspection, fair starts, resource controls and automatic startup.",
            status="experimental",
            priority="priority",
            default_enabled=True,
            notes=(
                "World Settings and Food can be selected independently; install the selected feature set on a marked copy.",
                "Restore before changing the installed features, then use a fresh game launch.",
                "Currently supports 0–3 ordinary AI opponents through mapped stock placeholders; this is not a proven engine maximum.",
                "Huge 2048 worlds remain experimental; automated tests and bounded game runs do not establish long-session stability.",
            ),
        ),
        Feature(
            id="smarter_ai",
            name="Smarter / better AI",
            description="Research improved AI behaviour and a target of eight ordinary AI opponents.",
            status="research",
            priority="planned",
            notes=(
                "Eight AI opponents are an unverified research target, not a supported setting.",
                "Player identifiers, special factions and flag counts do not prove ordinary-AI capacity.",
            ),
        ),
        Feature(
            id="lan_multiplayer",
            name="Local-host multiplayer",
            description="Research locally hosted multiplayer and its verified player capacity.",
            status="research",
            priority="priority",
            notes=(
                "Networking, transport, simulation synchronisation and save compatibility require investigation.",
                "Eight players and the flag count are unverified; no working local-host implementation is claimed.",
            ),
        ),
        Feature(
            id="knowledge_overhaul",
            name="Knowledge overhaul",
            description="Explore expanded uses for schools, universities and knowledge progression.",
            status="research",
            priority="planned",
            notes=("Design and engine support have not been implemented or tested.",),
        ),
    ))
