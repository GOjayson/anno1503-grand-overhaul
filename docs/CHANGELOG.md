# Changelog

## 0.9.0-beta.1

- Add an in-game Original game / Custom world choice. Original generation ignores World Settings options.
- Keep tutorials, campaigns and other scenarios on their native start route.
- Reduce repeated drawing checks for worlds without a World Settings policy.
- Keep the verified temporary Ubisoft bootstrap menu hidden during the handoff.
- Simplify World Settings wording and installer setup; keep Food optional and off by default.
- Preserve preceding presets and restore native setup fields after failed custom starts.
- Prepare public World-only installation from the player's own verified game files.
- Move the long development record out of the README.

See the release notes for the exact automated and game checks for this beta.
Long-session stability and other localizations remain outside the verified scope.

## 0.8.0-dev.4

Added individual disaster settings, island variety, climate minimum/maximum counts and seeded island rotation. Corrected disaster activation and scene-to-player handoff. A 24-island world with ten rotations passed creation, in-game reload and full-restart reload. Terrain and disaster choices persisted exactly. See [environment validation](WORLD_ENVIRONMENT_OPTIONS.md).

## 0.7.0-dev.1

Added pirate reinforcement frequency, strength for newly created pirate ships, and neutral merchant traffic frequency. Saved policies and merchant creation passed bounded checks. Pirate raid timing and long-session visit rates remain unverified. See [faction activity](WORLD_FACTION_ACTIVITY.md).

## 0.6 development series

Added terra incognita over land and sea, strict line of sight, last-seen towns, ownership controls and deployed-unit exploration. Corrected camera performance, mineral symbols and in-game loading. See [visibility validation](WORLD_VISIBILITY_VALIDATION.md).

## Earlier development

World sizes, preview generation, native cultures, special factions, fertility, starting options, map seeds, presets, fair starts and resource distribution were developed in earlier experimental builds. Food 0.5 and the modular installer remain distinct features.

The [preserved development history](DEVELOPMENT_HISTORY.md) contains the previous detailed README. Its historical builds and test claims remain bound to their original versions.
