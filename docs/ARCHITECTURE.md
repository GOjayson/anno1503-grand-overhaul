# Architecture

The project develops Anno 1503 History Edition features outside the installed
game. It preserves the existing experimental mods while building a common
platform for choosing, installing, launching and restoring compatible features.

## What exists today

There are two distinct layers:

- `legacy/` preserves imported mod source and its relative layout. These are
  experimental baselines with existing installation and activation assumptions.
- `src/anno1503_overhaul/` contains the feature catalogue, profiles, local
  package preparation, independent-copy installer and restoration platform.
  A valid profile records a selection; installation also requires the exact
  supported local inputs and native fingerprints.

The installer supports Food alone and Food with World Settings. World Settings
continues to use the preserved experimental native runtime. The new work
composes installation and restoration; it does not declare a new native runtime
or certify unperformed gameplay. See [installer usage](INSTALLER.md).

## Repository and local workspace

| Location | Responsibility |
| --- | --- |
| `legacy/world_settings/` | World Settings installer, activation helpers, native source, patch descriptions and developer source layout |
| `legacy/food_overhaul/` | Food overhaul source, patch descriptions and authored artwork |
| `legacy/launcher/` | Automatic launcher source and startup checks |
| `src/anno1503_overhaul/` | Feature profiles, checked package recipes, copy creation, vanilla recovery, isolated preparation, common installation/restoration and UI |
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

The shared installer resolves a profile, validates local inputs and prepares a
reviewable plan before changing game files. It then creates or reuses a managed
independent copy, establishes verified vanilla inputs and publishes one guarded
transaction with restoration metadata. Installation and restoration require a
closed game. Restore the managed copy before changing its feature set; native
features are not swapped underneath a running world.

## Current installer components

`packages.py` owns reviewed local package recipes and validation. Food-only
inputs come from public source, its patch specification and authored artwork.
The combined package additionally imports only the exact 25 pinned frozen
payloads from the local baseline provider. It retains the raw frozen World
specification and generates a relocated specification plus launcher pins for
the explicit source/copy pair. Provider Python is checked but never executed;
the package's helpers derive from tracked, provenance-checked source.

`filesystem.py` creates a separate writable copy using bounded game locations,
with inventory checks, reparse refusal and path-bound managed-copy metadata.
It does not copy historical backups or mod development workspaces into the new
game tree. `vanilla.py` checks the complete reviewed Food native/data/archive/UI
inputs and recovers original bytes from the source's existing known backups
when necessary. It reads those backups without changing them. Unproven bytes
and unknown archive changes are refused.

`legacy_adapter.py` runs preparation in a fresh interpreter to keep legacy
module imports isolated. The worker produces bounded before/after payloads;
it does not invoke a legacy installer. The copied World helper defers its
Food-native fingerprint check until Food preparation has produced an exact
whole-file before/after proof. Only the frozen Food output is accepted, and
an installed activation still requires the exact final fingerprint. This
permits composition from vanilla without applying a separate Food transaction.
Common installation reuses the reviewed
transaction implementation under the separate `GrandOverhaul_Backup_v1`
namespace. The journal owns the composed feature changes, whole-file backups,
introduced files, rollback and restoration together. Restoration rechecks both
current and original fingerprints and retains backup generations.

`installer.py` coordinates package validation, source/copy checks, copy
creation, recovery, composition and publication. The UI keeps **Check
installation** separate from **Install selected features**; publication
rechecks the prepared inputs. The UI's restore action affects managed copies
only. Retained journal bytes and reviewed source specifications make recovery
independent of a prepared package's continued availability.

## Shared platform responsibilities

The common platform owns the current supported paths and should extend them
through these responsibilities:

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

Build and integration tools take explicit source-game, independent-copy and
local-output paths. The modular installer does not infer an installed game
from the repository's parent directory or fall back to the original game when
a development copy is absent. Unknown build candidates are not made trusted
merely by editing their local package manifests.

Preserve the known build's fingerprints and evidence before refactoring. The
current installer imports the exact frozen World payloads; it does not claim
to reconstruct every historical native artifact from a clean public clone.
Any new native build needs output comparisons, isolated installation and
restoration checks, then separate actual launch/gameplay evidence.

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
