"""Activation parsing and buffer-lifetime tests; no game/process attachment."""
from pathlib import Path
import ctypes as C
import json
import struct
import unittest
from unittest.mock import patch
import activate_world_settings as loader
from pe_exports import exports


class CentralWarHook(unittest.TestCase):
    def test_nine_sites_include_the_central_native_endpoint(self):
        self.assertEqual(sum(len(sites) for sites in loader.HOOK_SITES.values()),9)
        self.assertIn((0xdf460,6),loader.HOOK_SITES['AnnoWelt.dll'])

    def test_only_the_exact_original_preimage_is_accepted(self):
        self.assertEqual(loader.central_hook_state(bytes.fromhex('488bc4895010')),'original')
        for data in [b'',bytes(6),bytes.fromhex('488bc4895011')]:
            self.assertEqual(loader.central_hook_state(data),'changed')

    def test_installed_shape_requires_full_jump_and_padding(self):
        self.assertEqual(loader.central_hook_state(bytes.fromhex('e91122334490')),'guard-jump')
        for data in [bytes.fromhex('e911223344'),bytes.fromhex('e81122334490'),bytes.fromhex('e91122334400')]:
            self.assertEqual(loader.central_hook_state(data),'changed')


class EngineState(unittest.TestCase):
    """Read-only fake sessions exercise every current guarded engine site."""
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads(loader.ENGINE_PLAN.read_bytes())
        assert cls.plan['engine_instruction_count']==len(cls.plan['edits'])>104
        assert set(cls.plan['modules'])=={'AnnoWelt.dll','AnnoFrame.dll'}
        cls.bases={'AnnoWelt.dll':0x280000000,'AnnoFrame.dll':0x380000000}
        cls.mods={name.lower():{'base':base,'size':0x200000} for name,base in cls.bases.items()}

    def address(self,edit):return self.bases[edit['module']]+edit['rva']

    def session(self,which='before',overrides=None):
        values={self.address(edit):bytes.fromhex(edit[which]) for edit in self.plan['edits']}
        values.update(overrides or {})
        class ReadOnlySession:
            def __init__(self):self.calls=[]
            def read(self,address,size):
                self.calls.append((address,size))
                data=values[address]
                return data[:size]
        return ReadOnlySession()

    def classified(self,session):
        result=loader.engine_state(session,self.mods,self.plan)
        self.assertEqual(session.calls,[(self.address(edit),len(bytes.fromhex(edit['before']))) for edit in self.plan['edits']])
        return result

    def test_all_exact_original_or_expanded_sites(self):
        self.assertEqual(self.classified(self.session()),'original')
        self.assertEqual(self.classified(self.session('after')),'expanded')
        self.assertEqual(sum(len(sites) for sites in loader.HOOK_SITES.values()),9)
        self.assertEqual(sum(edit['category']=='world_grid' for edit in self.plan['edits']),104)
        self.assertEqual(sum(edit['module']=='AnnoWelt.dll' for edit in self.plan['edits']),166)
        self.assertGreater(sum(edit['module']=='AnnoFrame.dll' for edit in self.plan['edits']),0)

    def test_each_single_patched_site_in_original_image_is_partial(self):
        for edit in self.plan['edits']:
            with self.subTest(rva=hex(edit['rva'])):
                self.assertNotEqual(edit['before'],edit['after'])
                self.assertEqual(self.classified(self.session(overrides={self.address(edit):bytes.fromhex(edit['after'])})),'changed')

    def test_each_single_original_site_in_expanded_image_is_partial(self):
        for edit in self.plan['edits']:
            with self.subTest(rva=hex(edit['rva'])):
                self.assertEqual(self.classified(self.session('after',{self.address(edit):bytes.fromhex(edit['before'])})),'changed')

    def test_corruption_and_truncated_reads_cannot_report_expanded(self):
        for edit in self.plan['edits']:
            original=bytes.fromhex(edit['after'])
            changed=bytes([original[0]^0x80])+original[1:]
            with self.subTest(rva=hex(edit['rva'])):
                self.assertEqual(self.classified(self.session('after',{self.address(edit):changed})),'changed')
                self.assertEqual(self.classified(self.session('after',{self.address(edit):original[:-1]})),'changed')

    def test_whole_module_mismatch_cannot_report_expanded(self):
        for module in self.bases:
            with self.subTest(module=module):
                before={self.address(edit):bytes.fromhex(edit['before'])
                        for edit in self.plan['edits'] if edit['module']==module}
                after={self.address(edit):bytes.fromhex(edit['after'])
                       for edit in self.plan['edits'] if edit['module']==module}
                self.assertEqual(self.classified(self.session('after',before)),'changed')
                self.assertEqual(self.classified(self.session('before',after)),'changed')

    def test_unknown_or_absent_engine_module_is_rejected(self):
        for module in ['Missing.dll','',None]:
            with self.subTest(module=module):
                session=self.session()
                with self.assertRaises(RuntimeError):
                    loader.engine_state(session,self.mods,{'edits':[
                        {'module':module,'rva':0x1000,'before':'00','after':'01'}]})
        for module in self.mods:
            with self.subTest(missing_loaded_module=module):
                session=self.session()
                with self.assertRaises(RuntimeError):
                    loader.engine_state(session,{k:v for k,v in self.mods.items() if k!=module},self.plan)

    def test_malformed_bounded_site_metadata_is_rejected_before_read(self):
        for before,after in [('', ''),('00','0000'),('00'*33,'01'*33)]:
            with self.subTest(before_length=len(before)):
                session=self.session()
                with self.assertRaisesRegex(RuntimeError,'bounded engine edit plan'):
                    loader.engine_state(session,self.mods,{'edits':[{'module':'AnnoWelt.dll','rva':0x1000,'before':before,'after':after}]})
                self.assertEqual(session.calls,[])


