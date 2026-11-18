"""Execute the read-only household aggregate without a running game.

Most cases replace only the native supply getter with an ABI-correct callback.
An optional Windows case executes the exact getter from a locally owned,
fingerprint-verified Food 0.5 module. No game file or live process is changed.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import mmap
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/anno1503_overhaul/native/food_household.c"
GOODS = (26, 40, 24, 25, 45)
SUPPLY = C.CFUNCTYPE(C.c_ssize_t, C.c_void_p, C.c_size_t, C.c_size_t, C.c_size_t)


class FoodSnapshot(C.Structure):
    _fields_ = [("state", C.c_uint32), ("percent", C.c_uint32),
                ("active", C.c_uint32), ("total_weight", C.c_uint32),
                ("scores", C.c_uint16 * 5), ("rates", C.c_uint16 * 5)]


class House:
    def __init__(self):
        self.house = C.create_string_buffer(0xB0)
        self.needs = C.create_string_buffer(0x128)
        self.records = C.create_string_buffer(143 * 26)
        self.vtable = C.create_string_buffer(0x138)
        self.calls = []
        self.errors = []
        self.scores = dict.fromkeys(GOODS, 128)
        self.getter = SUPPLY(self.supply)
        struct.pack_into("<Q", self.house, 0, C.addressof(self.vtable))
        struct.pack_into("<Q", self.house, 0x48, C.addressof(self.needs))
        struct.pack_into("<H", self.house, 0x52, 12)
        struct.pack_into("<Q", self.vtable, 0x130, C.cast(self.getter, C.c_void_p).value)
        struct.pack_into("<B", self.needs, 2, 5)
        C.memset(C.addressof(self.needs) + 3, 255, 96)
        struct.pack_into("<Q", self.needs, 0x118, C.addressof(self.records))
        for i, (good, rate) in enumerate(zip(GOODS, (30, 25, 10, 20, 15))):
            self.map_good(good, i)
            struct.pack_into("<B", self.needs, 0x64 + i * 4, good)
            self.rate(i, rate)
            self.gate(good, i)

    def supply(self, house, good, unused1, unused2):
        if house != C.addressof(self.house) or unused1 or unused2 or good not in GOODS:
            # Exceptions raised inside ctypes callbacks are otherwise ignored.
            self.errors.append((house, good, unused1, unused2))
            return 0
        self.calls.append(good)
        return self.scores[good]

    def map_good(self, good, index):
        struct.pack_into("<B", self.needs, good + 3, index)

    def rate(self, index, rate):
        struct.pack_into("<H", self.needs, 0x66 + index * 4, rate)

    def gate(self, good, gate):
        struct.pack_into("<B", self.records, good * 26 + 2, gate)

    def memory(self):
        return tuple(bytes(buffer) for buffer in (self.house, self.needs, self.records, self.vtable))


class HouseView:
    """Native-shaped widgets; only property and positioning boundaries are fake."""
    def __init__(self, house, *, constructing=False):
        self.house = house
        self.kind = 0x1A00
        self.unlocked = 0xFFFFFFFF
        self.view = C.create_string_buffer(0x820)
        self.vector = C.create_string_buffer(10 * 8)
        self.widgets = {} if constructing else {i: C.create_string_buffer(0x100) for i in (7, 8, 9)}
        self.widget_vtable = C.create_string_buffer(0xD0)
        self.owner = C.create_string_buffer(0x30)
        self.owner_vtable = C.create_string_buffer(0x48)
        self.profile = C.create_string_buffer(0x30)
        self.profile_vtable = C.create_string_buffer(0xA0)
        self.properties = {}
        self.retained_strings = {}
        self.bar_percent = None
        self.positions = {}
        self.errors = []
        self.profile_queries = []
        self.constructing = constructing
        self.widget_ids, self.parents, self.sizes = {}, {}, {}
        self.identities = {C.addressof(widget): i for i, widget in self.widgets.items()}
        self.callbacks = []

        def attach(table, slot, callback):
            function = SUPPLY(callback)
            self.callbacks.append(function)
            struct.pack_into("<Q", table, slot, C.cast(function, C.c_void_p).value)
        self.attach = attach

        def kind(this, a, b, c):
            if this != C.addressof(house.house) or a or b or c:
                self.errors.append("Unexpected house-kind query.")
            return self.kind

        def owner(this, a, b, c):
            if this != C.addressof(house.house) or a or b or c:
                self.errors.append("Unexpected house-owner query.")
            return C.addressof(self.owner)

        def profile(this, a, b, c):
            if this != C.addressof(self.owner) or a or b or c:
                self.errors.append("Unexpected owner-profile query.")
            return C.addressof(self.profile)

        def query(this, property_id, output, unused):
            if this != C.addressof(self.profile) or property_id != 0x21 or not output or unused:
                self.errors.append("Unexpected unlock-property query.")
                return 0
            self.profile_queries.append(property_id)
            C.c_uint64.from_address(output + 8).value = self.unlocked
            return 0

        def property(this, property_id, value, unused):
            if this not in self.identities or not value or unused:
                self.errors.append("Unexpected widget-property arguments.")
                return 0
            payload = C.c_uint64.from_address(value + 8).value
            key = self.identities[this], property_id
            if property_id in (0x1C4, 0x1C9, 0x1CA):
                if not payload:
                    self.errors.append("A text property received a null pointer.")
                    return 0
                if property_id == 0x1C4:
                    payload = C.string_at(payload).decode("ascii")
                else:
                    # The native tooltip setter retains this pointer. Do not
                    # copy the string here and accidentally hide a lifetime bug.
                    self.retained_strings[key] = payload
            elif property_id == 0x1C0:
                self.bar_percent = payload
            elif self.constructing and property_id in (0x19D, 0x198, 0x1BC, 0x194, 0x190, 0x1C2, 0x1C6):
                if property_id == 0x19D and payload != C.addressof(self.view):
                    self.errors.append("The widget owner is not its actual house view.")
            else:
                # 1cb is a native DWORD/bar-value setter, not a text property.
                if property_id == 0x1CB:
                    self.bar_percent = payload & 0xFFFFFFFF
                self.errors.append("A refresh tried an unexpected widget operation.")
            self.properties[key] = payload
            return 0

        def position(this, x, y, unused):
            if this not in self.identities or unused:
                self.errors.append("Unexpected widget-position arguments.")
                return 0
            self.positions[self.identities[this]] = (C.c_ssize_t(x).value, C.c_ssize_t(y).value)
            return 0

        def identify(this, identity, b, c):
            if this not in self.identities or identity != self.identities[this] or b or c:
                self.errors.append("Unexpected widget identity setter arguments.")
                return 0
            self.widget_ids[this] = identity
            return 0

        def parent(this, parent_pointer, b, c):
            if this not in self.identities or not parent_pointer or b or c:
                self.errors.append("Unexpected widget parent setter arguments.")
                return 0
            self.parents[self.identities[this]] = parent_pointer
            return 0

        def size(this, width, height, unused):
            if this not in self.identities or not width or not height or unused:
                self.errors.append("Unexpected widget size setter arguments.")
                return 0
            self.sizes[self.identities[this]] = (width, height)
            return 0

        attach(house.vtable, 0x30, kind)
        attach(house.vtable, 0x38, owner)
        attach(self.owner_vtable, 0x40, profile)
        attach(self.profile_vtable, 0x98, query)
        attach(self.widget_vtable, 0xA0, property)
        attach(self.widget_vtable, 0xC0, position)
        attach(self.widget_vtable, 0x58, parent)
        attach(self.widget_vtable, 0x80, identify)
        attach(self.widget_vtable, 0xA8, size)
        struct.pack_into("<Q", self.owner, 0, C.addressof(self.owner_vtable))
        struct.pack_into("<Q", self.profile, 0, C.addressof(self.profile_vtable))
        struct.pack_into("<Q", self.view, 0x750, C.addressof(self.vector))
        struct.pack_into("<Q", self.view, 0x758, C.addressof(self.vector) + (7 if constructing else 10) * 8)
        struct.pack_into("<Q", self.view, 0x760, C.addressof(self.vector) + 10 * 8)
        struct.pack_into("<Q", self.view, 0x808, C.addressof(house.house))
        for i, widget in self.widgets.items():
            struct.pack_into("<Q", widget, 0, C.addressof(self.widget_vtable))
            struct.pack_into("<Q", self.vector, i * 8, C.addressof(widget))

    def origin(self, x, y):
        struct.pack_into("<ff", self.view, 0x6F8, x, y)

    def tooltip(self, index):
        property_id = 0x1CA if index == 7 else 0x1C9
        return C.string_at(self.retained_strings[index, property_id]).decode("ascii")

    def simulation_memory(self):
        return self.house.memory() + tuple(bytes(buffer) for buffer in
                                          (self.owner, self.owner_vtable, self.profile, self.profile_vtable))


class ViewImage:
    """Authored executable image substitute; never maps or changes a game DLL."""
    SIZE, TABLE, ORIGINAL_CREATE = 0xB2000, 0xB1758, 0x80EE0

    def __init__(self, original_result=0):
        if os.name == "nt":
            self.kernel = C.WinDLL("kernel32", use_last_error=True)
            self.kernel.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
            self.kernel.VirtualAlloc.restype = C.c_void_p
            self.kernel.VirtualProtect.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.POINTER(C.c_uint32)]
            self.kernel.VirtualProtect.restype = C.c_int
            self.kernel.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
            self.kernel.VirtualFree.restype = C.c_int
            self.base = self.kernel.VirtualAlloc(None, self.SIZE, 0x3000, 4)
            if not self.base:
                raise OSError(C.get_last_error(), "Allocate authored View fixture")
        else:
            self.mapping = mmap.mmap(-1, self.SIZE, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                                     prot=mmap.PROT_READ | mmap.PROT_WRITE)
            self.base = C.addressof(C.c_char.from_buffer(self.mapping))
        # An x64 return-value stub stands in only for the original constructor.
        code = b"\xb8" + struct.pack("<I", original_result) + b"\xc3"
        C.memmove(self.base + self.ORIGINAL_CREATE, code, len(code))
        page = self.base + (self.ORIGINAL_CREATE & ~4095)
        if os.name == "nt":
            previous = C.c_uint32()
            protected = self.kernel.VirtualProtect(page, 4096, 0x20, C.byref(previous))
        else:
            protect = C.CDLL(None).mprotect
            protect.argtypes = [C.c_void_p, C.c_size_t, C.c_int]
            protect.restype = C.c_int
            protected = protect(page, 4096, mmap.PROT_READ | mmap.PROT_EXEC) == 0
        if not protected:
            self.close()
            raise OSError("Protect authored constructor fixture as executable")

    def close(self):
        if os.name == "nt":
            if not self.kernel.VirtualFree(self.base, 0, 0x8000):
                raise OSError(C.get_last_error(), "Release authored View fixture")
        else:
            self.mapping.close()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


class ConstructorView(HouseView):
    ICON_ID, BAR_ID = 913, 527

    def __init__(self, house, image):
        super().__init__(house, constructing=True)
        self.image = image
        self.factory_parent = C.create_string_buffer(64)
        self.icon_resources = C.create_string_buffer(64)
        self.text_resources = C.create_string_buffer(64)
        self.resource_vtable = C.create_string_buffer(0xA0)
        self.resource_queries, self.resource_high_words = [], []
        self.factory_calls, self.register_calls = [], []
        self.allocated, self.widget_kinds = {}, {}
        self.existing = [C.create_string_buffer(16) for _ in range(7)]
        for i, widget in enumerate(self.existing):
            struct.pack_into("<Q", self.vector, i * 8, C.addressof(widget))
        self.fail_resource = None
        self.resource_failure_writes_sentinel = True
        self.fail_factory, self.null_factory_output, self.fail_registration = False, False, False
        struct.pack_into("<Q", self.view, 0, image.base + image.TABLE)
        struct.pack_into("<Q", self.view, 0x6C8, C.addressof(self.factory_parent))
        struct.pack_into("<Q", self.view, 0x710, C.addressof(self.icon_resources))
        struct.pack_into("<Q", self.view, 0x730, C.addressof(self.text_resources))
        struct.pack_into("<Q", self.icon_resources, 0, C.addressof(self.resource_vtable))

        def factory(this, kind, output, parent):
            if (this != C.addressof(self.view) or kind not in (0xB18, 0xB1C)
                    or not output or C.c_void_p.from_address(output).value
                    or parent != C.addressof(self.factory_parent)):
                self.errors.append("Unexpected native factory ABI arguments.")
                return 0x80004005
            self.factory_calls.append(kind)
            if self.fail_factory:
                return 0x80004005
            if not self.null_factory_output:
                widget = C.create_string_buffer(0x100)
                address = C.addressof(widget)
                struct.pack_into("<Q", widget, 0, C.addressof(self.widget_vtable))
                self.allocated[address] = widget
                self.widget_kinds[address] = kind
                C.c_void_p.from_address(output).value = address
            return 0

        def register(this, address, index, unused):
            if (this != C.addressof(self.view) or address not in self.allocated
                    or index not in (7, 8, 9) or index in self.widgets or unused):
                self.errors.append("Unexpected native registration ABI arguments.")
                return 65535
            self.register_calls.append(index)
            if self.fail_registration:
                return 65535
            self.widgets[index] = self.allocated[address]
            self.identities[address] = index
            struct.pack_into("<Q", self.vector, index * 8, address)
            struct.pack_into("<Q", self.view, 0x758, C.addressof(self.vector) + (index + 1) * 8)
            return index

        def resource(this, property_id, value, unused):
            if this != C.addressof(self.icon_resources) or property_id != 0xA or not value or unused:
                self.errors.append("Unexpected native resource query ABI arguments.")
                return 0
            # Native lookup receives the name inline in Value+8. It returns
            # BOOL and overwrites only a DWORD, leaving the upper name bytes.
            try:
                name = C.string_at(value + 8, 110).split(b"\0", 1)[0].decode("ascii")
            except UnicodeError:
                self.errors.append("Resource name was not passed inline.")
                return 0
            if name not in ("OVERHAUL_FOOD_SUMMARY", "BALKENWOHNHAUS"):
                self.errors.append("Unexpected resource name or pointer-shaped name.")
                return 0
            self.resource_queries.append(name)
            high_before = C.string_at(value + 12, 4)
            if name == self.fail_resource:
                if self.resource_failure_writes_sentinel:
                    C.c_uint32.from_address(value + 8).value = 0xFFFFFFFF
                return 0
            C.c_uint32.from_address(value + 8).value = (
                self.ICON_ID if name == "OVERHAUL_FOOD_SUMMARY" else self.BAR_ID)
            self.resource_high_words.append((high_before, C.string_at(value + 12, 4)))
            return 1

        self.attach(self.resource_vtable, 0x98, resource)
        for slot, callback in ((0x178, factory), (0x50, register)):
            function = SUPPLY(callback)
            self.callbacks.append(function)
            C.c_uint64.from_address(image.base + image.TABLE + slot).value = C.cast(function, C.c_void_p).value


class HouseholdMeasureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if C.sizeof(C.c_void_p) != 8:
            raise unittest.SkipTest("Household fixtures require an x64 process.")
        if os.name == "nt":
            compiler = ROOT / ".local/toolchain/ziglang/zig.exe"
            if not compiler.is_file():
                raise unittest.SkipTest("Reviewed local native compiler is unavailable.")
            command = [str(compiler), "cc", "-target", "x86_64-windows-gnu"]
        else:
            compiler = shutil.which(os.environ.get("CC", "cc"))
            if not compiler:
                raise unittest.SkipTest("Native compiler is unavailable.")
            command = [compiler, "-fPIC"]
        cls.temp = tempfile.TemporaryDirectory(prefix="anno-food-household-")
        binary = Path(cls.temp.name) / ("household.dll" if os.name == "nt" else "household.so")
        try:
            run = subprocess.run(command + ["-std=c11", "-shared", "-O2", "-Wall", "-Wextra",
                                             "-Werror", str(SOURCE), "-o", str(binary)],
                                 capture_output=True, text=True)
            if run.returncode:
                raise AssertionError(run.stdout + run.stderr)
            cls.lib = C.CDLL(str(binary))
            cls.binary = binary
            cls.measure = cls.lib.food_measure
            cls.measure.argtypes = [C.c_void_p, C.c_uint32, C.POINTER(FoodSnapshot)]
            cls.measure.restype = C.c_uint32
            cls.refresh = cls.lib.food_refresh
            cls.refresh.argtypes = [C.c_void_p]
            cls.refresh.restype = None
            cls.position = cls.lib.food_position
            cls.position.argtypes = [C.c_void_p]
            cls.position.restype = None
            cls.create = cls.lib.food_create
            cls.create.argtypes = [C.c_void_p, C.c_size_t, C.c_size_t, C.c_size_t]
            cls.create.restype = C.c_ssize_t
        except BaseException:
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        handle = cls.lib._handle
        del cls.measure
        del cls.refresh
        del cls.position
        del cls.create
        del cls.lib
        if os.name == "nt":
            import _ctypes
            _ctypes.FreeLibrary(handle)
        cls.temp.cleanup()

    def check(self, house, mask=0xFFFFFFFF):
        before = house.memory()
        out = FoodSnapshot()
        C.memset(C.byref(out), 0xA5, C.sizeof(out))
        result = self.measure(C.addressof(house.house), mask, C.byref(out))
        self.assertEqual(result, out.state)
        self.assertEqual(house.errors, [], "Unexpected native supply getter arguments.")
        self.assertEqual(house.memory(), before, "Measuring food changed simulation memory.")
        return out

    def refresh_view(self, view):
        before = view.simulation_memory()
        self.refresh(C.addressof(view.view))
        self.assertEqual(view.simulation_memory(), before, "Refreshing information changed simulation memory.")
        self.assertEqual(view.errors, [])
        self.assertEqual(view.house.errors, [])

    def assert_module_pointer(self, pointer):
        """A retained tooltip must belong to the loaded helper, not its stack."""
        if os.name == "nt":
            raw = self.binary.read_bytes()
            pe = struct.unpack_from("<I", raw, 60)[0]
            image_size = struct.unpack_from("<I", raw, pe + 24 + 56)[0]
            self.assertLessEqual(self.lib._handle, pointer)
            self.assertLess(pointer, self.lib._handle + image_size)
        else:
            class DlInfo(C.Structure):
                _fields_ = [("filename", C.c_char_p), ("base", C.c_void_p),
                            ("symbol", C.c_char_p), ("address", C.c_void_p)]
            dladdr = C.CDLL(None).dladdr
            dladdr.argtypes = [C.c_void_p, C.POINTER(DlInfo)]
            dladdr.restype = C.c_int
            literal_info, function_info = DlInfo(), DlInfo()
            self.assertTrue(dladdr(pointer, C.byref(literal_info)))
            self.assertTrue(dladdr(C.cast(self.refresh, C.c_void_p), C.byref(function_info)))
            self.assertEqual(literal_info.base, function_info.base)

    def test_all_foods_full_and_empty_buffers_are_read_only(self):
        house = House()
        full = self.check(house)
        self.assertEqual((full.state, full.percent, full.active, full.total_weight), (2, 100, 5, 100))
        self.assertEqual(list(full.scores), [128] * 5)
        self.assertEqual(list(full.rates), [30, 25, 10, 20, 15])
        self.assertEqual(house.calls, list(GOODS))
        house.calls.clear()
        house.scores = dict.fromkeys(GOODS, 0)
        empty = self.check(house)
        self.assertEqual((empty.state, empty.percent, empty.active), (2, 0, 5))
        self.assertEqual(house.calls, list(GOODS))

    def test_actual_need_rates_determine_weight_not_hardcoded_tier_percentages(self):
        house = House()
        for i, rate in enumerate((1, 99, 0, 0, 0)):
            house.rate(i, rate)
        house.scores.update({26: 128, 40: 0})
        out = self.check(house)
        self.assertEqual((out.state, out.percent, out.active, out.total_weight), (2, 1, 2, 100))
        self.assertEqual(house.calls, [26, 40])

    def test_locked_absent_and_zero_foods_never_enter_getter_or_denominator(self):
        house = House()
        house.scores.update({26: 128, 24: 0})
        out = self.check(house, (1 << 0) | (1 << 2))
        self.assertEqual((out.percent, out.active, out.total_weight), (75, 2, 40))
        self.assertEqual(list(out.rates), [30, 0, 10, 0, 0])
        self.assertEqual(house.calls, [26, 24])
        house.calls.clear()
        house.map_good(40, 255)
        house.map_good(25, 5)  # Equal to count is out of range as well.
        house.rate(4, 0)
        out = self.check(house)
        self.assertEqual((out.percent, out.active, out.total_weight), (75, 2, 40))
        self.assertEqual(house.calls, [26, 24])

    def test_no_active_food_and_empty_population_have_distinct_states(self):
        house = House()
        inactive = self.check(house, 0)
        self.assertEqual((inactive.state, inactive.percent, inactive.active, inactive.total_weight),
                         (3, 0, 0, 0))
        self.assertEqual(house.calls, [])
        struct.pack_into("<H", house.house, 0x52, 0)
        vacant = self.check(house)
        self.assertEqual((vacant.state, vacant.percent, vacant.active), (1, 0, 0))
        self.assertEqual(house.calls, [])

    def test_invalid_null_inputs_or_count_clear_snapshot_before_native_calls(self):
        out = FoodSnapshot()
        C.memset(C.byref(out), 0xA5, C.sizeof(out))
        self.assertEqual(self.measure(None, 0xFFFFFFFF, C.byref(out)), 0)
        self.assertEqual(bytes(out), bytes(C.sizeof(out)))
        house = House()
        self.assertEqual(self.measure(C.addressof(house.house), 0xFFFFFFFF, None), 0)
        faults = (("house", 0, "<Q", 0), ("house", 0x48, "<Q", 0),
                  ("vtable", 0x130, "<Q", 0),
                  ("needs", 0x118, "<Q", 0), ("needs", 2, "<B", 0),
                  ("needs", 2, "<B", 19))
        for buffer, offset, encoding, value in faults:
            with self.subTest(buffer=buffer, offset=offset, value=value):
                house = House()
                struct.pack_into(encoding, getattr(house, buffer), offset, value)
                invalid = self.check(house)
                self.assertEqual(bytes(invalid), bytes(C.sizeof(invalid)))
                self.assertEqual(house.calls, [])

    def test_boundary_need_index_and_unlock_bit31_are_safe(self):
        house = House()
        struct.pack_into("<B", house.needs, 2, 18)
        for good in GOODS:
            house.map_good(good, 255)
        house.map_good(45, 17)
        house.rate(17, 321)
        house.gate(45, 31)
        out = self.check(house, 1 << 31)
        self.assertEqual((out.state, out.percent, out.active, out.total_weight), (2, 100, 1, 321))
        self.assertEqual(house.calls, [45])
        for gate in (32, 255):
            house.calls.clear()
            house.gate(45, gate)
            out = self.check(house)
            self.assertEqual((out.state, out.total_weight), (3, 0))
            self.assertEqual(house.calls, [])

    def test_supply_clamps_and_rounding_use_wide_accumulators(self):
        house = House()
        for i in range(5):
            house.rate(i, 65535)
        house.scores = dict.fromkeys(GOODS, (1 << 63) - 1)
        out = self.check(house)
        self.assertEqual((out.percent, out.total_weight), (100, 5 * 65535))
        self.assertEqual(list(out.scores), [128] * 5)
        house.scores = dict.fromkeys(GOODS, -(1 << 63))
        out = self.check(house)
        self.assertEqual(out.percent, 0)
        self.assertEqual(list(out.scores), [0] * 5)
        for i, rate in enumerate((16, 9, 0, 0, 0)):
            house.rate(i, rate)
        for fish, potato, expected in ((1, 0, 1), (3, 0, 2), (127, 128, 100), (64, 64, 50)):
            with self.subTest(fish=fish, potato=potato):
                house.scores.update({26: fish, 40: potato})
                out = self.check(house)
                self.assertEqual(out.percent, expected)

    def test_ui_refresh_shows_85_percent_from_real_foods_without_spending_any(self):
        house = House()
        house.scores[45] = 0
        view = HouseView(house)
        self.refresh_view(view)
        self.assertEqual(view.properties[8, 0x1C4], "Food: 85%")
        self.assertEqual(view.properties[7, 0x1C0], 85)
        self.assertEqual(view.bar_percent, 85)
        self.assertNotIn((7, 0x1CB), view.properties)
        self.assertIn("Locked foods are excluded", view.tooltip(8))
        self.assertIn("Informative only", view.tooltip(9))
        self.assertIn("combined household supply", view.tooltip(7))
        self.assertEqual(view.profile_queries, [0x21])
        self.assertEqual(house.calls, list(GOODS))

    def test_ui_full_empty_and_locked_states_stay_consistent(self):
        house = House()
        view = HouseView(house)
        self.refresh_view(view)
        self.assertEqual(view.properties[8, 0x1C4], "Food: 100%")
        self.assertEqual(view.properties[7, 0x1C0], 100)
        house.calls.clear()
        view.unlocked &= ~(1 << 4)
        house.scores[45] = 0
        self.refresh_view(view)
        self.assertEqual(view.properties[8, 0x1C4], "Food: 100%")
        self.assertIn("Locked foods are excluded", view.tooltip(8))
        self.assertNotIn(45, house.calls)
        house.calls.clear()
        view.unlocked = 0
        self.refresh_view(view)
        self.assertEqual(view.properties[8, 0x1C4], "Food: Not available")
        self.assertEqual(view.properties[7, 0x1C0], 0)
        self.assertEqual(house.calls, [])
        struct.pack_into("<H", house.house, 0x52, 0)
        self.refresh_view(view)
        self.assertEqual(view.properties[8, 0x1C4], "Food: No residents")
        self.assertEqual(view.properties[7, 0x1C0], 0)
        self.assertEqual(house.calls, [])

    def test_ui_other_selection_hides_information_and_house_selection_restores_it(self):
        house = House()
        view = HouseView(house)
        self.refresh_view(view)
        visible = dict(view.positions)
        house.calls.clear()
        view.kind = 0x1900
        self.refresh_view(view)
        self.assertEqual(view.positions, {i: (-10000, -10000) for i in (7, 8, 9)})
        self.assertEqual(house.calls, [])
        view.kind = 0x1A00
        self.refresh_view(view)
        self.assertEqual(view.positions, visible)
        struct.pack_into("<Q", view.view, 0x808, 0)
        house.calls.clear()
        self.refresh_view(view)
        self.assertEqual(view.positions, {i: (-10000, -10000) for i in (7, 8, 9)})
        self.assertEqual(house.calls, [])

    def test_ui_position_follows_nonzero_view_origin_without_touching_house(self):
        house = House()
        view = HouseView(house)
        before = view.simulation_memory()
        self.position(C.addressof(view.view))
        baseline = dict(view.positions)
        view.origin(160.5, 83.75)
        self.position(C.addressof(view.view))
        self.assertEqual(view.positions, {i: (x + 160, y + 83) for i, (x, y) in baseline.items()})
        self.assertEqual(view.simulation_memory(), before)
        self.assertEqual(view.errors, [])
        self.assertEqual(house.calls, [])

    def test_ui_tooltip_is_bounded_and_refresh_handles_short_widget_vectors(self):
        house = House()
        for i in range(5):
            house.rate(i, 65535)
        house.scores = dict.fromkeys(GOODS, 160)
        view = HouseView(house)
        self.refresh_view(view)
        for i in (7, 8, 9):
            tooltip = view.tooltip(i)
            self.assertLess(len(tooltip.encode("ascii")), 512)
            self.assertTrue(tooltip)
        self.assertLess(len(view.properties[8, 0x1C4].encode("ascii")), 64)
        view.properties.clear()
        view.positions.clear()
        house.calls.clear()
        struct.pack_into("<Q", view.view, 0x758, C.addressof(view.vector) + 9 * 8)
        self.refresh_view(view)
        self.assertEqual(view.properties, {})
        self.assertEqual(view.positions, {})
        self.assertEqual(house.calls, [])

    def test_ui_retained_tooltips_have_module_lifetime_and_labels_are_copied(self):
        first_house = House()
        first_house.scores[45] = 0
        first = HouseView(first_house)
        self.refresh_view(first)
        original_tips = {i: first.tooltip(i) for i in (7, 8, 9)}
        for pointer in first.retained_strings.values():
            self.assert_module_pointer(pointer)
        second = HouseView(House())
        self.refresh_view(second)
        self.assertEqual(first.properties[8, 0x1C4], "Food: 85%")
        self.assertEqual(second.properties[8, 0x1C4], "Food: 100%")
        self.assertEqual(first.bar_percent, 85)
        self.assertEqual(second.bar_percent, 100)
        self.assertEqual({i: first.tooltip(i) for i in (7, 8, 9)}, original_tips)
        for pointer in second.retained_strings.values():
            self.assert_module_pointer(pointer)

    def test_production_constructor_registers_three_children_then_refreshes_real_aggregate(self):
        with ViewImage() as image:
            house = House()
            house.scores[45] = 0
            view = ConstructorView(house, image)
            original_slots = bytes(view.vector)[:7 * 8]
            before = view.simulation_memory()
            self.assertEqual(self.create(C.addressof(view.view), 0, 0, 0), 0)
            self.assertEqual(view.errors, [])
            self.assertEqual(view.factory_calls, [0xB18, 0xB1C, 0xB1C])
            self.assertEqual(view.register_calls, [7, 8, 9])
            self.assertEqual(sorted(view.widgets), [7, 8, 9])
            self.assertEqual(bytes(view.vector)[:7 * 8], original_slots)
            self.assertEqual(set(view.resource_queries), {"OVERHAUL_FOOD_SUMMARY", "BALKENWOHNHAUS"})
            self.assertTrue(all(before == after for before, after in view.resource_high_words))
            self.assertEqual(view.properties[7, 0x198], view.ICON_ID)
            self.assertEqual(struct.unpack_from("<I", view.widgets[7], 0xC8)[0], view.BAR_ID)
            self.assertEqual(view.properties[7, 0x1BC], 100)
            self.assertEqual(view.bar_percent, 0)
            for index in (7, 8, 9):
                self.assertEqual(view.widget_ids[C.addressof(view.widgets[index])], index)
                self.assertEqual(view.properties[index, 0x19D], C.addressof(view.view))
                self.assertEqual(view.parents[index], C.addressof(
                    view.icon_resources if index == 7 else view.text_resources))
                width, height = view.sizes[index]
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
            self.assertEqual(view.simulation_memory(), before)
            view.constructing = False
            self.refresh_view(view)
            self.assertEqual(view.properties[8, 0x1C4], "Food: 85%")
            self.assertEqual(view.bar_percent, 85)
            self.assertEqual(house.calls, list(GOODS))
            self.assertNotIn((7, 0x1CB), view.properties)
            for pointer in view.retained_strings.values():
                self.assert_module_pointer(pointer)

    def test_constructor_honors_native_failure_and_refuses_duplicate_children(self):
        with ViewImage(0x80004005) as image:
            view = ConstructorView(House(), image)
            self.assertLess(C.c_int32(self.create(C.addressof(view.view), 0, 0, 0)).value, 0)
            self.assertEqual(view.resource_queries, [])
            self.assertEqual(view.factory_calls, [])
        with ViewImage() as image:
            view = ConstructorView(House(), image)
            duplicate = C.create_string_buffer(16)
            struct.pack_into("<Q", view.vector, 7 * 8, C.addressof(duplicate))
            struct.pack_into("<Q", view.view, 0x758, C.addressof(view.vector) + 8 * 8)
            self.assertLess(C.c_int32(self.create(C.addressof(view.view), 0, 0, 0)).value, 0)
            self.assertEqual(view.resource_queries, [])
            self.assertEqual(view.factory_calls, [])
            self.assertEqual(view.errors, [])

    def test_constructor_refuses_failed_or_missing_factory_and_registration_outputs(self):
        for fault in ("fail_factory", "null_factory_output", "fail_registration"):
            with self.subTest(fault=fault), ViewImage() as image:
                view = ConstructorView(House(), image)
                setattr(view, fault, True)
                before = view.simulation_memory()
                self.assertLess(C.c_int32(self.create(C.addressof(view.view), 0, 0, 0)).value, 0)
                self.assertEqual(view.widgets, {})
                self.assertEqual(view.properties, {})
                self.assertEqual(view.errors, [])
                self.assertEqual(view.simulation_memory(), before)

    def test_constructor_refuses_BOOL_resource_failures_before_allocating_widgets(self):
        for resource in ("OVERHAUL_FOOD_SUMMARY", "BALKENWOHNHAUS"):
            for sentinel in (True, False):
                with self.subTest(resource=resource, sentinel=sentinel), ViewImage() as image:
                    view = ConstructorView(House(), image)
                    view.fail_resource = resource
                    view.resource_failure_writes_sentinel = sentinel
                    before = view.simulation_memory()
                    self.assertLess(C.c_int32(self.create(C.addressof(view.view), 0, 0, 0)).value, 0)
                    self.assertEqual(view.factory_calls, [])
                    self.assertEqual(view.widgets, {})
                    self.assertEqual(view.errors, [])
                    self.assertEqual(view.simulation_memory(), before)

    @unittest.skipUnless(os.name == "nt", "The native HE getter uses the Windows x64 ABI.")
    def test_exact_native_supply_getter_uses_delivered_house_buffers(self):
        path = ROOT / ".local/baselines/world_settings/native/AnnoWelt.source.dll"
        if not path.is_file():
            self.skipTest("Reviewed local Food 0.5 World module is unavailable.")
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9")
        pe = struct.unpack_from("<I", raw, 60)[0]
        self.assertEqual(struct.unpack_from("<H", raw, pe + 4)[0], 0x8664)
        optional = pe + 24
        self.assertEqual(struct.unpack_from("<H", raw, optional)[0], 0x20B)
        image_base = struct.unpack_from("<Q", raw, optional + 24)[0]
        section_count = struct.unpack_from("<H", raw, pe + 6)[0]
        section_table = optional + struct.unpack_from("<H", raw, pe + 20)[0]

        def data(rva, size):
            for i in range(section_count):
                virtual_size, virtual, raw_size, offset = struct.unpack_from("<IIII", raw, section_table + i * 40 + 8)
                if virtual <= rva and rva + size <= virtual + raw_size:
                    return raw[offset + rva - virtual:offset + rva - virtual + size]
            raise AssertionError("Native RVA leaves its reviewed raw section.")

        self.assertEqual(struct.unpack("<Q", data(0xF9EE8 + 0x130, 8))[0], image_base + 0x88DF0)
        leaf = data(0x88DF0, 0x49)
        self.assertEqual(hashlib.sha256(leaf).hexdigest(),
                         "0d97ca6dd00c08c1e928ca60d66400fc2950711f7e342c95a8f06b51ecd51c99")
        kernel = C.WinDLL("kernel32", use_last_error=True)
        kernel.VirtualAlloc.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.c_uint32]
        kernel.VirtualAlloc.restype = C.c_void_p
        kernel.VirtualProtect.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32, C.POINTER(C.c_uint32)]
        kernel.VirtualProtect.restype = C.c_int
        kernel.VirtualFree.argtypes = [C.c_void_p, C.c_size_t, C.c_uint32]
        kernel.VirtualFree.restype = C.c_int
        page = kernel.VirtualAlloc(None, 4096, 0x3000, 4)
        self.assertTrue(page)
        try:
            C.memmove(page, leaf, len(leaf))
            old = C.c_uint32()
            self.assertTrue(kernel.VirtualProtect(page, 4096, 0x20, C.byref(old)))
            house = House()
            struct.pack_into("<Q", house.vtable, 0x130, page)
            for i, supplied in enumerate((16, 8, 0, 32, 4)):
                house.rate(i, 16)
                struct.pack_into("<H", house.house, 0x54 + i * 2, supplied)
            out = self.check(house)
            self.assertEqual((out.state, out.percent, out.total_weight), (2, 55, 80))
            self.assertEqual(list(out.scores), [128, 64, 0, 128, 32])
            self.assertEqual(house.calls, [])
            struct.pack_into("<H", house.house, 0x52, 0)
            self.assertEqual(self.check(house).state, 1)
        finally:
            self.assertTrue(kernel.VirtualFree(page, 0, 0x8000))
        self.assertEqual(path.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
