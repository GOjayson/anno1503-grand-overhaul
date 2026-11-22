"""Verify the scenario name in the inspected native cache layout."""

from hashlib import sha256
from struct import pack
import unittest
from unittest.mock import patch

from anno1503_overhaul import world_settings_multiplayer_catalogue as catalogue


def cache_entry(kind, path, filename, alias, *, seats=(1, 1), guid=bytes(16)):
    metadata = bytes((kind, 0, *seats)) + bytes(4) + guid
    return (
        pack("<12sI", b"ENTRY", 384)
        + metadata
        + path.ljust(48, b"\0")
        + filename.ljust(48, b"\0")
        + alias.ljust(260, b"\0")
        + b"\0\0\x01\0"
    )


def fixture():
    single_player = [
        cache_entry((0, 2, 4, 8)[index % 4], b"Languages\\Nl\\Scenes\\", f"Test{index}.sze".encode(), b"Test")
        for index in range(50)
    ]
    multiplayer_path = b"Scenes\\0500MultiEndlos\\"
    alternate_multiplayer = [
        cache_entry(3, multiplayer_path, b"Multi01_04.sze", b"Classic", seats=(2, 4)),
        cache_entry(5, multiplayer_path, b"LastWager.sze", b"Last Wager", seats=(2, 2)),
        cache_entry(5, multiplayer_path, b"MoralHighGround.sze", b"Moral High Ground", seats=(3, 4)),
        cache_entry(5, b"Scenes\\0700Multi\\", b"Multi001.sze", b"Imperial Legacy", seats=(4, 4)),
    ]
    new_earth = cache_entry(
        5, multiplayer_path, b"NewEarth.sze", b"Nieuwe aarde (2-4)",
        seats=(2, 4), guid=bytes.fromhex("8c93300df2fe494880c43080ca511525"),
    )
    entries = single_player[:13] + alternate_multiplayer + [new_earth] + single_player[13:]
    return b"".join(entries), entries, new_earth


class GeneratedWorldCatalogueTests(unittest.TestCase):
    def test_changes_only_the_new_earth_name(self):
        stock, original_entries, new_earth = fixture()
        with patch.object(catalogue, "STOCK_SCENE_CACHE_SHA256", sha256(stock).hexdigest()):
            result = catalogue.derive_generated_world_catalogue(stock)
        entries = [result[index:index + 400] for index in range(0, len(result), 400)]
        generated = entries[17]
        self.assertEqual(len(entries), 55)
        self.assertEqual(entries[:17] + entries[18:], original_entries[:17] + original_entries[18:])
        self.assertEqual(generated[:136], new_earth[:136])
        self.assertEqual(generated[136:396], b"Custom world (2-4)".ljust(260, b"\0"))
        self.assertEqual(generated[396:], new_earth[396:])

    def test_rejects_an_unreviewed_cache(self):
        stock, _, _ = fixture()
        with self.assertRaisesRegex(ValueError, "reviewed Dutch"):
            catalogue.derive_generated_world_catalogue(stock)

    def test_rejects_a_changed_new_earth_identity_even_if_repinning(self):
        stock, _, new_earth = fixture()
        changed = stock.replace(new_earth, new_earth[:24] + bytes(16) + new_earth[40:])
        self.assertNotEqual(changed, stock)
        with patch.object(catalogue, "STOCK_SCENE_CACHE_SHA256", sha256(changed).hexdigest()):
            with self.assertRaisesRegex(ValueError, "New Earth scenario cache identity"):
                catalogue.derive_generated_world_catalogue(changed)
