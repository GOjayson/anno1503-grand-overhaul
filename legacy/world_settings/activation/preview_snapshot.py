"""Decode a bounded read-only snapshot of the game-owned map preview."""
import hashlib
import struct

SETTINGS_FIELDS = ["size", "difficulty", "islandSize", "islandCount", "spacing", "aiCount",
                   "cultures", "factions", "startingMoney", "startingFleet", "aiDifficulty",
                   "plantFertility", "mineralFertility", "worldSize"]
ISLAND_FIELDS = ["id", "x", "y", "width", "height", "templateIndex", "cropMask",
                 "mineralMask", "cultures", "climate"]
SNAPSHOT_SIZE = 16+56+128*40
SETTINGS_SIZE = 56
ROWS_OFFSET = 16+SETTINGS_SIZE
CATALOGUE_COUNT = 444
STATES = ["absent", "ready", "staged", "committed", "cancelled-or-failed"]


def decode(data):
    if len(data) != SNAPSHOT_SIZE:
        raise ValueError("Preview snapshot size differs from the inspected ABI")
    size, state, seed, count = struct.unpack_from("<4I", data)
    if size != SNAPSHOT_SIZE or state >= len(STATES) or count > 128:
        raise ValueError("Invalid preview snapshot envelope")
    settings = dict(zip(SETTINGS_FIELDS, struct.unpack_from("<I5i2I6i", data, 16)))
    if state == 0:
        if count or seed or any(settings.values()) or any(data[ROWS_OFFSET:]):
            raise ValueError("Absent preview contains an unexpected plan")
    elif (not 1 <= count <= 128 or settings["size"] != SETTINGS_SIZE or settings["islandCount"] != count
          or settings["worldSize"] not in (256,512,1024,2048)):
        raise ValueError("Preview settings and island count disagree")
    rows = []
    for i in range(count):
        row = dict(zip(ISLAND_FIELDS, struct.unpack_from("<10I", data, ROWS_OFFSET+i*40)))
        if (row["id"] != i or row["templateIndex"] >= CATALOGUE_COUNT or row["climate"] >= 6
                or not 0 < row["width"] <= 256 or not 0 < row["height"] <= 256
                or row["x"] % 8 or row["y"] % 8 or row["x"]+row["width"] > settings["worldSize"]
                or row["y"]+row["height"] > settings["worldSize"]):
            raise ValueError("Invalid preview island bounds or identity")
        rows.append(row)
    if any(data[ROWS_OFFSET+count*40:]):
        raise ValueError("Unexpected rows beyond the preview island count")
    return dict(state=state, state_name=STATES[state], seed=seed, count=count,
                settings=settings, islands=rows,
                plan_sha256=hashlib.sha256(data[ROWS_OFFSET:ROWS_OFFSET+count*40]).hexdigest(),
                snapshot_sha256=hashlib.sha256(data).hexdigest(),
                scope="Read-only exact menu preview; committed state requires separate live game/save evidence.")
