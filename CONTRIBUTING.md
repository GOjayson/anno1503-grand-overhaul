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

The new feature selector currently prepares profiles only. Changes must not
present unavailable research modules as installable or hide dependencies from
the user. World-specific settings belong inside Anno.
