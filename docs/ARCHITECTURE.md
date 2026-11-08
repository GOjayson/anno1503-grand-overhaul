# Architecture

The project develops Anno 1503 History Edition features outside the installed
game. It preserves the existing experimental mods while building a common
platform for choosing, installing, launching and restoring compatible features.

## What exists today

There are two distinct layers:

- `legacy/` preserves imported mod source and its relative layout. These are
  experimental baselines with existing installation and activation assumptions.
- `src/anno1503_overhaul/` contains the new feature-profile foundation and its
  selection interface. A valid profile records a supported selection; it does
  not establish that a new combination can be installed or played.

The new selector prepares profiles. A common modular installer and a new native
runtime have not been delivered by this migration.

## Repository and local workspace

| Location | Responsibility |
| --- | --- |
| `legacy/world_settings/` | World Settings installer, activation helpers, native source, patch descriptions and developer source layout |
| `legacy/food_overhaul/` | Food overhaul source, patch descriptions and authored artwork |
| `legacy/launcher/` | Automatic launcher source and startup checks |
| `src/anno1503_overhaul/` | New feature catalogue, profile validation and selection interface |
| `docs/` | Architecture, feature status, migration instructions and roadmap |
| `.local/` | Ignored local copies of tested packages, game inputs, build output and private validation material |

The public repository contains mod source rather than a game installation.
Original and patched game DLLs, executable files, complete native islands, game
archives, saves and crash dumps remain local. Compiler installations, launch
sessions, machine-specific paths and generated logs also remain untracked.

The imported developer layout matters. For example, the World Settings runtime
builder reads source under `developer/source/` and engine metadata under its
sibling `developer/huge_world/`. Moving a file into a tidier folder can break
that relationship without changing its contents. Preserve the legacy tree until
an explicit build adaptation replaces it.

## Current feature dependency

World Settings currently depends on Food overhaul 0.5.0. This is an observed
installation requirement, not a desired permanent coupling:

1. The World Settings installer composes Food changes with the copied native
   overlays and private runtime, AI and island files.
2. Activation preflight requires exact Food 0.5.0 in the original source game.
3. The independently marked game copy must contain the exact combined World
   Settings build before activation can proceed.

The selector must make this dependency visible and resolve or reject an
incomplete selection. A World Settings-only profile cannot promise a working
installation until decoupling is implemented and tested. Separately imported
Food code also keeps its original limitations; later combined AI work does not
retroactively certify every standalone Food configuration.

## Intended feature lifecycle

Feature selection has two levels:

1. **Before installation or launch:** choose which overhaul modules are enabled.
   Resolve dependencies, unavailable features, conflicts and save compatibility.
2. **Inside the game:** configure world-specific options such as size, fertility,
   starting fleet and opponent count through World Settings.

The launcher should enable the approved feature set automatically. It should not
turn the external profile editor into a replacement for the in-game world menu.

A future shared installer should consume a fully resolved profile, validate
local game inputs and prepare a complete change plan before writing anything.
It should then publish a single guarded transaction with restoration metadata.
Installation and restoration require a closed game. A feature selection that
changes native code or save semantics takes effect on a fresh launch rather
than being swapped underneath a running world.

## Shared platform responsibilities

The common platform should own:

- Exact History Edition executable/module fingerprints and supported layouts.
- Dependency and conflict resolution, including unavailable research features.
- Patch composition and ownership of each modified byte range.
- Preparation of local payloads from the user's explicit game inputs.
- Transactional installation, backups, restoration and changed-file refusal.
- Fresh-process launch, readiness checks and one guarded activation attempt.
- Versioned profile data, feature-set fingerprints and save compatibility notes.

Feature modules should declare their inputs, dependencies, patch ranges,
configuration and validation evidence. Shared changes need an explicit
composition rule. Applying two patches in sequence to the same instructions is
not a conflict-resolution mechanism.

The existing launcher's useful safety properties remain requirements: verify
the active process and main menu, distinguish Ubisoft's pre-menu bootstrap
handoff, pin the final process identity, and never retry after an uncertain or
partial activation. Moving the source into Git does not remove those checks.

## Builds and reproducibility

A source-only checkout and a preserved tested package serve different purposes.
The local baseline store keeps the tested packages and released archives intact.
The public source enables review and further development, but legacy scripts
may still expect native inputs, generated payloads or inspection workspaces
that are not distributed in Git.

Build adaptation must make those inputs explicit. New build and integration
tools should accept a configured source-game path, independent test-copy path
and local output directory. They must not infer an installed game from the
repository's parent directory or silently fall back to the original game when
a development copy is absent.

Preserve the known build's fingerprints and evidence before refactoring. Once
the adapted pipeline can reconstruct a local package, compare its native
outputs and exercise installation/restoration on an isolated copy before
calling it a replacement for the tested baseline.

## Multiplayer and player capacity

Eight ordinary AI opponents and eight human multiplayer participants are
separate research goals. The current World Settings implementation supports
zero to three ordinary AI opponents from inspected stock placeholders. This
does not establish the engine's maximum capacity.

Flags or colours do not establish playable slots. Capacity work must inspect
owner IDs, human and AI controllers, Pirates, Venetians, native cultures, native
arrays, diplomacy, UI indexing, scene creation and save serialization. Network
session and synchronization limits require additional inspection.

The multiplayer workstream must establish local-host feasibility and a working
small session before extending capacity. Participants need matching feature
sets, native builds, world plans and deterministic simulation behavior. Lobby,
connection, save/resume and synchronization tests are separate from a menu that
offers a host button.

## Evidence levels

Keep these results separate in documentation and release metadata:

| Evidence | What it establishes |
| --- | --- |
| Portable tests | Catalogue, profile and other platform logic under their test inputs |
| Native/instruction fixtures | Inspected instruction, structure, bounds or transaction behavior |
| Actual menu observations | The stated UI appeared and accepted the observed interaction |
| Actual game runs and save comparisons | The named build loaded or preserved the inspected world state |
| Extended gameplay sessions | The specific long-session behavior actually observed |

Passing profile validation does not prove native installation, game loading,
Food production, diplomacy, combat or multiplayer. New features retain an
unavailable status until their implementation and required evidence justify
enabling them.
