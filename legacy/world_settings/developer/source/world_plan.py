"""Development layout planner. It does not produce a playable ANNO world.

The catalogue is extracted from this installation, not another game version.
Layout success proves only count/size/culture selection and rectangle spacing.
The native resource allocator and player/settlement import require a separate
verified integration before these layouts can be offered by the game's Start.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'world_data'))
from scene_catalogue import CULTURES, geometry_errors


class PlanError(ValueError):
    pass


class IntegrationUnverified(PlanError):
    pass


@dataclass(frozen=True)
class Settings:
    difficulty: str = 'medium'
    island_size: str = 'mixed'
    island_count: int = 24
    spacing: int = 16
    ai_count: int = 0
    cultures: frozenset[str] = frozenset(CULTURES)

    def validate(self):
        if self.difficulty not in {'easy', 'medium', 'hard'}:
            raise PlanError('Unknown difficulty')
        if self.island_size not in {'small', 'medium', 'large', 'mixed'}:
            raise PlanError('Unknown island size')
        # Input safety bounds, not claims about engine capacity.
        if type(self.island_count) is not int or not 1 <= self.island_count <= 128:
            raise PlanError('Development planner accepts 1..128 islands')
        if type(self.spacing) is not int or not 0 <= self.spacing <= 256:
            raise PlanError('Development planner accepts 0..256 tiles of spacing')
        if type(self.ai_count) is not int or self.ai_count != 0:
            raise PlanError('Additional-food AI planning has not been implemented')
        if not isinstance(self.cultures, frozenset) or not self.cultures <= set(CULTURES):
            raise PlanError('Unknown native culture')
        if len(self.cultures) > self.island_count:
            raise PlanError('Island count is smaller than enabled culture count')


def size_class(template):
    dimensions = (template['width'], template['height'])
    # These are observed HE assets: 64/80, 128 and 256 tiles. Labels are a mod
    # policy, not a presumed classic-version engine enumeration.
    if dimensions in {(64, 64), (80, 80)}:
        return 'small'
    if dimensions == (128, 128):
        return 'medium'
    if dimensions == (256, 256):
        return 'large'
    raise PlanError(f'Uncatalogued template dimensions: {dimensions}')


def verify_template(root, template):
    root = Path(root).resolve()
    path = (root / template['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise PlanError('Template path is absent or leaves the inspected game')
    if hashlib.sha256(path.read_bytes()).hexdigest() != template['sha256']:
        raise PlanError('Template differs from the inspected catalogue')


def _select(settings, catalogue, rng):
    candidates = [t for t in catalogue['templates']
                  if set(t['cultures']) <= settings.cultures
                  and (settings.island_size == 'mixed' or size_class(t) == settings.island_size)]
    selected = []
    represented = set()
    for culture in CULTURES:
        if culture not in settings.cultures or culture in represented:
            continue
        options = [t for t in candidates if culture in t['cultures']]
        if not options:
            raise PlanError(f'No {settings.island_size} template contains {culture}')
        template = rng.choice(options)
        selected.append(template)
        represented.update(template['cultures'])
    # Filler islands must not silently enable or duplicate native settlements.
    empty = [t for t in candidates if not t['cultures']]
    if len(selected) < settings.island_count and not empty:
        raise PlanError('No uninhabited templates match this size')
    while len(selected) < settings.island_count:
        selected.append(rng.choice(empty))
    # The size setting is independent of difficulty, including RNG consumption.
    return selected


def _pack(selected, width, height, spacing, rng):
    placed = []
    # Bottom-left packing against every existing rectangle, with randomized
    # tie-breaking. Every result is independently checked before it is returned.
    ordered = sorted(enumerate(selected), key=lambda it: -it[1]['width'] * it[1]['height'])
    for ident, template in ordered:
        xs = {spacing, *(p['x'] + p['width'] + spacing for p in placed)}
        ys = {spacing, *(p['y'] + p['height'] + spacing for p in placed)}
        positions = [(x, y) for x in sorted(xs) for y in sorted(ys)]
        rng.shuffle(positions)
        positions.sort(key=lambda pos: (pos[1] + template['height'], pos[0] + template['width']))
        for x, y in positions:
            if x + template['width'] > width - spacing or y + template['height'] > height - spacing:
                continue
            item = dict(id=ident, x=x, y=y, width=template['width'], height=template['height'],
                        path=template['path'], sha256=template['sha256'],
                        cultures=template['cultures'], climate_index=template['climate_index'])
            if not geometry_errors(placed + [item], width, height, spacing):
                placed.append(item)
                break
        else:
            return None
    return sorted(placed, key=lambda p: p['id'])


def plan_layout(settings, catalogue, seed=0, width=1024, height=1024):
    settings.validate()
    if type(width) is not int or type(height) is not int or (width, height) != (1024, 1024):
        raise PlanError('Only the observed 1024x1024 development layout is supported')
    if catalogue.get('cultures') != list(CULTURES) or catalogue.get('failures'):
        raise PlanError('Incomplete or incompatible catalogue')
    rng = random.Random(seed)
    for _ in range(32):
        selected = _select(settings, catalogue, rng)
        result = _pack(selected, width, height, settings.spacing, rng)
        if result is not None:
            errors = geometry_errors(result, width, height, settings.spacing)
            if errors:
                raise PlanError('; '.join(errors))
            represented = {c for p in result for c in p['cultures']}
            if represented != settings.cultures:
                raise PlanError('Native culture selection mismatch')
            return dict(width=width, height=height, islands=result,
                        difficulty=settings.difficulty,
                        geometry_validated=True, resources_validated=False,
                        settlement_import_validated=False, playable=False)
    raise PlanError('Requested island sizes/count/spacing could not be packed; reduce count or spacing')


def require_playable_world(plan):
    # There is deliberately no flag or external config switch that can promote
    # a geometric plan to an engine-validated playable world.
    raise IntegrationUnverified(
        'Native resource coverage, settlement/player import, ship spawn positions, '
        'and every endless-start path are not verified; game start is blocked')


def load_catalogue(path=None):
    path = path or Path(__file__).resolve().parent / 'world_data' / 'catalogue.json'
    return json.loads(Path(path).read_text(encoding='utf-8'))
