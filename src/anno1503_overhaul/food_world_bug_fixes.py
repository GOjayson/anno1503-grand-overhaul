"""Exact optional asset recipe for Food 0.6 + World Settings packages.

The reviewed transforms read supported originals and produce fingerprints only.
The source installer still owns all edits and the common restoration journal.
This module is also staged with its dependencies for the isolated World launcher.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .ambient_sound import ambient_sound_assets
from .bug_fixes import king_of_ore_assets


VERSION = '1.2'


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def recipe(source: Path) -> dict:
    """Derive the complete installed-language recipe from checked stock assets."""
    quests = king_of_ore_assets(source)
    sounds = ambient_sound_assets(source, (quest.locale for quest in quests))
    fingerprints = lambda path, before, after: dict(
        path=path, before_size=len(before), before_sha256=_sha(before),
        after_size=len(after), after_sha256=_sha(after), offset=None)
    files = [fingerprints(quest.quest_path, quest.before, quest.after) for quest in quests]
    files.extend(fingerprints(sound.path, sound.before, sound.after) for sound in sounds)
    names = [entry['path'].casefold() for entry in files]
    if len(set(names)) != len(names):
        raise ValueError('Optional Bug Fixes contains overlapping asset paths.')
    return dict(version=VERSION,
                quests=[dict(locale=quest.locale, path=quest.quest_path,
                             before_sha256=_sha(quest.before), after_sha256=_sha(quest.after),
                             scene_path=quest.scene_path, scene_sha256=quest.scene_sha256)
                        for quest in quests],
                sounds=[dict(path=sound.path, before_sha256=_sha(sound.before),
                             after_sha256=_sha(sound.after)) for sound in sounds],
                files=files)
