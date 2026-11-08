"""Bounded read-only diagnostics for the expanded in-game settings ABI."""
import hashlib
import struct

SETTINGS_FIELDS = ['size', 'difficulty', 'islandSize', 'islandCount', 'spacing', 'aiCount',
    'cultures', 'factions', 'startingMoney', 'startingFleet', 'aiDifficulty',
    'plantFertility', 'mineralFertility', 'worldSize', 'mapSeed', 'startClimate', 'startIsland',
    'cargoMode', 'cargoTools', 'cargoWood', 'cargoFood', 'climateBalance', 'layoutStyle', 'disasters',
    'fairStarts', 'startSeparation', 'resourceDistribution', 'guaranteeBasics']
ISLAND_FIELDS = ['id', 'x', 'y', 'width', 'height', 'templateIndex', 'cropMask', 'mineralMask', 'cultures', 'climate']
SETTINGS_SIZE = 112
ROWS_OFFSET = 16 + SETTINGS_SIZE
SNAPSHOT_SIZE = ROWS_OFFSET + 128 * 40
CATALOGUE_COUNT = 444
STATES = ['absent', 'ready', 'staged', 'committed', 'cancelled-or-failed']


def decode(data):
    if len(data) != SNAPSHOT_SIZE:
        raise ValueError('World options snapshot differs from the inspected ABI.')
    size, state, seed, count = struct.unpack_from('<4I', data)
    if size != SNAPSHOT_SIZE or state >= len(STATES) or count > 128:
        raise ValueError('Invalid World options snapshot envelope.')
    settings = dict(zip(SETTINGS_FIELDS, struct.unpack_from('<I5i2I6iI13i', data, 16)))
    if state == 0:
        if count or seed or any(settings.values()) or any(data[ROWS_OFFSET:]):
            raise ValueError('An absent preview contains data.')
    elif (not 1 <= count <= 128 or settings['size'] != SETTINGS_SIZE
          or settings['mapSeed'] != seed or settings['islandCount'] != count
          or settings['worldSize'] not in (256, 512, 1024, 2048)
          or not 0 <= settings['difficulty'] <= 2 or not 0 <= settings['islandSize'] <= 4
          or not 0 <= settings['spacing'] <= 256 or not 0 <= settings['aiCount'] <= 3
          or settings['cultures'] & ~255 or settings['factions'] & ~3
          or settings['startingMoney'] not in (10000, 30000, 50000, 80000, 100000)
          or not 0 <= settings['startingFleet'] <= 2 or not 0 <= settings['aiDifficulty'] <= 3
          or not 0 <= settings['plantFertility'] <= 3 or not 0 <= settings['mineralFertility'] <= 3
          or not -1 <= settings['startClimate'] <= 5 or not -1 <= settings['startIsland'] < count
          or settings['cargoMode'] not in (0, 1) or settings['disasters'] not in (0, 1)
          or not 0 <= settings['climateBalance'] <= 3 or not 0 <= settings['layoutStyle'] <= 2
          or settings['fairStarts'] not in (0, 1) or settings['guaranteeBasics'] not in (0, 1)
          or not 0 <= settings['startSeparation'] <= 2 or not 0 <= settings['resourceDistribution'] <= 2
          or any(not 0 <= settings[key] <= 400 for key in ('cargoTools', 'cargoWood', 'cargoFood'))):
        raise ValueError('World options settings and preview disagree.')
    if state and settings['cargoMode']:
        used = sum((settings[key] + 49) // 50 for key in ('cargoTools', 'cargoWood', 'cargoFood'))
        if used > (8 if settings['startingFleet'] == 1 else 4):
            raise ValueError('Preview cargo exceeds trade-ship holds.')
    islands = []
    for index in range(count):
        row = dict(zip(ISLAND_FIELDS, struct.unpack_from('<10I', data, ROWS_OFFSET + index * 40)))
        gap, world = settings['spacing'], settings['worldSize']
        if (row['id'] != index or row['templateIndex'] >= CATALOGUE_COUNT or row['climate'] >= 6
                or not 0 < row['width'] <= 256 or not 0 < row['height'] <= 256
                or row['x'] % 8 or row['y'] % 8 or row['x'] < gap or row['y'] < gap
                or row['x'] + row['width'] + gap > world or row['y'] + row['height'] + gap > world):
            raise ValueError('Invalid preview island identity, grid or bounds.')
        for other in islands:
            if not (row['x'] + row['width'] + gap <= other['x'] or other['x'] + other['width'] + gap <= row['x']
                    or row['y'] + row['height'] + gap <= other['y'] or other['y'] + other['height'] + gap <= row['y']):
                raise ValueError('Preview islands overlap or violate spacing.')
        islands.append(row)
    if any(data[ROWS_OFFSET + count * 40:]):
        raise ValueError('Unexpected data beyond the preview island count.')
    return dict(state=state, state_name=STATES[state], seed=seed, count=count, settings=settings,
                islands=islands, plan_sha256=hashlib.sha256(data[ROWS_OFFSET:ROWS_OFFSET + count * 40]).hexdigest(),
                snapshot_sha256=hashlib.sha256(data).hexdigest(),
                scope='Exact cached preview; loaded-world and save evidence remain separate.')
