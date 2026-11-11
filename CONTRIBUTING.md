# Contributing

Follow the [Code of Conduct](CODE_OF_CONDUCT.md). Use the [issue chooser](https://github.com/GOjayson/anno1503-grand-overhaul/issues/new/choose)
for bugs, feature requests or accessibility barriers. Report vulnerabilities
through the [security policy](SECURITY.md), without posting sensitive details.

By submitting original work for inclusion, you agree to license it under the
project's [MIT License](LICENSE). Existing third-party materials retain their
own terms; identify their source and license, and only submit material you have
the right to contribute. The adapted Code of Conduct has its separate terms
listed in [third-party notices](docs/THIRD_PARTY_NOTICES.md).

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

The modular installer exposes independent Food and World choices on a managed
copy. Food-only preparation must work from public source without private World
payloads. Preserve the existing combined profile's exact compatibility contract.
World-only uses its separate stock host, runtime and engine-plan pins, with no
Food diet, market or native host changes. Do not make the checkbox independent
while retaining Food semantics underneath it. Read
`docs/INSTALLER.md` before changing package, copy or restoration behavior.

Keep **Check installation** separate from publication and revalidate inputs
before installation. Retain original-file fingerprints, one composed journal,
exclusive operation locks, changed-file refusal and backup generations. Do
not convert a historical "restore preceding setup" journal into a vanilla
claim or accept an arbitrary provider's executable helpers. Restore must
remain possible from retained backups without a prepared package.

Changes must not present unavailable research modules as installable or hide
dependencies from the user. World-specific settings belong inside Anno.
