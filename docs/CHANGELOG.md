# Changelog

## Source development update — 2026-11-18

- Add Food 0.6 tier-specific diets, a read-only household Food summary using the original Food icon, and consistent food-icon backgrounds.
- Add a separate, pinned Food 0.6 + World Settings profile, including compatible AI need lookups and active engine exception-table checks.
- Add optional Bug Fixes: corrected King of Ore quest instructions and 118 quieter sound effects per installed supported language, derived from the player's originals.
- Allow Food 0.6, World Settings and Bug Fixes together with an exact package selection, guarded launch checks and one restoration journal.
- Allow World Settings and Bug Fixes with Food unchecked, retaining the stock diet and separate native profile. Refuse the unsupported preserved Food 0.5 + World + Bug Fixes combination explicitly.
- Default new source-installer Food choices to 0.6 while retaining explicit Food 0.5 selections and their preserved recipes.

Food 0.6 requires new endless worlds. This source update does not replace the
published World Settings-only beta ZIP. See [Food validation](FOOD_06_VALIDATION.md),
[combined validation](FOOD_WORLD_VALIDATION.md) and [Bug Fixes scope](BUGFIX_RESEARCH.md)
for separate automated, file, game and remaining gameplay checks.

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
