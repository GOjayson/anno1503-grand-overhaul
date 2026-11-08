"""Validate feature choices and store profiles without installing anything.

Profiles select features only. World-generation options remain inside Anno.
A valid profile is a planning document, not proof that a feature combination
can be built or installed by the imported legacy scripts.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import re
import tempfile

from .features import FeatureCatalog, default_catalog


SCHEMA_VERSION = 1
MAX_PROFILE_BYTES = 65536
_SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}


class ProfileError(ValueError):
    """A feature selection or stored profile is unsupported."""


def _catalog(catalog: FeatureCatalog | None) -> FeatureCatalog:
    return default_catalog() if catalog is None else catalog


def default_profile(catalog: FeatureCatalog | None = None, name: str = "Default") -> dict:
    catalog = _catalog(catalog)
    return validate_profile({
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "features": {feature.id: feature.default_enabled for feature in catalog.features},
    }, catalog)


def resolve_selection(document: Mapping, catalog: FeatureCatalog | None = None,
                      auto_enable_dependencies: bool = False) -> dict:
    """Normalize choices, optionally adding required *available* features.

    Missing feature flags become false. The caller chooses default_profile()
    explicitly when it wants defaults, so reading a partial profile cannot
    silently enable an unrelated feature.
    """
    catalog = _catalog(catalog)
    if type(auto_enable_dependencies) is not bool:
        raise ProfileError("auto_enable_dependencies must be a boolean.")
    if not isinstance(document, Mapping):
        raise ProfileError("A profile must be a JSON object.")
    if set(document) != {"schema_version", "name", "features"}:
        raise ProfileError("A profile requires exactly schema_version, name and features.")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise ProfileError(f"Only profile schema version {SCHEMA_VERSION} is supported.")
    name = document["name"]
    if (not isinstance(name, str) or not name.strip() or len(name) > 80
            or not name.isprintable()):
        raise ProfileError("Profile names must contain 1–80 printable characters.")
    requested = document["features"]
    if not isinstance(requested, Mapping):
        raise ProfileError("Profile features must be an object of boolean flags.")
    unknown = [feature_id for feature_id in requested if not isinstance(feature_id, str) or feature_id not in catalog]
    if unknown:
        raise ProfileError("Unknown feature IDs: " + ", ".join(sorted(map(repr, unknown))))
    if any(type(value) is not bool for value in requested.values()):
        raise ProfileError("Feature choices must be booleans, not strings or numbers.")
    chosen = {feature_id: requested.get(feature_id, False) for feature_id in catalog}

    def enable_requirements(feature_id: str) -> None:
        feature = catalog[feature_id]
        if not feature.available:
            raise ProfileError(f"{feature.name} is a research target and cannot be enabled.")
        for dependency in feature.requires:
            if not chosen[dependency]:
                if not auto_enable_dependencies:
                    raise ProfileError(f"{feature.name} requires {catalog[dependency].name}.")
                chosen[dependency] = True
            enable_requirements(dependency)

    # Catalogue construction has already rejected missing dependencies/cycles.
    for feature_id in catalog:
        if chosen[feature_id]:
            enable_requirements(feature_id)
    return {"schema_version": SCHEMA_VERSION, "name": name, "features": chosen}


def validate_profile(document: Mapping, catalog: FeatureCatalog | None = None) -> dict:
    return resolve_selection(document, catalog, auto_enable_dependencies=False)


def selected_features(document: Mapping, catalog: FeatureCatalog | None = None) -> tuple:
    """Return enabled features with dependencies before their dependants."""
    catalog = _catalog(catalog)
    normalized = validate_profile(document, catalog)
    return tuple(catalog[feature_id] for feature_id in catalog.dependency_order
                 if normalized["features"][feature_id])


def profile_path(directory: str | Path, slug: str) -> Path:
    """Build a Windows-safe filename inside an explicitly chosen directory."""
    if not isinstance(slug, str) or not _SLUG.fullmatch(slug) or slug in _RESERVED:
        raise ProfileError("Profile filenames need a lowercase name using letters, numbers, '_' or '-'.")
    root = Path(directory).resolve()
    target = root / (slug + ".json")
    if target.is_symlink() or target.resolve().parent != root:
        raise ProfileError("A profile path must stay inside its profile directory.")
    return target


def _file_path(path: str | Path) -> Path:
    path = Path(path)
    if any(part == ".." for part in path.parts):
        raise ProfileError("Profile paths cannot contain parent-directory traversal.")
    if path.suffix != ".json":
        raise ProfileError("Profile files must have the .json extension.")
    expected = profile_path(path.parent, path.stem)
    if path.resolve() != expected:
        raise ProfileError("The profile filename is not supported.")
    return expected


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProfileError(f"Duplicate profile key: {key}")
        result[key] = value
    return result


def load_profile(path: str | Path, catalog: FeatureCatalog | None = None) -> dict:
    path = _file_path(path)
    # Bound the read itself, rather than trusting a potentially stale stat.
    with path.open("rb") as stream:
        raw = stream.read(MAX_PROFILE_BYTES + 1)
    if len(raw) > MAX_PROFILE_BYTES:
        raise ProfileError("The profile is too large.")
    try:
        document = json.loads(raw, object_pairs_hook=_unique_keys)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, ProfileError):
            raise
        raise ProfileError("The profile is not valid JSON.") from error
    return validate_profile(document, catalog)


def save_profile(path: str | Path, document: Mapping, catalog: FeatureCatalog | None = None,
                 overwrite: bool = False) -> Path:
    if type(overwrite) is not bool:
        raise ProfileError("overwrite must be a boolean.")
    normalized = validate_profile(document, catalog)
    path = _file_path(path)
    data = (json.dumps(normalized, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(data) > MAX_PROFILE_BYTES:
        raise ProfileError("The profile is too large.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite:
        # Exclusive creation preserves an existing profile, including a file
        # created concurrently after the caller inspected the directory.
        with path.open("xb") as stream:
            stream.write(data)
        return path

    # Replacing a checked filename is atomic and does not follow a destination
    # symlink. The temporary file remains in the same explicit profile folder.
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return path
