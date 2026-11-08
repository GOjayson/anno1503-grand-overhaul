Development checks for starting money and fleets

All actual player configuration is in the in-game World Settings screen.
These scripts inspect/test configuration; they do not configure a game.

Production stage test (from the original game folder):
  python -B WorldSettings_Work/anno1503_food_world_dev4/developer/start_options/economy/test_production_stage.py
Loads the final production runtime, checks its AMD64 architecture, 44-byte ABI
and all build source hashes, stages/inspects/deletes 180 temporary scenes on
the marked game copy, tests 9 invalid options and rejects a second pending stage.
No game process or UI is started. All original player bytes/order are checked
except selected human money/main-ship fields, CPU suspension, disabled special
players and the previously verified map-bound Venetian city removal.

Saved-state inspector synthetic tests (standard library only):
  python -B WorldSettings_Work/anno1503_food_world_dev4/developer/start_options/economy/test_save_inspector.py
Uses 45 captured production API scene-player records and explicitly synthetic
assigned IDs/merged player states; checks 45 valid shapes and 405 corruptions.
These fixtures are not actual game saves. No fixture DLL is shipped or required.

Actual save inspection (read-only; choose the options that were selected):
  python -B inspect_start_save.py SAVE --difficulty easy --money 50000 --fleet war
For a progressed save, add --observed. This reports current cash/coordinates,
requires cash between zero and the selected start, and requires boats outside
all saved island rectangles and in world bounds. Count/classes/full health,
cannons and per-boat cargo remain exact. Initial cash and coordinate equality
are explicitly not claimed; they require the prior in-game runtime certificate.
The default keeps exact initial-money and spawn-coordinate checks.

Accepts native SCHIFF and SCHI64 records. Requires exact initial cash, ship
count/types/positions, full health, equipped cannons and per-boat cargo. A
progressed save can fail because ships/cargo/cash changed after the initial
runtime certificate. This does not certify navigation, combat, diplomacy or
Food production. No actual game run is claimed by these automated reports.

The JSON/native disassembly reports preserve local development evidence.
The complete compiled C sources are also under developer/source and bound by
the runtime build_result.json. SOURCE_SHA256.json fingerprints this folder.
