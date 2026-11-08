# Imported source and preserved baselines

The import copies the current Food overhaul 0.5.0, combined World Settings
0.11.0-dev.1 and automatic launcher 1.0.0 source into `legacy/`. The original
installed files, working copy, saves, backups, shortcuts and released archives
stay in place. `provenance/legacy_import.json` records every imported source's
original and imported SHA-256 with relative provenance labels.

The World Settings package retains its internal directory layout, particularly
`developer/source/` and its sibling `developer/huge_world/`. All 43 inputs named
by the verified native runtime build remain byte-exact. Generated mod hook
arrays, patch plans, catalogue metadata and simplified preview-coast metadata
are source/build inputs; they are not complete native game islands or modules.

Food PNGs and indexed icon descriptions are authored mod artwork. The imported
`assets/ARTWORK.txt` records their generated provenance. Food patch and historical
compatibility JSONs contain fingerprints, byte differences and appended mod
code rather than whole original game files.

## Public import boundary

The importer permits reviewed authored source extensions, authored food artwork,
selected documentation and an explicit patch/build JSON allowlist. It excludes:

- Original and patched game DLLs/EXEs, complete `.scp` islands, `.sze` worlds,
  game archives, saves, dumps, shortcuts and compiler intermediates.
- Bulk `.asm` disassembly, build caches and duplicated historical snapshots.
- Raw live/copy-acceptance reports, process sessions, logs and local shortcuts.
- Operator source or documents containing the runtime user's home-directory
  name or identifiers supplied through a private local JSON file.

Generic system paths and artificial test paths such as `C:/OriginalAnno` are
code examples, not the user's machine path. Exact installed game paths in
selected documentation or noncompiled scripts are replaced by an explicit
environment placeholder. All transformations are recorded in the provenance.
Possible credential material stops the import instead of being published.

The public `world_patch.json` is explicitly an **uncertified source snapshot**.
It replaces the original root with `${ANNO1503_GAME_DIR}`, omits duplicated raw
live evidence and clears current-package gameplay claims. Its provenance keeps
the original specification/runtime fingerprints and the historical fact that
the frozen baseline had actual game tests. The copied `resolve_copy` function
refuses installation or activation from this source-only specification. The
launcher source also keeps its original frozen-specification pin, so it cannot
silently activate this changed source snapshot.

## Local preservation

Running the import with `--copy-baselines` additionally copies all three complete
current packages into `.local/baselines/`, excluding only caches and compiler
intermediates. This private copy retains native payloads, complete local assets,
the original metadata and historical evidence. It also preserves both current
release ZIPs with their exact known fingerprints. A local manifest checks every
copied file against its source; its machine paths stay inside ignored `.local/`.
The installed game itself is not copied again by this importer.

No Game Settings option, Food gameplay rule, native engine byte or save is
changed by this migration. Importing existing test results does not establish
a new repository build or a new actual game test.

## Building outside the game directory

The native runtime can be built from its preserved source closure with an
explicit external compiler-tools path. Legacy payload reconstruction and audit
scripts still have historical assumptions about adjacent game inputs, complete
evidence and prior releases. Use repository staging/build tools with explicit
local input paths. Do not run legacy installers or infer portability from a
source import. A clean public clone deliberately contains no Ubisoft modules,
complete islands or user test corpus.

Run the importer only against a prepared, new destination:

```powershell
python -B tools/import_legacy.py --game-dir "PATH_TO_INSTALLED_ANNO" --repo-dir "PATH_TO_THIS_REPOSITORY" --copy-baselines --private-identifiers-file .local/setup/import_private_identifiers.json
```

It refuses an existing `legacy/` tree or existing baseline destination instead
of overwriting it. All writes are confined to the explicit repository.
The optional private-identifiers file is a JSON list of strings and must remain
beneath ignored `.local/`; its contents are never copied into public provenance
or printed. The importer source itself contains no personal identifier list.
