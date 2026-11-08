This is a developer fixture, not a game launcher.

Extract the combined development package anywhere under the original Anno
1503 game folder, then run:
  python -B developer/settlement_owner_fix/test_scene_sanitization.py

Requires Python 3.10+ and the existing development compiler at:
  WorldSettings_Work/_tools/ziglang/zig.exe

The fixture locates the original game folder through its ancestor folders.
All scene, failure and source-comparison inputs are included locally under
fixture_data and bound by FIXTURE_INPUTS.json. It compiles only the fixture
DLL into its own _build directory, exercises supplied memory buffers and
writes scene_sanitization_results.json. It never attaches to a game process,
installs a mod, or changes a game file or backup.

Seven automated tests include twelve difficulty/faction combinations, the
exact failed Easy Venetian city collision, preservation of controller bytes,
extended fields, thirteen malformed states and five capacity failures. These
checks do not establish actual game behavior or Venetian trade/navigation.
