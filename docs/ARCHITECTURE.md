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

The installer exposes Food alone, World Settings alone and the combined
selection. Food-only and combined installations preserve their existing Food
implementations. World-only uses a separate stock-host native derivative with
its own runtime and engine-plan fingerprints. Build checks do not certify
unperformed gameplay. See [installer usage](INSTALLER.md) and
[decoupling validation](DECOUPLING_VALIDATION.md).

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

## Independent choices and native profiles

The feature catalogue has no Food requirement on World Settings. Saved flags
and checkboxes remain independent. Installation resolves those choices to a
specific native/data profile:

| Selection | Host and gameplay data | Native profile |
| --- | --- | --- |
| Food only | Inspected Food 0.5 outputs on the managed copy | Existing Food patch recipe |
| World only | Stock host DLLs, diet, markets, archives and UI on the managed copy | Separately pinned stock-host runtime, private World-policy AI and stock-bound engine plan |
| Food and World | Existing Food and World outputs composed together | Preserved combined runtime and native overlays |

The preserved combined path retains its exact Food 0.5 source-installation
startup contract. Its runtime is not repurposed by relaxing fingerprints.
World-only instead runs the identical game executable from a fully independent
stock managed copy and uses that same folder as the world data root. The input
installation remains separate and read-only; verified historical originals can
provide stock recovery inputs even when that installation contains Food.

The World-only C derivative accepts the executable host as data root only with
the regular managed-copy marker and matching directory identity/spelling. Its
Python preflight verifies the complete marker/source binding, stock inputs,
introduced payloads, restoration journal and private AI identities. Native hook
installation still checks exact stock module hashes and every native preimage.

Restoration is required before switching profiles. Selection changes do not
hot-swap a running world, rewrite save semantics or transfer historical gameplay
evidence from one runtime to another.

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

`world_only_package.py` has a distinct package kind and regenerates its expected
recipe from the same pinned local corpus plus verified stock native inputs.
It uses `world_only_backend.py` in place of the combined Food composer. That
backend verifies the stock diet/native/archive/UI closure and introduces only
World runtime, World-policy AI and island files; it never calls Food transforms.
Derived disk Frame/Scene/Welt overlays are not installed on the stock host.
The private AI derivation retains one World-policy flag-preservation hook and
its exact unwind metadata while leaving the other original mapped bytes stock.

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

`client_context.py` implements the stock-host startup handoff. It starts the
normal registered Ubisoft route, positively identifies the fresh source main
menu and captures its existing startup context in memory. After rechecking that
exact owned menu, it starts the identical independent executable once while the
verified normal menu remains alive for client SDK initialization. Both exact
processes must reach and remain at their verified menus before the handoff
requests a normal close of its source menu. The copied host must then survive
alone at its verified menu before native activation. Existing games, worlds and
unknown processes are not adopted or closed. Argument and
environment values are not written to logs or packages, synthesized, or reused
for a second attempt. The Ubisoft client retains authentication and ownership
checks. No registration, permanent install-path or security-setting change is
part of this handoff.

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

`world_runtime_build.py` stages the imported 43-file compiled closure after
checking every original fingerprint. Only four staged compiled inputs change:
stock module/AI pins, the managed same-root configuration guard and the two
stock exception-table edit RVAs. All nine hook preimages and 173 engine sites
are checked on the exact stock PE images, including two original chained
Scene unwind parents. The engine plan relocates the two Food-expanded `.pdata`
fields to their uniquely matched stock function tuples; unchanged numeric
addresses are not assumed compatible.

The builder uses Zig 0.16.0, verifies AMD64 exports and canonicalizes only COFF
and debug build metadata. Two separate staging builds produced the same pinned
World-only runtime. Runtime profiles and old candidates stay under ignored
local storage; unknown rebuilt DLLs are not accepted by manifest changes.

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
