"""History Edition asset transforms for the optional Bug Fixes module."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
from html import unescape
from pathlib import Path
import re
import struct

from .filesystem import file_sha, safe_child


class BugFixError(ValueError):
    """An input asset differs from the reviewed game build."""


KING_OF_ORE_PATH = 'Languages/Nl/Scenes/0200Single/Singleplayer14.htm'
KING_OF_ORE_SHA256 = 'a277d1843bce9d0691357b2f10b410184910b1c58ca83663a50c7c37316c46a9'
KING_OF_ORE_SCENE_PATH = 'Languages/Nl/Scenes/0200Single/Single_14.sze'
KING_OF_ORE_SCENE_SHA256 = 'ec9234fc088503c7739d00ec582e3fb01ca235794707645d9da9382551dcac2a'
_KING_OF_ORE_SIZE = 1227
KING_OF_ORE_LOCALES = ('Eng', 'Fra', 'Ger', 'Ita', 'Nl', 'Spa')

_ORE_OBJECTIVE_BEFORE = (
    b'Haal binnen het gegeven tijdsbestek ten\r\n'
    b'  minste 170 ton ijzererts uit de grond in elk van je zes steden.'
)
_ORE_OBJECTIVE_AFTER = (
    b'Zorg dat je binnen de tijdslimiet in elk van je zes startsteden\r\n'
    b'  minstens 170 ton ijzererts op voorraad hebt.'
)


@dataclass(frozen=True)
class KingOfOreEdit:
    locale: str
    quest_path: str
    scene_path: str
    scene_sha256: str
    before: bytes
    after: bytes


@dataclass(frozen=True)
class _KingOfOreBaseline:
    quest_size: int
    quest_sha1: str
    scene_size: int
    scene_sha1: str
    ore_words: tuple[str, ...]
    objective: str


# Size and SHA-1 pairs from Ubisoft's shipped installation manifest.
_KING_OF_ORE_BASELINES = {
    'Eng': _KingOfOreBaseline(
        1163, '6a7547b162f089bd071e0ef1b736aa9c6a8fcf60',
        1123739, 'ec6737ff826c9dbd0e97ee2dd80e113367168c2b', ('ore', 'iron'),
        'Have at least 170 tons of iron ore in stock in each of your six starting cities before time runs out.',
    ),
    'Fra': _KingOfOreBaseline(
        1189, '31c451c6fb191619f599890e7aafd80ac0647e51',
        1123740, '68c602b75c4498814301b4f87bd8764c3d77fe2b', ('minerai', 'fer'),
        'Stockez au moins 170 tonnes de minerai de fer dans chacune de vos six villes de départ avant la fin du temps imparti.',
    ),
    'Ger': _KingOfOreBaseline(
        1245, '267411ad20527fdacf95abf669e6fd1aee51de21',
        1123728, '4d5c843ae10c03e6fe834f51d0da8424c0c40394', ('erz',),
        'Lagere vor Ablauf der Zeit in jeder deiner sechs Startstädte mindestens 170 Tonnen Eisenerz.',
    ),
    'Ita': _KingOfOreBaseline(
        1254, 'fa325de80f9a73059ade69bf7f1c16fd55bd31e0',
        1123742, 'f11e6e172880eafb215390b5a44e6a73ccee07bd', ('mineral', 'ferro'),
        'Accumula almeno 170 tonnellate di minerale di ferro in ciascuna delle tue sei città iniziali entro il tempo limite.',
    ),
    'Spa': _KingOfOreBaseline(
        1181, '84da3b13bdc11bcb2506e251b558565b9cf66ac0',
        1123736, '75c630bc20e3c7d4ebbb9a1e4a4228132e88f92e', ('mineral', 'hierro', 'mena'),
        'Almacena al menos 170 toneladas de mineral de hierro en cada una de tus seis ciudades iniciales antes de que se agote el tiempo.',
    ),
}
_ORE_SCENE_HEADER = b'ANNO\0' + b'\0' * 7
_ORE_QUEST_REFERENCE = b'QUEST\0\x14\0\x12singleplayer14.htm\0'
_ORE_KERNEL_SHA256 = 'f8ba650ccc3272b7fde233c4eaa013f59ec79101c0d2d87d58ee8aa76b30deae'
_QUEST_ROW = re.compile(rb'<tr\b[^>]*>(.*?)</tr\s*>', re.IGNORECASE | re.DOTALL)
_QUEST_CELL = re.compile(rb'<td\b[^>]*>(.*?)</td\s*>', re.IGNORECASE | re.DOTALL)
_QUEST_ANCHOR = re.compile(rb'<a\b[^>]*\bname\s*=\s*["\']single14_(30017[01])["\']', re.IGNORECASE)
_QUEST_MARKUP_OR_TEXT = re.compile(rb'<[^>]*>|([^<>]+)')
_QUEST_LINE_BREAK = re.compile(rb'(?:\r\n|\n|\r)[\t ]*')


def fix_king_of_ore(data: bytes) -> bytes:
    """Update both objective states without changing markup or the scenario."""
    if (hashlib.sha256(data).hexdigest() != KING_OF_ORE_SHA256
            or data.count(_ORE_OBJECTIVE_BEFORE) != 2):
        raise BugFixError('Unsupported Dutch King of Ore quest text: ' + KING_OF_ORE_PATH)
    return data.replace(_ORE_OBJECTIVE_BEFORE, _ORE_OBJECTIVE_AFTER)


def _read_manifest_asset(path: Path, name: str, size: int, digest: str) -> bytes:
    with path.open('rb') as stream:
        data = stream.read(size + 1)
    if len(data) != size or hashlib.sha1(data, usedforsecurity=False).hexdigest() != digest:
        raise BugFixError('King of Ore asset differs from the reviewed Ubisoft installation: ' + name)
    return data


def _verify_ore_scene(data: bytes, name: str) -> None:
    # Locale-specific scene metadata differs. The executable scenario rules
    # match after removing script comments and normalizing whitespace.
    header, separator, tail = data.partition(b'[SCRIPT_KERNEL]')
    script, delimiter, _ = tail.partition(b'[SIGNALS]')
    code = b' '.join(b'\n'.join(
        line for line in script.splitlines() if not line.lstrip().startswith(b'$')
    ).split())
    if (not header.startswith(_ORE_SCENE_HEADER)
            or header.lower().count(_ORE_QUEST_REFERENCE.lower()) != 1
            or not separator or not delimiter or b'[SCRIPT_KERNEL]' in tail
            or hashlib.sha256(code).hexdigest() != _ORE_KERNEL_SHA256):
        raise BugFixError('King of Ore scene does not have the reviewed stockpile rule: ' + name)


def _preserve_objective_wrapping(objective: bytes, original: bytes, name: str) -> bytes:
    separators = _QUEST_LINE_BREAK.findall(original)
    if not separators:
        return objective
    words = objective.split()
    if len(words) <= len(separators):
        raise BugFixError('Unexpected King of Ore objective line wraps: ' + name)
    parts = []
    first_word = 0
    for line, separator in enumerate(separators, start=1):
        next_word = len(words) * line // (len(separators) + 1)
        parts.extend((b' '.join(words[first_word:next_word]), separator))
        first_word = next_word
    parts.append(b' '.join(words[first_word:]))
    return b''.join(parts)


def _localized_ore_quest(data: bytes, baseline: _KingOfOreBaseline, name: str) -> bytes:
    edits = {}
    encoding = 'utf-8' if (data.startswith(b'\xef\xbb\xbf') or re.search(
        rb'charset\s*=\s*["\']?utf-8\b', data, re.IGNORECASE,
    )) else 'cp1252'
    for row in _QUEST_ROW.finditer(data):
        anchor = _QUEST_ANCHOR.search(row[1])
        if anchor is None:
            continue
        quest_id = anchor[1]
        cells = tuple(_QUEST_CELL.finditer(row[1]))
        if (quest_id in edits or len(cells) != 2 or not _QUEST_ANCHOR.search(cells[0][1])
                or b'#' + quest_id + b'*' not in cells[0][1]):
            raise BugFixError('Unexpected King of Ore objective markup: ' + name)
        body = cells[1]
        strings = [m for m in _QUEST_MARKUP_OR_TEXT.finditer(body[1]) if m[1] and m[1].strip()]
        if len(strings) != 1:
            raise BugFixError('Expected a single King of Ore objective text span: ' + name)
        visible = strings[0]
        original = visible[1].strip()
        sentence = ' '.join(unescape(original.decode(encoding)).casefold().split())
        if (not re.search(r'(?<![0-9])170(?![0-9])', sentence)
                or not any(word in sentence for word in baseline.ore_words)):
            raise BugFixError('Expected the original King of Ore objective text: ' + name)
        start = row.start(1) + body.start(1) + visible.start(1)
        start += len(visible[1]) - len(visible[1].lstrip())
        corrected = _preserve_objective_wrapping(baseline.objective.encode(encoding), original, name)
        edits[quest_id] = (start, start + len(original), corrected)
    if tuple(edits) != (b'300170', b'300171') or len(tuple(_QUEST_ANCHOR.finditer(data))) != 2:
        raise BugFixError('Expected both King of Ore objectives in order: ' + name)
    for start, end, corrected in reversed(tuple(edits.values())):
        data = data[:start] + corrected + data[end:]
    return data


def king_of_ore_assets(root: Path, *, locales: Iterable[str] | None = None) -> tuple[KingOfOreEdit, ...]:
    """Plan all installed King of Ore locale edits, or recheck an exact selection."""
    selected = KING_OF_ORE_LOCALES if locales is None else tuple(locales)
    if not selected or not set(selected).issubset(KING_OF_ORE_LOCALES) or len(set(selected)) != len(selected):
        raise BugFixError('Invalid King of Ore language selection.')
    edits = []
    for locale in KING_OF_ORE_LOCALES:
        if locale not in selected:
            continue
        quest_name = f'Languages/{locale}/Scenes/0200Single/Singleplayer14.htm'
        scene_name = f'Languages/{locale}/Scenes/0200Single/Single_14.sze'
        quest = safe_child(root, quest_name)
        scene = safe_child(root, scene_name)
        if locales is None and not quest.exists() and not scene.exists():
            continue
        if not quest.is_file() or not scene.is_file():
            raise BugFixError('The King of Ore quest and scenario files are required for ' + locale + '.')
        if locale == 'Nl':
            scene_sha256 = file_sha(scene)
            if scene_sha256 != KING_OF_ORE_SCENE_SHA256:
                raise BugFixError('The Dutch King of Ore scenario differs from the supported version.')
            with quest.open('rb') as stream:
                before = stream.read(_KING_OF_ORE_SIZE + 1)
            after = fix_king_of_ore(before)
        else:
            baseline = _KING_OF_ORE_BASELINES[locale]
            scene_data = _read_manifest_asset(scene, scene_name, baseline.scene_size, baseline.scene_sha1)
            _verify_ore_scene(scene_data, scene_name)
            scene_sha256 = hashlib.sha256(scene_data).hexdigest()
            before = _read_manifest_asset(quest, quest_name, baseline.quest_size, baseline.quest_sha1)
            after = _localized_ore_quest(before, baseline, quest_name)
        edits.append(KingOfOreEdit(locale, quest_name, scene_name, scene_sha256, before, after))
    if not edits:
        raise BugFixError('No supported King of Ore language files were found in this game.')
    return tuple(edits)


# Experimental A/B samples derived locally from the original Dutch assets.
# The reviewed files all have mono, 22,050 Hz, 16-bit PCM at byte 4096.
_LIVESTOCK_SAMPLE_SHA256 = {
    'Languages/Nl/Samples/Schaf1.wav': 'db0e86fd59fe79bae701ff99f4bd5882a8ebd42665cf4e3de5741822d1d36903',
    'Languages/Nl/Samples/Schaf2.wav': 'd876498e296da024d95d6d890876fb941271f9b0b45e1d59bfd36c8ad8f220df',
    'Languages/Nl/Samples/Kuh1.wav': 'fa2e0323e77988a9657895ab11dbc8fb480e509107560e2d71fc0ff1da5a8b3c',
    'Languages/Nl/Samples/Kuh2.wav': 'b9ce14a625dd5cad0151e7b9496a345feb1141043ad24dc0ec0c4ab1dbe49a00',
    'Languages/Nl/Samples/Huhn gluckst.wav': 'cd5158155ec68ae0e4358ee0762b58725ed2d5de892f505b2333c0499ddbdc7d',
}
LIVESTOCK_SAMPLE_PATHS = tuple(_LIVESTOCK_SAMPLE_SHA256)
_SAMPLE_OFFSET = 4096
_LIVESTOCK_GAIN = 10 ** (-10 / 20)


def quieter_livestock_sample(name: str, data: bytes) -> bytes:
    """Reduce a verified original by 10 dB for playback comparison."""
    if hashlib.sha256(data).hexdigest() != _LIVESTOCK_SAMPLE_SHA256.get(name):
        raise BugFixError('Unsupported Dutch livestock sample: ' + name)
    samples = struct.iter_unpack('<h', data[_SAMPLE_OFFSET:])
    attenuated = [round(sample * _LIVESTOCK_GAIN) for (sample,) in samples]
    return data[:_SAMPLE_OFFSET] + struct.pack(f'<{len(attenuated)}h', *attenuated)