class Exports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=loader.DLL.read_bytes()

    def test_actual_runtime_direct_exports(self):
        values=exports(self.data,loader.REQUIRED)
        self.assertTrue(loader.REQUIRED <= values.keys())
        self.assertEqual(len(values),41)

    def test_malformed_architecture_and_bounds(self):
        pe=struct.unpack_from('<I',self.data,60)[0]
        legacy=bytearray(self.data);struct.pack_into('<H',legacy,pe+4,0x14c)
        for data in [bytes(64),self.data[:128],bytes(legacy),self.data[:1024]]:
            with self.subTest(length=len(data)):
                with self.assertRaises(ValueError):exports(data,loader.REQUIRED)

    def test_missing_required_export(self):
        with self.assertRaises(ValueError):exports(self.data,{'NotAnExport'})

    def test_executable_section_and_eat_above_image_are_rejected(self):
        data=bytearray(self.data)
        pe=struct.unpack_from('<I',data,60)[0];optional=pe+24
        count=struct.unpack_from('<H',data,pe+6)[0]
        optional_size=struct.unpack_from('<H',data,pe+20)[0]
        image_size=struct.unpack_from('<I',data,optional+56)[0]
        sections=[];text=None
        for i in range(count):
            at=optional+optional_size+i*40
            virtual,rva,raw_size,raw=struct.unpack_from('<IIII',data,at+8)
            sections.append((rva,raw_size,raw))
            if data[at:at+8].rstrip(b'\0')==b'.text':text=(at,rva,max(virtual,raw_size))
        def physical(rva):
            return next(raw+rva-base for base,size,raw in sections if base<=rva<base+size)
        export_rva=struct.unpack_from('<I',data,optional+112)[0]
        directory=physical(export_rva)
        function_count=struct.unpack_from('<I',data,directory+20)[0]
        function_at=physical(struct.unpack_from('<I',data,directory+28)[0])
        at,old,extent=text;new=image_size+0x1000;delta=new-old
        struct.pack_into('<I',data,at+12,new)
        for i in range(function_count):
            address=struct.unpack_from('<I',data,function_at+4*i)[0]
            if old<=address<old+extent:struct.pack_into('<I',data,function_at+4*i,address+delta)
        with self.assertRaisesRegex(ValueError,'SizeOfImage'):exports(data,loader.REQUIRED)


class Lifetime(unittest.TestCase):
    def session(self):
        session=loader.Session.__new__(loader.Session)
        session.handle=123;session.incomplete_thread=False
        return session

    def test_timeout_retains_argument(self):
        session=self.session()
        with patch.object(loader,'thread',return_value=456),patch.object(loader,'wait',return_value=258),patch.object(loader,'close'),patch.object(loader,'free') as free:
            with self.assertRaises(RuntimeError):session.remote(111,222)
            session.release(222);free.assert_not_called()

    def test_keyboard_interrupt_retains_argument(self):
        session=self.session()
        with patch.object(loader,'thread',return_value=456),patch.object(loader,'wait',side_effect=KeyboardInterrupt),patch.object(loader,'close'),patch.object(loader,'free') as free:
            with self.assertRaises(KeyboardInterrupt):session.remote(111,222)
            session.release(222);free.assert_not_called()

    def test_completed_thread_allows_argument_release(self):
        session=self.session()
        def completed(handle,out):out._obj.value=1;return 1
        with patch.object(loader,'thread',return_value=456),patch.object(loader,'wait',return_value=0),patch.object(loader,'thread_code',side_effect=completed),patch.object(loader,'close'),patch.object(loader,'free',return_value=1) as free:
            self.assertEqual(session.remote(111,222),1)
            session.release(222);free.assert_called_once_with(123,222,0,0x8000)

    def test_failed_argument_copy_frees_unstarted_buffer(self):
        session=self.session()
        with patch.object(loader,'allocate',return_value=222),patch.object(loader,'write',return_value=0),patch.object(loader,'free',return_value=1) as free:
            with self.assertRaises(OSError):session.buffer(b'test')
            free.assert_called_once_with(123,222,0,0x8000)


if __name__=='__main__':unittest.main(verbosity=2)
