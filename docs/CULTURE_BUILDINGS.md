# Culture Buildings prototype

**Ornaments → Cultural Buildings** opens ten submenus for Venetian, African,
Moorish, Bedouin, Mongolian, Aztec, Inuit, Native American, Polynesian and Pirate
architecture. The prototype offers 157 build choices, including 20 residence
options and 137 decorations. It uses the Add-On single-player construction menu
in the inspected 64-bit History Edition build.

Each culture has a working Pioneer residence that can advance through Settlers,
Citizens and Merchants under the normal housing rules. A separate Aristocrat
option uses the normal Aristocrat unlock. Some tiers share a façade. Other
culture buildings, including markets and workshops, are decorative. Bridges,
piers and culture pieces that require fishing or ice placement are outside the
prototype.

Every button has a thumbnail generated from the installed game’s corresponding
sprite. A small gold diamond marks Aristocrat residences. The build generates
the artwork locally from your own game files.

## Build a separate test copy

Use a checkout of the repository on 64-bit Windows with Python 3.10 or newer and
the supported Ubisoft Connect installation. From the repository checkout,
install the optional icon-building dependency.

```powershell
python -m pip install -e ".[culture-buildings]"
```

Set `$originalGame` to the original registered Anno installation and
`$cultureCopy` to a new folder outside the game. For Food Overhaul Off, set
`$donorGame` to the original installation with the exact supported stock files
or a verified game copy with those files.

```powershell
python -m anno1503_overhaul.culture_buildings build --original-game "$originalGame" --donor "$donorGame" --food-overhaul off --copy "$cultureCopy"
python -m anno1503_overhaul.culture_buildings verify --copy "$cultureCopy"
```

For Food Overhaul On, use `--food-overhaul on` and set `$donorGame` to a managed
Food 0.6-only copy built from the same original installation. The builder
accepts the reviewed Food 0.6 builds with the original and combined housing
rules, including their city supply statistics fix variants. It applies the fix
to the new Food On copy when needed.

Close running Anno sessions, then start the copy through the regular Ubisoft
Connect handoff. Use an Add-On single-player game to open the new submenus.

```powershell
python -m anno1503_overhaul.culture_buildings launch --copy "$cultureCopy"
```

Keep saves that contain culture buildings with a compatible Culture Buildings
copy. Use separate saves for each Food profile.

## Validation

- Local builds of both Food profiles match the tested prototype archives, menus
  and icon atlases. The palette, frame-size and catalogue tests use synthetic
  fixtures and run without game files.
- With Food Overhaul off, the Moorish Pioneer house filled to eight residents
  and survived save and reload with the minarets. The Moorish icons were also
  checked in-game after a restart.
- With Food Overhaul on, a Pirate residence gained residents and survived save
  and reload with its watchtower. A prepared save with houses from all ten
  cultures reloaded with occupied households.
- In a bounded Food On replay, the city statistics fix let a previously failing
  save run past the reproduced exit and complete another save and reload. The
  precise exit site and long-session behavior remain unverified. Multiplayer
  and World Settings runtime activation are outside the tested scope.
