# Contributing

Work in this repository, outside your installed game. Read `AGENTS.md` and the
architecture/feature-status documents before changing native code or installers.

Keep proposals and research targets separate from working features. Provide
reproducible evidence before raising player limits, changing native layouts or
claiming network compatibility. Use exact History Edition module fingerprints;
classic-version patch addresses require independent verification.

Use `.local/` for licensed game inputs, compiler tools, build candidates and
private validation material. Do not commit full game files, native saves,
credentials, raw operator logs or machine-specific paths. Run the repository
content check before pushing.

For new platform code, add meaningful portable tests and run:

```console
python -B -m unittest discover -s tests -v
python -B tools/check_repository.py
```

Keep imported compiled source fingerprints intact during the initial migration.
Later feature changes should explicitly update their provenance and validation
scope. Never mark historical runtime evidence as a test of a changed binary.

Before integration testing, preserve existing backups and saves and use an
independent marked game copy. Installation/restoration requires a closed game;
unknown inputs and conflicting changes must fail before publication. Native
activation must retain its process/menu and transactional safety guards.

The modular installer supports Food alone and Food with World Settings on an
independent managed copy. Food-only preparation must work from public source
without private World payloads. The combined selection must retain its
explicit Food and Ubisoft source-installation dependency. Read
`docs/INSTALLER.md` before changing package, copy or restoration behavior.

Keep **Check installation** separate from publication and revalidate inputs
before installation. Retain original-file fingerprints, one composed journal,
exclusive operation locks, changed-file refusal and backup generations. Do
not convert a historical "restore preceding setup" journal into a vanilla
claim or accept an arbitrary provider's executable helpers. Restore must
remain possible from retained backups without a prepared package.

Changes must not present unavailable research modules as installable or hide
dependencies from the user. World-specific settings belong inside Anno.
