"""Food/World native ownership and PE/unwind checks on synthetic AMD64 images."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from anno1503_overhaul import world_native as native


def stock_image():
    data=bytearray(0x9800)
    data[:2]=b'MZ';struct.pack_into('<I',data,60,0x80)
    data[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<HH',data,0x84,0x8664,3)
    struct.pack_into('<H',data,0x94,240)
    opt=0x98;struct.pack_into('<H',data,opt,0x20b)
    struct.pack_into('<I',data,opt+4,0x9000)
    struct.pack_into('<Q',data,opt+24,0x180000000)
    struct.pack_into('<II',data,opt+32,0x1000,0x200)
    struct.pack_into('<II',data,opt+56,0xd000,0x400)
    struct.pack_into('<I',data,opt+108,16)
    struct.pack_into('<II',data,opt+112+3*8,0xb000,24)
    sections=[(b'.text',0x9000,0x1000,0x9000,0x400,0x60000020),
              (b'.pdata',0x200,0xb000,0x200,0x9400,0x40000040),
              (b'.rdata',0x200,0xc000,0x200,0x9600,0x40000040)]
    for index,(name,vs,rva,size,raw,flags) in enumerate(sections):
        struct.pack_into('<8sIIIIIIHHI',data,0x188+index*40,name,vs,rva,size,raw,0,0,0,0,flags)
    data[0x400:0x9400]=b'\x90'*0x9000
    struct.pack_into('<IIIIII',data,0x9400,0x4000,0x5000,0xc004,0x6000,0x7000,0xc000)
    data[0x9600:0x9608]=bytes.fromhex('0100000001000000')
    for rva in (0x6542,0x48c2):
        at=rva-0x1000+0x400;data[at:at+6]=bytes.fromhex('8986b80a0000')
    return bytes(data)


def food_and_world():
    stock=stock_image();result=bytearray(stock)
    desc=struct.pack('<8sIIIIIIHHI',b'.fmarket',0x200,0xd000,0x200,0x9800,0,0,0,0,0x60000020)
    patches=[dict(offset=0x86,before='0300',after='0400'),
             dict(offset=0x188+3*40,before=bytes(40).hex(),after=desc.hex()),
             dict(offset=0x410,before='9090909090',after='e900000000')]
    for item in patches:
        at=item['offset'];after=bytes.fromhex(item['after']);result[at:at+len(after)]=after
    result.extend(b'\xcc'*0x200)
    food=bytes(result);result[0x440:0x443]=b'\x48\x89\xd8';world=bytes(result)
    entry=dict(name='AnnoFrame.dll',sources={'vanilla':native.sha(stock)},after_sha256=native.sha(food),
               changes={native.sha(stock):dict(patches=patches,append_base64=base64.b64encode(b'\xcc'*0x200).decode(),result_size=len(food))})
    return stock,food,world,entry


def frozen_policy(stock,name):
    data=bytearray(stock)
    store={'CompLogic.dll':0x6542,'CompLogicClassic.dll':0x48c2}[name]
    rva=0xd000;code=native._policy_code(rva,store)
    at=store-0x1000+0x400
    data[at:at+6]=b'\xe9'+struct.pack('<i',rva-store-5)+b'\x90'
    struct.pack_into('<H',data,0x86,4)
    struct.pack_into('<8sIIIIIIHHI',data,0x188+3*40,b'.oldwrld',0x200,rva,0x200,len(stock),0,0,0,0,0x60000020)
    data.extend(code+bytes(0x200-len(code)))
    return bytes(data)


class WorldNativeTests(unittest.TestCase):
    def test_food_body_is_removed_without_moving_or_changing_world_bridges(self):
        stock,food,world,entry=food_and_world()
        self.assertEqual(native._food_forward(stock,entry),food)
        output,proof=native._restore_food_body(stock,food,world,entry)
        self.assertEqual(output[0x410:0x415],stock[0x410:0x415])
        self.assertEqual(output[0x440:0x443],world[0x440:0x443])
        self.assertEqual(output[len(stock):],world[len(stock):])
        self.assertEqual(len(output),len(world))
        self.assertEqual(proof['restored_food_body_edits'][0]['rva'],0x1010)
        self.assertEqual(proof['inert_food_sections'],['.fmarket'])
        self.assertEqual(struct.unpack_from('<I',output,0x98+64)[0],native.checksum(output))

    def test_native_food_world_overlap_is_refused(self):
        stock,food,world,entry=food_and_world();changed=bytearray(world);changed[0x410]^=1
        with self.assertRaisesRegex(native.NativeProfileError,'overlap'):
            native._restore_food_body(stock,food,bytes(changed),entry)

    def test_original_section_relocation_is_refused(self):
        stock,food,world,entry=food_and_world();changed=bytearray(world)
        struct.pack_into('<I',changed,0x188+12,0x2000)
        with self.assertRaisesRegex(native.NativeProfileError,'mapping'):
            native._restore_food_body(stock,food,bytes(changed),entry)

    def test_food_recipe_requires_exact_original_and_after_hash(self):
        stock,food,world,entry=food_and_world()
        with self.assertRaises(native.NativeProfileError):native._food_forward(stock+b'!',entry)
        entry['after_sha256']='0'*64
        with self.assertRaises(native.NativeProfileError):native._food_forward(stock,entry)

    def test_stock_ai_retains_only_world_flag_hook_and_chained_unwind(self):
        for name,store in [('CompLogic.dll',0x6542),('CompLogicClassic.dll',0x48c2)]:
            with self.subTest(name=name):
                stock=stock_image();frozen=frozen_policy(stock,name)
                output,proof=native._policy_ai(stock,frozen,name)
                info=native._pe(stock);at=native._offset(info,store,6)
                self.assertEqual(proof['helper_size'],92)
                self.assertFalse(proof['food_market_demand_production_rewrites'])
                self.assertTrue(proof['frozen_helper_exact'])
                for section in info['sections']:
                    start,end=section['raw'],section['raw']+section['size']
                    expected=bytearray(output[start:end])
                    if start<=at and at+6<=end:expected[at-start:at-start+6]=stock[at:at+6]
                    self.assertEqual(bytes(expected),stock[start:end])
                parsed=native._pe(output);pdata,size=struct.unpack_from('<II',output,0x98+112+3*8)
                pd_at=native._offset(parsed,pdata,size)
                rows=[struct.unpack_from('<III',output,pd_at+i)for i in range(0,size,12)]
                row=next(row for row in rows if row[0]==proof['helper_rva'])
                unwind=native._offset(parsed,row[2],16)
                self.assertEqual(output[unwind:unwind+4],bytes.fromhex('21000000'))
                self.assertEqual(list(struct.unpack_from('<III',output,unwind+4)),proof['chained_unwind_parent'])
                self.assertEqual(struct.unpack_from('<I',output,0x98+64)[0],native.checksum(output))

    def test_frozen_policy_helper_changes_are_refused(self):
        stock=stock_image();frozen=bytearray(frozen_policy(stock,'CompLogic.dll'));frozen[len(stock)+14]^=1
        with self.assertRaisesRegex(native.NativeProfileError,'generator'):
            native._policy_ai(stock,bytes(frozen),'CompLogic.dll')

    def test_missing_setter_unwind_parent_is_refused(self):
        stock=bytearray(stock_image());struct.pack_into('<II',stock,0x9400+12,0x7000,0x7100)
        with self.assertRaisesRegex(native.NativeProfileError,'parent'):
            native._policy_ai(bytes(stock),frozen_policy(stock_image(),'CompLogic.dll'),'CompLogic.dll')

    def test_unknown_ai_and_unpinned_ai_inputs_are_refused(self):
        stock=stock_image()
        for name in ('CompLogic.dll','Unknown.dll'):
            with self.assertRaises(native.NativeProfileError):native.derive_ai_candidate(name,stock,stock)

    def test_checksum_matches_independently_computed_fixture_values(self):
        stock=stock_image()
        self.assertEqual(native.checksum(stock),47928)
        candidate,proof=native._policy_ai(stock,frozen_policy(stock,'CompLogic.dll'),'CompLogic.dll')
        self.assertEqual(native.checksum(candidate),62348)

    def test_unknown_specification_is_refused_before_any_native_input_use(self):
        with self.assertRaisesRegex(native.NativeProfileError,'Unreviewed Food'):
            native.derive_native_profile({}, {}, food_spec=b'{}',world_spec=b'{}')

    def test_frozen_payload_tampering_is_not_authorized_by_its_supplied_inventory(self):
        raw_food=b'{"native_modules":[]}'
        raw_world=json.dumps(dict(version='0.11.0-dev.1',status='UNFINISHED',payloads={'native/example.dll':'0'*64})).encode()
        with patch.object(native,'FOOD_SPEC_SHA256',native.sha(raw_food)),patch.object(native,'WORLD_SPEC_SHA256',native.sha(raw_world)):
            with self.assertRaisesRegex(native.NativeProfileError,'payload fingerprint'):
                native.derive_native_profile({}, {'native/example.dll':stock_image()},food_spec=raw_food,world_spec=raw_world)

    def test_x86_and_truncated_pe_inputs_are_refused(self):
        data=bytearray(stock_image());struct.pack_into('<H',data,0x84,0x14c)
        for value in (bytes(data),b'MZ',stock_image()[:200]):
            with self.assertRaises(native.NativeProfileError):native._pe(value)


if __name__=='__main__':unittest.main()
