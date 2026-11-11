"""Derived readiness logic with synthetic Win32/process/memory collaborators.

No process is enumerated, opened, hidden or activated. Replay the preserved
observer fixtures, then exercise the exact-owned hidden bootstrap exception.
"""
from pathlib import Path
import ast
import struct
import sys
import types
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from anno1503_overhaul import world_only_package as package


def staged_observer():
    files={name:(ROOT/'legacy'/name).read_bytes() for name in
           ('launcher/native_ready.py','launcher/launch_world_settings.pyw')}
    package._launcher_recipe(files,'source','copy')
    module=types.ModuleType('derived_bootstrap_readiness')
    exec(compile(files['launcher/native_ready.py'],'<derived readiness>','exec'),module.__dict__)
    old=(ROOT/'legacy/launcher/developer/evidence/test_native_ready.py').read_bytes()
    tree=ast.parse(old)
    helpers=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))
             and n.name in ('FakeProcess','fake_verify_modules','fixture')]
    if len(helpers)!=3:raise AssertionError('Preserved read-only readiness fixtures changed.')
    namespace=dict(n=module,Path=Path,types=types,struct=struct,
                   REQUIRED_NATIVE={'annoframe.dll','annoscene.dll','annowelt.dll','annogame.dll','view.dll'},
                   BASE=0x180000000,OBJECT=0x200000000,HWND=42,EXE=str(Path('Anno1503.exe').resolve()))
    exec(compile(ast.Module(body=helpers,type_ignores=[]),'<preserved fixture helpers>','exec'),namespace)
    return module,namespace


class HiddenBootstrapReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module,cls.helpers=staged_observer()

    def fixture(self,change=None):
        observer,process=self.helpers['fixture'](change)
        observer.frame_sha=self.module.FRAME_SHA256
        return observer,process

    def test_default_observer_retains_all_eighteen_preserved_classifications(self):
        cases={'valid':'menu','bink':'waiting','closing':'waiting','starting':'waiting',
               'stopped':'waiting','racing':'waiting','backlink':'waiting','code':'unsafe',
               'hash':'unsafe','missing':'waiting','loaded':'unsafe','hidden':'waiting',
               'minimized':'waiting','owner':'waiting','destroyed':'waiting','empty':'waiting',
               'userdata_race':'waiting','unreadable':'waiting'}
        for change,wanted in cases.items():
            observer,process=self.fixture(None if change=='valid' else change)
            with self.subTest(change=change):
                result=observer.inspect(7)
                self.assertEqual(result['state'],wanted)
                self.assertEqual(process.closed,1)
                self.assertEqual(result['menu_proof_verified'],wanted=='menu')

    def test_exact_hidden_or_minimized_owned_menu_keeps_native_identity_proofs(self):
        for change in ('hidden','minimized'):
            observer,process=self.fixture(change)
            with self.subTest(change=change):
                result=observer.inspect_owned_bootstrap(7,(7,123,42,0x200000000))
                self.assertEqual(result['state'],'menu')
                self.assertEqual(result['process_creation_time'],123)
                self.assertEqual((result['hwnd'],result['frame_pointer']),(42,0x200000000))
                self.assertTrue(result['menu_proof_verified'])
                self.assertTrue(result['positive_flags']['native_modules_verified'])
                self.assertTrue(result['positive_flags']['frame_instructions_verified'])
                self.assertTrue(result['positive_flags']['ownership_read_twice'])
                self.assertEqual(process.closed,1)

    def test_hidden_exception_never_accepts_changed_owner_frame_or_native_menu(self):
        for change in ('owner','destroyed','backlink','userdata_race','code','hash','loaded',
                       'bink','starting','closing','stopped','racing','unreadable'):
            observer,process=self.fixture(change)
            observer.windows['visible']=lambda _:False
            with self.subTest(change=change):
                result=observer.inspect_owned_bootstrap(7,(7,123,42,0x200000000))
                self.assertNotEqual(result['state'],'menu')
                self.assertFalse(result['menu_proof_verified'])
                self.assertEqual(process.closed,1)

    def test_wrong_creation_window_and_frame_identity_are_refused(self):
        for token in ((7,124,42,0x200000000),(7,123,43,0x200000000),(7,123,42,0x200000008)):
            observer,process=self.fixture('hidden')
            with self.subTest(token=token):
                result=observer.inspect_owned_bootstrap(7,token)
                self.assertNotEqual(result['state'],'menu')
                self.assertFalse(result['menu_proof_verified'])
                self.assertEqual(process.closed,1)

    def test_malformed_or_foreign_pid_exception_is_rejected_before_process_reads(self):
        for token in (None,(),[7,123,42,0x200000000],(8,123,42,0x200000000),
                      (7,True,42,0x200000000),(7,123,0,0x200000000)):
            observer,process=self.fixture('hidden')
            with self.subTest(token=token),self.assertRaises(RuntimeError):
                observer.inspect_owned_bootstrap(7,token)
            self.assertEqual(process.read_count,0)
            self.assertEqual(process.closed,0)


if __name__=='__main__':unittest.main()
