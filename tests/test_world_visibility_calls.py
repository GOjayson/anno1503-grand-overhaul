"""Strict visibility call bridges on synthetic PEs and isolated C buffers.

The C compiler interprets the actual original/augmented metadata. Leaf tests
execute only newly generated 16-byte jump stubs in this test process, with a
six-argument recorder. No game binary, running game, save or asset is changed.
"""
import ctypes as C
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from anno1503_overhaul import world_options_visibility_calls as visibility
from anno1503_overhaul.world_runtime_build import BLOBS, ROOT, PE, RuntimeBuildError, blob_metadata
from test_world_visibility_hooks import fixture_pe

SOURCE = ROOT / 'legacy/world_settings' / BLOBS


def call_images():
    images = {name: fixture_pe(index) for index, name in enumerate(sorted({x[0] for x in visibility.CALLS}))}
    for name, data in images.items():
        pe = PE(data)
        sites = [row for row in visibility.CALLS if row[0] == name]
        struct.pack_into('<II', data, pe.optional + 112 + 3 * 8, 0x100000, len(sites) * 12)
        for index, (_, _, rva, before, _) in enumerate(sites):
            at = pe.offset(rva, len(before))
            data[at:at + len(before)] = before
            struct.pack_into('<III', data, pe.offset(0x100000 + index * 12, 12),
                             rva - 8, rva + len(before) + 8, 0x100100)
    return images


def pins(images):
    return {name: hashlib.sha256(data).hexdigest() for name, data in images.items()}


class VisibilityCallPreimageTests(unittest.TestCase):
    def test_fifteen_complete_branches_in_separate_pinned_module_images(self):
        images = call_images()
        before = {name: bytes(data) for name, data in images.items()}
        result = visibility.verify_visibility_call_preimages(images, pins(images))
        expected = {(name, rva, code.hex(), callback) for name, _, rva, code, callback in visibility.CALLS}
        self.assertEqual(len(expected), 15)
        self.assertEqual(result['call_count'], 15)
        self.assertEqual({(x['module'], x['rva'], x['before'], x['callback'])
                          for x in result['call_preimages']}, expected)
        self.assertFalse(result['stack_rewriting'])
        self.assertTrue(result['stack_or_argument_rewriting'])
        self.assertEqual(result['context_argument_copies'], [dict(
            module='AnnoFrame.dll', rva=0x1ca76, source='RDI', destination='RDX')])
        self.assertEqual([(x['module'], x['rva']) for x in result['call_preimages']
                          if x['branch'] == 'tail-jump'], [('AnnoFrame.dll', 0x75b80)])
        self.assertTrue(result['allocation_and_unwind_in_existing_transaction'])
        self.assertEqual(images, before)
        spans = sorted((name, rva, rva + len(code)) for name, _, rva, code, _ in visibility.CALLS)
        for (name, _, end), (other, start, _) in zip(spans, spans[1:]):
            self.assertTrue(name != other or end <= start)

    def test_changed_image_hash_or_instruction_is_rejected(self):
        for name, _, rva, before, _ in visibility.CALLS:
            with self.subTest(module=name, rva=hex(rva)):
                images = call_images()
                original_pins = pins(images)
                images[name][PE(images[name]).offset(rva, len(before))] ^= 1
                with self.assertRaisesRegex(RuntimeBuildError, 'exact native call-site'):
                    visibility.verify_visibility_call_preimages(images, original_pins)
                with self.assertRaisesRegex(RuntimeBuildError, 'dispatch instruction differs'):
                    visibility.verify_visibility_call_preimages(images, pins(images))

    def test_crossing_function_end_noncode_and_nonamd64_are_rejected(self):
        for fault in ('end', 'begin', 'noncode', 'machine'):
            images = call_images()
            name = sorted(images)[0]
            data = images[name]
            pe = PE(data)
            _, _, rva, before, _ = next(row for row in visibility.CALLS if row[0] == name)
            if fault in ('end', 'begin'):
                at = pe.offset(0x100000, 12)
                begin, end, unwind = struct.unpack_from('<III', data, at)
                struct.pack_into('<III', data, at, rva + 1 if fault == 'begin' else begin,
                                 rva + len(before) - 1 if fault == 'end' else end, unwind)
            elif fault == 'noncode':
                struct.pack_into('<I', data, pe.optional + 240 + 36, 0x40000040)
            else:
                struct.pack_into('<H', data, 0x84, 0x14c)
            with self.subTest(fault=fault), self.assertRaises(RuntimeBuildError):
                visibility.verify_visibility_call_preimages(images, pins(images))

    def test_missing_module_or_exception_table_is_rejected(self):
        images = call_images()
        expected = pins(images)
        del images[sorted(images)[0]]
        with self.assertRaises(RuntimeBuildError):
            visibility.verify_visibility_call_preimages(images, expected)
        images = call_images()
        expected = pins(images)
        del expected[sorted(expected)[0]]
        with self.assertRaises(RuntimeBuildError):
            visibility.verify_visibility_call_preimages(images, expected)
        images = call_images()
        data = images[sorted(images)[0]]
        struct.pack_into('<II', data, PE(data).optional + 112 + 3 * 8, 0, 0)
        with self.assertRaisesRegex(RuntimeBuildError, 'exception-function table'):
            visibility.verify_visibility_call_preimages(images, pins(images))


