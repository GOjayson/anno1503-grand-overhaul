# Roadmap

Priorities follow the project owner's direction: World Settings, Food overhaul
and local-host multiplayer are priority workstreams. A larger AI capacity and
Knowledge overhaul are additional goals. The milestones below describe work
and acceptance gates, not release dates or promised engine capabilities.

## Foundation: preserve and separate development

- Keep development in this repository outside the installed game.
- Preserve the tested World Settings, Food and launcher packages and released
  archives locally, with their fingerprints and evidence scopes.
- Import reviewable mod source without game binaries, native saves or machine
  configuration in the public repository.
- Establish portable tests, repository-content checks and documented local
  input/build directories.
- Prepare feature profiles with visible dependencies and unavailable modules.

**Delivered foundation:** source and local baseline preservation, feature
profiles, portable checks and repository boundaries are in place. The modular
installer now adds a supported Food-only and combined installation path. This
does not claim a portable rebuild of every historical native package or new
actual-game evidence for the installer integration.

## Priority: modular platform and existing features

Current implementation includes explicit source/copy paths, a check-first
interface with Food and World checkboxes, reviewed local package recipes,
verified vanilla recovery on managed copies, a shared installation/restoration
journal and the pinned automatic World launcher adapter. Food-only package
preparation uses public source without private World payloads. The combined
path retains its exact local payload and source-Food requirements.

Remaining work:

1. Broaden supported build/language coverage through inspected fingerprints
   and real input checks rather than accepting unknown files.
2. Extend reproducible native payload reconstruction so the current frozen
   local baseline store is no longer required for the combined selection.
3. Exercise the modular installer, automatic startup, gameplay and restoration
   together in actual game runs; retain bounded historical evidence separately.
4. Decouple World Settings from the Food baseline if independent selection is
   to be offered. Until then, keep Food as an explicit required dependency.
5. Validate each supported selection on an isolated game copy. Record save
   compatibility and new-world requirements for every module.

**Acceptance:** supported selections can be built, checked, installed, launched
and restored without changing prior backups or unselected features. Unknown
or conflicting inputs are refused before publication. A successful profile
validation alone does not satisfy this milestone.

## Priority: World Settings continuation

- Keep the corrected 2048 engine baseline and the smaller-world behavior.
- Broaden actual layout, resource, start-position and save/reload coverage.
- Exercise longer sessions, settlement, ship navigation and map-edge behavior.
- Add selected menu improvements in small steps, such as seed reuse, presets,
  starting-area/cargo choices and climate/layout controls.
- Preserve all culture and special-faction choices and essential-resource
  validation as new choices are added.

**Acceptance:** each new setting has meaningful automated checks and the
necessary actual menu/world/save evidence. Existing native patches and Food
changes remain intact. Keep unsupported combinations and dimensions refused.

## Priority: finish the Food overhaul

- Verify the five-food economy from production through consumption and sales.
- Check resident needs, starvation, market switches, stock/accounting and trade.
- Extend ordinary AI planning to the actual Food economy rather than treating
  index safety or an active controller as proof of economic competence.
- Cover existing save compatibility, new-world requirements and repeated
  save/reload behavior.
- Test Food alone and the combined feature set separately where both are
  supported.

**Acceptance:** sustained human and AI settlements can produce, distribute,
consume and trade the intended foods in the documented configurations. Report
all remaining unsupported profiles explicitly.

## Priority research: local-host multiplayer

Begin feasibility work alongside the existing-feature workstreams so that
future module interfaces account for deterministic state and synchronization.

1. Inspect the History Edition transport/session path and discover which
   player roles and limits the engine actually supports.
2. Prove a small local host/join session before attempting extra capacity.
3. Define version/feature-set compatibility checks for joining participants.
4. Verify identical world plans, simulation state, ownership and save/resume.
5. Exercise disconnects, joining failures, repeated sessions and long runs.
6. Increase capacity only after the relevant native bounds and live session
   tests justify it.

**Acceptance:** actual independent game instances can host/join and remain
synchronized in the documented configuration. Eight human participants remain
a research target until verified; flags or a lobby control do not establish it.

## Smarter AI and increased capacity

Build on the Food and world-generation work to improve settlement, production,
resource planning, ship use, trade and diplomacy. Treat the separate eight-AI
target as an engine extension investigation.

Audit native controller/owner allocations, special-faction reservations,
arrays, scene construction, diplomacy, UI and save serialization before
raising the current zero-to-three supported ordinary-AI range. Verify AI
behavior and player count independently, including interaction with local
multiplayer when that work becomes available.

**Acceptance:** the documented number of ordinary AI opponents remains active,
economically functional and save-compatible in sustained game runs. No higher
count is exposed solely because a colour or flag exists.

## Knowledge overhaul

Agree on the intended roles of schools and universities, then inspect the
relevant native building effects, progression and saved state. Prototype one
bounded mechanic before expanding its research/unlock rules or connections to
other modules.

**Acceptance:** progression persists across saves, communicates its effects,
has defined AI behavior and uses deterministic state suitable for multiplayer.
Its interaction with optional Food/economy features is documented and tested.

## Release discipline

For every milestone, distinguish portable tests, native/instruction fixtures,
actual menu observations, native saves and extended gameplay evidence. Publish
the exact supported build and feature set. Preserve previous releases and
restoration support. Keep unfinished research features unavailable until they
have an implementation and an appropriate verification record.
