"""Bounded read-only diagnostics for the expanded in-game settings ABI."""
import hashlib
import struct

SETTINGS_FIELDS = ['size', 'difficulty', 'islandSize', 'islandCount', 'spacing', 'aiCount',
    'cultures', 'factions', 'startingMoney', 'startingFleet', 'aiDifficulty',
    'plantFertility', 'mineralFertility', 'worldSize', 'mapSeed', 'startClimate', 'startIsland',
    'cargoMode', 'cargoTools', 'cargoWood', 'cargoFood', 'climateBalance', 'layoutStyle', 'disasters',
    'fairStarts', 'startSeparation', 'resourceDistribution', 'guaranteeBasics',
    'mapVisibility', 'enemyVisibility', 'pirateFrequency', 'pirateStrength', 'merchantFrequency',
    'islandVariety', 'minPolar', 'maxPolar', 'minTemperate', 'maxTemperate', 'minTropical', 'maxTropical',
    'disasterMask', 'disasterFrequency', 'disasterSeverity', 'islandRotation']
SETTINGS_FIELDS += [f'{name}{index}' for name, count in
                    (('climateMin', 6), ('climateMax', 6),
                     ('islandSizeMin', 18), ('islandSizeMax', 18))
                    for index in range(count)]
SETTINGS_FORMAT = '<I5i2I6iI25i3Ii48i'
CLIMATES = ('Polar', 'Tundra', 'Northern', 'Prairie', 'Jungle', 'Steppe')
ISLAND_FIELDS = ['id', 'x', 'y', 'width', 'height', 'templateIndex', 'cropMask', 'mineralMask', 'cultures', 'climate', 'rotation']
SETTINGS_SIZE = 368
ROWS_OFFSET = 16 + SETTINGS_SIZE
ISLAND_SIZE = 44
SNAPSHOT_SIZE = ROWS_OFFSET + 128 * ISLAND_SIZE
CATALOGUE_COUNT = 444
STATES = ['absent', 'ready', 'staged', 'committed', 'cancelled-or-failed']


def _quota_limits(settings, count):
    """Independently check the nested size/climate/legacy-group intervals."""
    lower, upper = [], []
    for climate in range(6):
        minimum, maximum = settings[f'climateMin{climate}'], settings[f'climateMax{climate}']
        if not 0 <= minimum <= maximum <= 128 or maximum < 1:
            raise ValueError('Each climate must permit an island for essential resources.')
        sizes = [(settings[f'islandSizeMin{climate*3+size}'],
                  settings[f'islandSizeMax{climate*3+size}']) for size in range(3)]
        if any(not 0 <= low <= high <= 128 for low, high in sizes):
            raise ValueError('Invalid per-climate island size limits.')
        low, high = max(1, minimum, sum(v[0] for v in sizes)), min(maximum, sum(v[1] for v in sizes))
        if low > high:
            raise ValueError('Island size limits do not fit their climate limits.')
        lower.append(low)
        upper.append(high)
    group_lower, group_upper = [], []
    for group, name in enumerate(('Polar', 'Temperate', 'Tropical')):
        minimum, maximum = settings['min'+name], settings['max'+name]
        if not 0 <= minimum <= maximum <= 128:
            raise ValueError('Invalid legacy climate group limits.')
        low = max(minimum, sum(lower[group*2:group*2+2]))
        high = min(maximum, sum(upper[group*2:group*2+2]))
        if low > high:
            raise ValueError('Independent climates conflict with legacy climate group limits.')
        group_lower.append(low)
        group_upper.append(high)
    if not sum(group_lower) <= count <= sum(group_upper):
        raise ValueError('Climate and size limits cannot accommodate the island count.')


