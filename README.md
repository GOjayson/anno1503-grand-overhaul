# Anno 1503 Grand Overhaul

A modular mod for **Anno 1503 History Edition**. The goal is to give players more control over their worlds and, over time, expand the game's economy, AI and education systems.

The current focus is **World Settings** for single-player endless games: choose how a world is created, entirely inside the game. The Food overhaul is a separate, optional feature. Better AI, local multiplayer and the Knowledge overhaul are future work.

## World Settings

Before an endless game starts, choose **Original game** or **Custom world**.

- **Original game** uses Anno's own setup and generation. World Settings choices are ignored.
- **Custom world** opens the mod's setup menu. Preview your map, regenerate it, enter a seed or load a favourite preset.
- Tutorials, campaigns and scenarios use their normal start route.

Custom-world options include:

- World and island sizes, island count, spacing, layout and random island rotation.
- Climate preferences and minimum/maximum climate counts; preferences for different island shapes.
- Plant fertility, minerals, resource distribution and balanced starting positions.
- Starting money, fleet and cargo; up to three ordinary AI opponents and their aggression.
- Individual native cultures, Pirates, Venetians, pirate activity and neutral merchant traffic.
- Terra incognita, map visibility and enemy activity visibility, including remembered towns.
- Individual disaster switches, frequencies and supported severity choices.

**Huge 2048 × 2048 worlds remain experimental.** Eight AI players and local-host multiplayer are research goals, not supported features.

## Install the Windows beta

Download the Windows beta ZIP from [Releases](https://github.com/GOjayson/anno1503-grand-overhaul/releases).

1. Extract the **whole beta ZIP** outside your Anno installation.
2. Close Anno, then open **Anno1503OverhaulSetup.exe**.
3. Check the detected **Original game folder** and choose a separate **Modded copy folder**. For the public World Settings beta, keep World Settings selected and Food unchecked.
4. Click **Check installation**, then **Install selected features**.
5. Use the new desktop shortcut or **Start with World Settings**. The launcher enables the mod automatically; world choices stay inside Anno.

The Windows bundle includes its preparation tools, so users do not need a separate Python or compiler installation. It builds from the player's own supported game files. Anno's executable, game DLLs, islands and saves are not included. Bundled tool licenses are listed in [third-party notices](docs/THIRD_PARTY_NOTICES.md).

A legitimate History Edition installation and normal Ubisoft Connect authentication are required. The launcher briefly needs a normal client session before handing off to the modded copy; it hides that temporary menu before opening the second one. Only the modded game remains after startup.

The beta currently targets the inspected **64-bit History Edition build with Dutch scene data**. Other localizations still need verification; changing only the interface language is not a compatibility check.

## Food and restoration

Food is optional. Leave it unchecked to keep the standard food economy. The public World Settings beta prepares World-only installations. Food 0.5 remains experimental, and selecting Food together with World Settings still requires the preserved matching development inputs; the public bundle does not prepare that combination. The setup checks the selected inputs and never silently enables Food.

To remove installed features, close Anno, select your modded copy and click **Restore original game**. Your original Ubisoft installation, saves and existing backups are preserved. Restore before changing the installed feature combination.

Saves made with custom worlds can require the mod even after restoration, particularly Huge worlds. Keep a compatible installation for those saves.

## Beta status and help

This is a beta, not a claim that every map combination or long campaign has been tested. Automated checks, observed game runs and untested behaviour are recorded separately.

- [Installation details and troubleshooting](docs/INSTALLER.md)
- [Changelog](docs/CHANGELOG.md)
- [World options and validation](docs/WORLD_ENVIRONMENT_OPTIONS.md)
- [Island catalogue audit](docs/WORLD_ISLAND_CATALOGUE.md)
- [Report a problem or suggest a feature](https://github.com/GOjayson/anno1503-grand-overhaul/issues/new/choose)
- [Accessibility and reporting barriers](ACCESSIBILITY.md)
- [Report a security vulnerability privately](SECURITY.md)

When reporting a problem, include the mod version, selected features, game mode, what you expected and what happened. Keep a copy of an affected save. Do not post Ubisoft startup arguments, account information or original game files.

## Contributors

Development happens in this repository, outside the installed game. Read [CONTRIBUTING.md](CONTRIBUTING.md), the [Code of Conduct](CODE_OF_CONDUCT.md) and [AGENTS.md](AGENTS.md). For source setup and the earlier implementation record, see [development history](docs/DEVELOPMENT_HISTORY.md).

Only mod source, tests, authored assets and documentation belong in the public repository. Native game files and local build/test data stay private.

## License

Original project code, documentation and authored artwork are available under the [MIT License](LICENSE), except where a separate license is identified. Third-party components and the adapted Code of Conduct retain their own terms; see [third-party notices](docs/THIRD_PARTY_NOTICES.md).

This license grants no rights to Ubisoft's game files, assets or trademarks. Anno 1503 Grand Overhaul is an independent community project and requires a supported game installation.