class Relocation(C.Structure):
    _fields_ = [('offset', C.c_uint32)]


class Import(C.Structure):
    _fields_ = [('offset', C.c_uint32), ('name', C.c_char_p)]


class Function(C.Structure):
    _fields_ = [('begin', C.c_uint32), ('end', C.c_uint32), ('unwind', C.c_void_p), ('size', C.c_uint32)]


class Hook(C.Structure):
    _fields_ = [('rva', C.c_uint32), ('length', C.c_uint32), ('before', C.c_void_p),
                ('target', C.c_uint32), ('call', C.c_int)]


class Blob(C.Structure):
    _fields_ = [('module', C.c_wchar_p), ('sha256', C.c_ubyte * 32),
                ('code', C.c_void_p), ('codeSize', C.c_uint32),
                ('relocs', C.POINTER(Relocation)), ('relocCount', C.c_uint32),
                ('imports', C.POINTER(Import)), ('importCount', C.c_uint32),
                ('functions', C.POINTER(Function)), ('functionCount', C.c_uint32),
                ('hooks', C.POINTER(Hook)), ('hookCount', C.c_uint32)]


def record(blob):
    return dict(module=blob.module, digest=bytes(blob.sha256), code=C.string_at(blob.code, blob.codeSize),
                relocs=[blob.relocs[i].offset for i in range(blob.relocCount)],
                imports=[(blob.imports[i].offset, blob.imports[i].name.decode()) for i in range(blob.importCount)],
                functions=[(blob.functions[i].begin, blob.functions[i].end,
                            C.string_at(blob.functions[i].unwind, blob.functions[i].size))
                           for i in range(blob.functionCount)],
                hooks=[(blob.hooks[i].rva, C.string_at(blob.hooks[i].before, blob.hooks[i].length),
                        blob.hooks[i].target, blob.hooks[i].call) for i in range(blob.hookCount)])


class VisibilityCallMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='anno-visibility-leaf-', ignore_cleanup_errors=True)
        folder = Path(cls.temp.name)
        if os.name == 'nt' and (ROOT / '.local/toolchain/ziglang/zig.exe').is_file():
            compiler = [str(ROOT / '.local/toolchain/ziglang/zig.exe'), 'cc']
        else:
            found = shutil.which('cc') or shutil.which('gcc') or shutil.which('clang')
            if not found:
                cls.temp.cleanup()
                raise unittest.SkipTest('Visibility leaf metadata checks need a C compiler.')
            compiler = [found]
        cls.original = SOURCE.read_bytes()
        files = {BLOBS: cls.original, 'unrelated': b'preserved'}
        visibility.apply_visibility_calls(files)
        cls.extended = files[BLOBS]
        if SOURCE.read_bytes() != cls.original or files['unrelated'] != b'preserved':
            raise AssertionError('Visibility staging modified an input.')
        cls.libs = []
        for label, header in (('before', cls.original), ('after', cls.extended)):
            path = folder / (label + '.c')
            source = r'''
#include <stddef.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#define EXPORT __declspec(dllexport)
#else
#include <sys/mman.h>
#define EXPORT
#endif
'''.encode() + header + r'''
EXPORT const WSBlob*fixture_blob(uint32_t i){return i<sizeof wsBlobs/sizeof wsBlobs[0]?&wsBlobs[i]:NULL;}
static uint64_t seen[6];
static uint64_t recorder(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f){seen[0]=a;seen[1]=b;seen[2]=c;seen[3]=d;seen[4]=e;seen[5]=f;return a+3*b+5*c+7*d+11*e+13*f;}
EXPORT int fixture_leaf(uint32_t blob,uint32_t hook,const uint64_t*args,uint64_t*out){
 const WSBlob*b=fixture_blob(blob);if(!b||hook>=b->hookCount)return 0;
 uint32_t target=b->hooks[hook].target;if(target>b->codeSize||16>b->codeSize-target)return 0;
 void*memory;
#ifdef _WIN32
 memory=VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
#else
 memory=mmap(NULL,4096,PROT_READ|PROT_WRITE|PROT_EXEC,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 if(memory==MAP_FAILED)memory=NULL;
#endif
 if(!memory)return 0;memcpy(memory,b->code+target,16);uintptr_t callback=(uintptr_t)recorder;memcpy((unsigned char*)memory+8,&callback,8);
 typedef uint64_t(*Fn)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
 out[6]=((Fn)memory)(args[0],args[1],args[2],args[3],args[4],args[5]);memcpy(out,seen,sizeof seen);
#ifdef _WIN32
 VirtualFree(memory,0,MEM_RELEASE);
#else
 munmap(memory,4096);
#endif
 return 1;}
'''.encode()
            path.write_bytes(source)
            output = folder / (label + ('.dll' if os.name == 'nt' else '.so'))
            command = [*compiler, '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                       '-shared', str(path), '-o', str(output)]
            if os.name != 'nt':
                command.insert(len(compiler), '-fPIC')
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode:
                cls.temp.cleanup()
                raise AssertionError(result.stdout + result.stderr)
            lib = C.CDLL(str(output))
            lib.fixture_blob.argtypes = [C.c_uint32]
            lib.fixture_blob.restype = C.POINTER(Blob)
            lib.fixture_leaf.argtypes = [C.c_uint32, C.c_uint32, C.POINTER(C.c_uint64), C.POINTER(C.c_uint64)]
            cls.libs.append(lib)
        cls.before = [record(cls.libs[0].fixture_blob(i).contents) for i in range(8)]
        cls.after = [record(cls.libs[1].fixture_blob(i).contents) for i in range(8)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_original_parser_contract_is_retained_and_staging_is_once_only(self):
        self.assertEqual(len(blob_metadata(self.original)), 8)
        self.assertEqual(sum(len(x['hooks']) for x in blob_metadata(self.original)), 9)
        with self.assertRaisesRegex(RuntimeBuildError, 'eight native blobs and nine'):
            blob_metadata(self.extended)
        files = {BLOBS: self.extended}
        with self.assertRaises(RuntimeBuildError):
            visibility.apply_visibility_calls(files)
        self.assertEqual(files[BLOBS], self.extended)
        self.assertEqual(SOURCE.read_bytes(), self.original)

    def test_compiler_preserves_old_metadata_and_all_new_branch_contracts(self):
        self.assertEqual(sum(len(x['hooks']) for x in self.after), 24)
        actual = set()
        for prior, current in zip(self.before, self.after):
            self.assertEqual(prior['module'], current['module'])
            self.assertEqual(prior['digest'], current['digest'])
            self.assertEqual(prior['relocs'], current['relocs'])
            self.assertEqual(current['code'][:len(prior['code'])], prior['code'])
            for kind in ('imports', 'functions', 'hooks'):
                self.assertEqual(current[kind][:len(prior[kind])], prior[kind])
            new_hooks = current['hooks'][len(prior['hooks']):]
            if not new_hooks:
                self.assertEqual(prior, current)
                continue
            new_imports = dict(current['imports'][len(prior['imports']):])
            new_functions = current['functions'][len(prior['functions']):]
            self.assertEqual(len(new_hooks), len(new_imports))
            self.assertEqual(len(new_hooks), len(new_functions))
            for (rva, before, target, call), (begin, end, unwind) in zip(new_hooks, new_functions):
                executable, import_offset, function_end = visibility.bridge_layout(current['module'], rva)
                self.assertEqual(target % 16, 0)
                self.assertEqual((begin, end, unwind), (target, target + function_end, b'\x01\0\0\0'))
                self.assertEqual(current['code'][target:target + import_offset + 8], executable + bytes(8))
                self.assertEqual((target + import_offset) % 8, 0)
                self.assertEqual(call, int(visibility.branch_is_call(current['module'], rva)))
                actual.add((current['module'], rva, before, new_imports[target + import_offset]))
        self.assertEqual(actual, {(module, rva, before, callback) for module, _, rva, before, callback in visibility.CALLS})

    def test_plain_leaves_preserve_six_register_and_stack_arguments_and_return(self):
        values = [0x1020304050607080, 0x2131415161718191, 0x32425262728292a2,
                  0x435363738393a3b3, 0x5464748494a4b4c4, 0x65758595a5b5c5d5]
        args = (C.c_uint64 * 6)(*values)
        checksum = sum(x * w for x, w in zip(values, (1, 3, 5, 7, 11, 13))) & ((1 << 64) - 1)
        tested = 0
        for blob, (prior, current) in enumerate(zip(self.before, self.after)):
            for hook in range(len(prior['hooks']), len(current['hooks'])):
                if (current['module'], current['hooks'][hook][0]) == ('AnnoFrame.dll', 0x1ca76):
                    continue  # This separately proved bridge supplies the live RDI context.
                with self.subTest(blob=blob, hook=hook):
                    out = (C.c_uint64 * 7)()
                    self.assertEqual(self.libs[1].fixture_leaf(blob, hook, args, out), 1)
                    self.assertEqual(list(out), [*values, checksum])
                    tested += 1
        self.assertEqual(tested, 14)

    def test_generated_frame_context_leaf_preserves_native_stack_and_nonvolatiles(self):
        private_tools = ROOT / '.local/toolchain/world-options-validation'
        if private_tools.is_dir():
            sys.path.insert(0, str(private_tools))
        try:
            import unicorn as U
            from unicorn import x86_const as X
        except ImportError:
            self.skipTest('The native Win64 context-leaf check needs Unicorn.')
        frame = next(x for x in self.after if any(hook[0] == 0x1ca76 for hook in x['hooks']))
        hook = next(x for x in frame['hooks'] if x[0] == 0x1ca76)
        _, _, target, _ = hook
        code = bytearray(frame['code'][target:target + 24])
        for base in (0x180000000, 0x280000000):
            machine = U.Uc(U.UC_ARCH_X86, U.UC_MODE_64)
            stack, callback, stop = 0x31000000, 0x32000000, 0x32000100
            for at, length in ((base, 0x1000), (stack, 0x2000), (callback, 0x1000)):
                machine.mem_map(at, length)
            struct.pack_into('<Q', code, 16, callback)
            machine.mem_write(base, bytes(code))
            rsp = stack + 0x1008
            stack_bytes = struct.pack('<Q', stop) + bytes(range(1, 97))
            machine.mem_write(rsp, stack_bytes)
            nonvolatile = (X.UC_X86_REG_RBX, X.UC_X86_REG_RBP, X.UC_X86_REG_RSI,
                           X.UC_X86_REG_RDI, X.UC_X86_REG_R12, X.UC_X86_REG_R13,
                           X.UC_X86_REG_R14, X.UC_X86_REG_R15)
            values = {register: 0x102030400 + index * 0x100 for index, register in enumerate(nonvolatile)}
            values.update({X.UC_X86_REG_RSP: rsp, X.UC_X86_REG_RCX: 0x44000000,
                           X.UC_X86_REG_RDX: 0xdeadbeef, X.UC_X86_REG_R8: 123,
                           X.UC_X86_REG_R9: 456})
            for register, value in values.items():
                machine.reg_write(register, value)
            calls = []

            def recorder(cpu, address, size, data):
                if address != callback:
                    return
                calls.append((cpu.reg_read(X.UC_X86_REG_RCX), cpu.reg_read(X.UC_X86_REG_RDX),
                              cpu.reg_read(X.UC_X86_REG_R8), cpu.reg_read(X.UC_X86_REG_R9)))
                self.assertEqual(cpu.reg_read(X.UC_X86_REG_RSP), rsp)
                self.assertEqual(bytes(cpu.mem_read(rsp, len(stack_bytes))), stack_bytes)
                for register in nonvolatile:
                    self.assertEqual(cpu.reg_read(register), values[register])
                cpu.reg_write(X.UC_X86_REG_RAX, 0x12345678abcdef00)
                cpu.reg_write(X.UC_X86_REG_RSP, rsp + 8)
                cpu.reg_write(X.UC_X86_REG_RIP, stop)

            machine.hook_add(U.UC_HOOK_CODE, recorder)
            machine.emu_start(base, stop, count=20)
            self.assertEqual(calls, [(0x44000000, values[X.UC_X86_REG_RDI], 123, 456)])
            self.assertEqual(machine.reg_read(X.UC_X86_REG_RAX), 0x12345678abcdef00)
            self.assertEqual(machine.reg_read(X.UC_X86_REG_RSP), rsp + 8)

    def test_missing_or_duplicate_staging_arrays_fail_without_partial_output(self):
        anchor = b'static const WSFunctionMeta world_policy_functions[]'
        for bad in (self.original.replace(anchor, b'static const WSFunctionMeta unexpected_functions[]', 1),
                    self.original + b'\nstatic const unsigned char world_policy_code[] = {0x90};\n'):
            with self.subTest(duplicate=bad.endswith(b'{0x90};\n')):
                files = {BLOBS: bad}
                with self.assertRaises(RuntimeBuildError):
                    visibility.apply_visibility_calls(files)
                self.assertEqual(files, {BLOBS: bad})


if __name__ == '__main__':
    unittest.main()