def decode(data):
    if len(data) != SNAPSHOT_SIZE:
        raise ValueError('World options snapshot differs from the inspected ABI.')
    size, state, seed, count = struct.unpack_from('<4I', data)
    if size != SNAPSHOT_SIZE or state >= len(STATES) or count > 128:
        raise ValueError('Invalid World options snapshot envelope.')
    settings = dict(zip(SETTINGS_FIELDS, struct.unpack_from(SETTINGS_FORMAT, data, 16)))
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
          or not 0 <= settings['mapVisibility'] <= 2 or settings['enemyVisibility'] not in (0, 1)
          or any(not 0 <= settings[key] <= 2 for key in ('pirateFrequency', 'pirateStrength', 'merchantFrequency'))
          or not 0 <= settings['islandVariety'] <= 2
          or settings['disasterMask'] & ~31 or settings['disasterFrequency'] & ~1023 or settings['disasterSeverity'] & ~1023
          or any((settings[key] >> (i*2) & 3) > 2 for key in ('disasterFrequency', 'disasterSeverity') for i in range(5))
          or settings['disasterSeverity'] & 15 != 5
          or settings['islandRotation'] not in (0, 1)
          or settings['mapVisibility'] == 0 and settings['startIsland'] >= 0
          or any(not 0 <= settings[key] <= 400 for key in ('cargoTools', 'cargoWood', 'cargoFood'))):
        raise ValueError('World options settings and preview disagree.')
    if state:
        _quota_limits(settings, count)
    if state and settings['cargoMode']:
        used = sum((settings[key] + 49) // 50 for key in ('cargoTools', 'cargoWood', 'cargoFood'))
        if used > (8 if settings['startingFleet'] == 1 else 4):
            raise ValueError('Preview cargo exceeds trade-ship holds.')
    islands = []
    for index in range(count):
        row = dict(zip(ISLAND_FIELDS, struct.unpack_from('<11I', data, ROWS_OFFSET + index * ISLAND_SIZE)))
        gap, world = settings['spacing'], settings['worldSize']
        if (row['id'] != index or row['templateIndex'] >= CATALOGUE_COUNT or row['climate'] >= 6
                or row['rotation'] > 3 or not settings['islandRotation'] and row['rotation']
                or not 0 < row['width'] <= 256 or not 0 < row['height'] <= 256
                or row['x'] % 8 or row['y'] % 8 or row['x'] < gap or row['y'] < gap
                or row['x'] + row['width'] + gap > world or row['y'] + row['height'] + gap > world):
            raise ValueError('Invalid preview island identity, grid or bounds.')
        for other in islands:
            if not (row['x'] + row['width'] + gap <= other['x'] or other['x'] + other['width'] + gap <= row['x']
                    or row['y'] + row['height'] + gap <= other['y'] or other['y'] + other['height'] + gap <= row['y']):
                raise ValueError('Preview islands overlap or violate spacing.')
        islands.append(row)
    if any(data[ROWS_OFFSET + count * ISLAND_SIZE:]):
        raise ValueError('Unexpected data beyond the preview island count.')
    if state:
        climate_counts = [sum(row['climate'] // 2 == group for row in islands) for group in range(3)]
        if any(not settings['min'+group] <= climate_counts[i] <= settings['max'+group]
               for i, group in enumerate(('Polar', 'Temperate', 'Tropical'))):
            raise ValueError('Preview island climates violate the selected limits.')
        counts = [sum(row['climate'] == climate for row in islands) for climate in range(6)]
        sizes = [0] * 18
        for row in islands:
            width = max(row['width'], row['height'])
            size = 0 if width < 128 else 1 if width == 128 else 2
            sizes[row['climate']*3+size] += 1
        if any(not max(1, settings[f'climateMin{climate}']) <= counts[climate] <= settings[f'climateMax{climate}']
               for climate in range(6)):
            raise ValueError('Preview islands violate the independent climate limits.')
        if any(not settings[f'islandSizeMin{cell}'] <= sizes[cell] <= settings[f'islandSizeMax{cell}']
               for cell in range(18)):
            raise ValueError('Preview islands violate the per-climate size limits.')
    return dict(state=state, state_name=STATES[state], seed=seed, count=count, settings=settings,
                islands=islands, plan_sha256=hashlib.sha256(data[ROWS_OFFSET:ROWS_OFFSET + count * ISLAND_SIZE]).hexdigest(),
                snapshot_sha256=hashlib.sha256(data).hexdigest(),
                scope='Exact cached preview; loaded-world and save evidence remain separate.')
