"""Exact HE faction policy/ABI fixtures; no game process or gameplay tests."""
import ctypes as C
import hashlib
import importlib.util
import itertools
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'.local/toolchain/world-options-validation')]
from anno1503_overhaul import world_options_factions as f
from anno1503_overhaul.world_runtime_build import RuntimeBuildError
from anno1503_overhaul.world_native import derive_ai_candidate


def inputs():
    for profile, pins in f.PROFILE_INPUT_SHA256.items():
        for name, digest in pins.items():
            frozen = ROOT/'.local/baselines/world_settings/native'/name.replace('.dll', '.food-ai.dll')
            stock = ROOT/'.local/game-copies/World Settings'/name
            if not frozen.is_file() or (profile == 'world-only' and not stock.is_file()):
                raise unittest.SkipTest('Exact private HE AI inputs are unavailable.')
            # The installed private copy can legitimately contain this new
            # derivative. Reconstruct its exact predecessor from pinned inputs.
            raw = frozen.read_bytes()
            if profile == 'world-only':
                raw = derive_ai_candidate(name, stock.read_bytes(), raw)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise AssertionError('Local private input differs from its reviewed profile.')
            yield profile, name, raw, digest


class FactionDerivativeTests(unittest.TestCase):
    def test_pins_are_complete_and_profile_specific(self):
        self.assertEqual(set(f.PROFILE_INPUT_SHA256), {'world-only', 'food-world'})
        values = [v for pins in f.PROFILE_INPUT_SHA256.values() for v in pins.values()]
        self.assertEqual(len(set(values)), 4)
        for value in values:
            self.assertRegex(value, r'^[0-9a-f]{64}$')

    def test_exact_derivatives_deterministic_four_counted_edits_no_new_exports(self):
        import pefile
        for profile, name, raw, digest in inputs():
            with self.subTest(profile=profile, name=name):
                output, proof = f.derive_faction_ai(name, raw, digest)
                self.assertEqual((output, proof), f.derive_faction_ai(name, raw, digest))
                self.assertEqual(proof['input_sha256'], hashlib.sha256(raw).hexdigest())
                self.assertEqual(proof['output_sha256'], hashlib.sha256(output).hexdigest())
                self.assertEqual(len(proof['edits']), 4)
                self.assertEqual(proof['exception_entries']-proof['old_exception_entries'], 4)
                old, new = pefile.PE(data=raw), pefile.PE(data=output)
                self.assertEqual(new.sections[-1].Name.rstrip(b'\0'), b'.wsfacts')
                self.assertEqual(old.DIRECTORY_ENTRY_EXPORT.struct.dump(), new.DIRECTORY_ENTRY_EXPORT.struct.dump())
                self.assertTrue(all(row['stack_adjustment'] == 0 for row in proof['functions']))
                for row in proof['functions']:
                    self.assertEqual(row['unwind_bytes'][:8], '01000000' if row['parent'] is None else '21000000')

    def test_unknown_changed_cross_profile_or_second_derivation_refuses(self):
        for profile, name, raw, digest in inputs():
            output, _ = f.derive_faction_ai(name, raw, digest)
            other = f.PROFILE_INPUT_SHA256['food-world' if profile == 'world-only' else 'world-only'][name]
            for value, pin in [(raw[:-1]+bytes([raw[-1]^1]), digest), (raw, other), (output, digest), (raw, '0'*64)]:
                with self.assertRaises(RuntimeBuildError):
                    f.derive_faction_ai(name, value, pin)
        with self.assertRaises(RuntimeBuildError):
            f.derive_faction_ai('Other.dll', b'', '0'*64)


class NativeFactionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import pefile
            from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
            from unicorn import x86_const as X
            import capstone
        except ImportError as exc:
            raise unittest.SkipTest('Local native instruction tools are unavailable.') from exc
        cls.PE, cls.Uc, cls.X, cls.capstone = pefile.PE, Uc, X, capstone
        cls.arch, cls.mode = UC_ARCH_X86, UC_MODE_64
        cls.mapped_images = {}
        cls.variants = []
        for profile, name, raw, digest in inputs():
            output, proof = f.derive_faction_ai(name, raw, digest)
            cls.variants.append((profile, name, raw, output, proof))

    def fixture(self, name, output, proof, base=0x180000000):
        X=self.X;u=self.Uc(self.arch,self.mode);key=(proof['output_sha256'],base)
        if key not in self.mapped_images:
            pe=self.PE(data=output);image=bytearray(pe.get_memory_mapped_image());delta=base-pe.OPTIONAL_HEADER.ImageBase
            if delta:
                for block in pe.DIRECTORY_ENTRY_BASERELOC:
                    for entry in block.entries:
                        if entry.type==10:struct.pack_into('<Q',image,entry.rva,struct.unpack_from('<Q',image,entry.rva)[0]+delta)
            self.mapped_images[key]=bytes(image)
        image=self.mapped_images[key];u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,image)
        ctrl,stack,world,table,player=0x31000000,0x32000000,0x33000000,0x34000000,0x35000000
        for at,size in [(ctrl,0x4000),(stack,0x4000),(world,0x8000),(table,0x1000),(player,0x1000)]:u.mem_map(at,size)
        def put(at,fmt,*values):u.mem_write(at,struct.pack(fmt,*values))
        spec=f.SPEC[name];put(ctrl,'<Q',base+spec['pirate_vtable']);put(ctrl+8,'<Q',world)
        put(ctrl+0xa4c,'<I',15);put(ctrl+0xa64,'<H',6);put(world+0x210,'<Q',table)
        put(table+8+6*8,'<Q',player);put(player+8,'<I',6);put(player+0x18,'<Q',ctrl)
        put(player+0x9c,'<HH',15,11);u.mem_write(player+0x68,b'PIRAT01\0')
        rsp=stack+0x2008;put(rsp,'<Q',0x36000000)
        for register,value in [('RSP',rsp),('RDI',ctrl),('RSI',ctrl),('RCX',ctrl+8),('RDX',96),('R8',6),('R9',6)]:u.reg_write(getattr(X,'UC_X86_REG_'+register),value)
        put(rsp+0x28,'<I',1508);put(rsp+0x30,'<I',10)
        return u,put,ctrl,rsp,player,base,spec,{row['name']:row for row in proof['functions']}

    def test_frequency_modes_native_typ_table_strict_boundaries_and_reserved_refusal(self):
        factors=[25,18,15,12,10,8,6,4]
        for profile,name,raw,output,proof in self.variants:
            for base,typ,frequency,strength in itertools.product([0x180000000,0x280000000],range(8),range(3),range(3)):
                u,put,ctrl,rsp,player,base,spec,functions=self.fixture(name,output,proof,base)
                flags=f.PIRATE_TAG|(frequency<<8)|(strength<<10)|0xa5
                put(ctrl+0xab8,'<I',flags);u.reg_write(self.X.UC_X86_REG_R8,factors[typ])
                u.emu_start(base+functions['pirate_interval']['start'],base+spec['threshold']+7,count=100)
                expected=factors[typ]*[60000,30000,15000][frequency]
                self.assertEqual(u.reg_read(self.X.UC_X86_REG_RAX)&0xffffffff,expected)
                self.assertEqual(u.reg_read(self.X.UC_X86_REG_RSP),rsp)
                self.assertEqual(u.reg_read(self.X.UC_X86_REG_R8),factors[typ])
            for flags,expected in [(0xa5,180000),(f.PIRATE_TAG|0x300,0xffffffff),
                (f.PIRATE_TAG|0xc00,0xffffffff),(f.PIRATE_TAG|0x1000,0xffffffff)]:
                u,put,ctrl,rsp,player,base,spec,functions=self.fixture(name,output,proof)
                put(ctrl+0xab8,'<I',flags);u.reg_write(self.X.UC_X86_REG_R8,6)
                u.emu_start(base+functions['pirate_interval']['start'],base+spec['threshold']+7,count=100)
                self.assertEqual(u.reg_read(self.X.UC_X86_REG_RAX)&0xffffffff,expected)

    def test_creation_only_armament_all_native_counts_and_identity_refusals(self):
        for profile,name,raw,output,proof in self.variants:
            for base,original,mode in itertools.product([0x180000000,0x280000000],range(4,19,2),range(3)):
                u,put,ctrl,rsp,player,base,spec,functions=self.fixture(name,output,proof,base)
                put(ctrl+0xab8,'<I',f.PIRATE_TAG|0x100|(mode<<10)|9);put(rsp+0x30,'<I',original)
                before=bytes(u.mem_read(ctrl,0x3000))
                u.emu_start(base+functions['new_pirate_armament']['start'],base+spec['create'],count=150)
                expected=max(4,original//2) if mode==0 else original if mode==1 else min(18,original+(original+1)//2)
                self.assertEqual(struct.unpack('<I',u.mem_read(rsp+0x30,4))[0],expected)
                self.assertEqual(bytes(u.mem_read(ctrl,0x3000)),before)
                self.assertEqual(u.reg_read(self.X.UC_X86_REG_RSP),rsp)
                self.assertEqual([u.reg_read(getattr(self.X,'UC_X86_REG_'+r)) for r in ['RCX','RDX','R8','R9']],[ctrl+8,96,6,6])
            for fault in ['vtable','type','owner','definition','alias','player_type','culture','player_owner','player_controller']:
                u,put,ctrl,rsp,player,base,spec,functions=self.fixture(name,output,proof)
                put(ctrl+0xab8,'<I',f.PIRATE_TAG|0x100)
                locations={'vtable':(ctrl,'<Q',base+spec['pirate_vtable']+8),'type':(ctrl+0xa4c,'<I',12),
                    'owner':(ctrl+0xa64,'<H',5),'definition':(rsp+0x28,'<I',1504),'alias':(player+0x68,'<Q',0),
                    'player_type':(player+0x9c,'<H',12),'culture':(player+0x9e,'<H',1),
                    'player_owner':(player+8,'<I',7),'player_controller':(player+0x18,'<Q',ctrl+8)}
                put(*locations[fault]);u.emu_start(base+functions['new_pirate_armament']['start'],base+spec['create'],count=150)
                self.assertEqual(struct.unpack('<I',u.mem_read(rsp+0x30,4))[0],10,fault)

    def test_special_setter_preserves_native_low_updates_and_transports_invalid_save_for_validation(self):
        for profile,name,raw,output,proof in self.variants:
            for typ,old,incoming in itertools.product([12,15,16],[0,0xa5,0x575305a5,0x575409a5,0x575501a5],
                                                     [0,0x89,0x57540955,0x57550355,0x5754f055]):
                u,put,ctrl,rsp,player,base,spec,functions=self.fixture(name,output,proof)
                vt=spec['merchant_vtable'] if typ==16 else spec['pirate_vtable']
                if typ==12:vt=0x84fc8 if 'Classic' in name else 0x88128
                put(ctrl,'<Q',base+vt);put(ctrl+0xa4c,'<I',typ);put(ctrl+0xab8,'<I',old)
                u.reg_write(self.X.UC_X86_REG_RAX,incoming)
                u.emu_start(base+functions['special_native_flag_preserver']['start'],base+spec['setter']+6,count=150)
                tag={12:0x57530000,15:f.PIRATE_TAG,16:f.MERCHANT_TAG}[typ]
                if typ==12:
                    expected=(old&0xffffff00)|(incoming&255) if old&0xffff0000==tag and incoming&0xffff0000!=tag else incoming
                else:
                    expected=(old&0xffffff00)|incoming if old&0xffff0000==tag and not incoming&0xffffff00 else incoming
                self.assertEqual(struct.unpack('<I',u.mem_read(ctrl+0xab8,4))[0],expected,(profile,name,typ,hex(old),hex(incoming)))
                self.assertEqual(u.reg_read(self.X.UC_X86_REG_RSP),rsp)

    def test_actual_native_comp_serialization_and_parser_preserve_full_special_policy_words(self):
        from unicorn import UC_HOOK_CODE
        import re
        X=self.X
        for profile,name,raw,output,proof in self.variants:
            pe=self.PE(data=output);image=pe.get_memory_mapped_image();classic='Classic' in name
            for base,typ in itertools.product([0x180000000,0x280000000],[15,16]):
                u,put,ctrl,rsp,player,base,spec,functions=self.fixture(name,output,proof,base)
                vt=spec['pirate_vtable'] if typ==15 else spec['merchant_vtable']
                put(ctrl,'<Q',base+vt);put(ctrl+0xa4c,'<I',typ)
                save,load=[struct.unpack_from('<Q',image,vt+offset)[0]-pe.OPTIONAL_HEADER.ImageBase for offset in (0x28,0x30)]
                io,io_vt,out,fake_world,fake_wvt,fake_table,fake_tvt,fake_player,fake_pvt,ext=0x37000000,0x37001000,0x37002000,0x37003000,0x3700b000,0x3700c000,0x3700d000,0x3700e000,0x3700f000,0x38000000
                u.mem_map(io,0x20000);u.mem_map(ext,0x10000)
                put(ctrl+8,'<Q',fake_world);put(fake_world,'<Q',fake_wvt);put(fake_table,'<Q',fake_tvt);put(fake_player,'<Q',fake_pvt)
                put(fake_wvt+0x98,'<Q',ext+0x100);put(fake_wvt+0x150,'<Q',ext+0x120)
                put(fake_tvt+0x10,'<Q',ext+0x140);put(fake_tvt+0x18,'<Q',ext+0x160);put(fake_pvt+0x228,'<Q',ext+0x180)
                put(fake_pvt+0x98,'<Q',ext+0x1a0)
                put(io,'<Q',io_vt);put(io_vt,'<QQ',ext+0x200,ext+0x220)
                output_chunks=[];input_text=[b''];imports={}
                for descriptor in pe.DIRECTORY_ENTRY_IMPORT:
                    for item in descriptor.imports:
                        if item.name not in (b'strchr',b'strrchr',b'strncmp',b'atoi',b'atol'):continue
                        stub=ext+0x300+16*len(imports);imports[stub]=item.name.decode();put(base+item.address-pe.OPTIONAL_HEADER.ImageBase,'<Q',stub)
                printf=0x1010 if classic else 0x2f00;memset=0x82532 if classic else 0x85a42;probe=0x825a0 if classic else 0x85ab0
                def string(address):
                    value=bytearray()
                    for index in range(8192):
                        byte=bytes(u.mem_read(address+index,1))
                        if byte==b'\0':return bytes(value)
                        value+=byte
                    raise AssertionError('Fixture string is unbounded.')
                def returned(machine,value):
                    sp=machine.reg_read(X.UC_X86_REG_RSP);target=struct.unpack('<Q',machine.mem_read(sp,8))[0]
                    machine.reg_write(X.UC_X86_REG_RAX,value&0xffffffffffffffff);machine.reg_write(X.UC_X86_REG_RSP,sp+8);machine.reg_write(X.UC_X86_REG_RIP,target)
                def primitive(machine,address,size,data):
                    rcx=machine.reg_read(X.UC_X86_REG_RCX);rdx=machine.reg_read(X.UC_X86_REG_RDX);r8=machine.reg_read(X.UC_X86_REG_R8);r9=machine.reg_read(X.UC_X86_REG_R9)
                    if address==base+probe:returned(machine,machine.reg_read(X.UC_X86_REG_RAX))
                    elif address==base+memset:machine.mem_write(rcx,bytes([rdx&255])*r8);returned(machine,rcx)
                    elif address==base+printf:
                        fmt=string(r8).decode();args=[]
                        for index,kind in enumerate(re.findall(r'%[dius]',fmt)):
                            value=r9 if not index else struct.unpack('<Q',machine.mem_read(machine.reg_read(X.UC_X86_REG_RSP)+0x28+(index-1)*8,8))[0]
                            args.append(string(value).decode() if kind=='%s' else struct.unpack('<i',struct.pack('<I',value&0xffffffff))[0])
                        text=(fmt%tuple(args)).encode();self.assertLess(len(text),rdx);machine.mem_write(rcx,text+b'\0');returned(machine,len(text))
                    elif address==ext+0x100:machine.mem_write(r8+8,bytes(4));returned(machine,1)
                    elif address==ext+0x120:returned(machine,fake_table)
                    elif address==ext+0x140:returned(machine,1)
                    elif address==ext+0x160:returned(machine,fake_player)
                    elif address==ext+0x180:returned(machine,1)
                    elif address==ext+0x1a0:machine.mem_write(r8+8,struct.pack('<I',typ));returned(machine,1)
                    elif address==ext+0x200:
                        output_chunks.append(bytes(machine.mem_read(rdx,r8)));machine.mem_write(r9,struct.pack('<I',r8));returned(machine,1)
                    elif address==ext+0x220:
                        self.assertEqual(r8,len(input_text[0]));machine.mem_write(rdx,input_text[0]);machine.mem_write(r9,struct.pack('<I',r8));returned(machine,1)
                    elif address in imports:
                        kind=imports[address]
                        if kind in ('strchr','strrchr'):
                            text=string(rcx);at=(text.rfind if kind=='strrchr' else text.find)(bytes([rdx&255]));returned(machine,rcx+at if at>=0 else 0)
                        elif kind=='strncmp':
                            left,right=bytes(machine.mem_read(rcx,r8)).split(b'\0')[0],bytes(machine.mem_read(rdx,r8)).split(b'\0')[0];returned(machine,(left>right)-(left<right))
                        else:returned(machine,int(string(rcx)))
                for target in [base+printf,base+memset,base+probe,*[ext+x for x in (0x100,0x120,0x140,0x160,0x180,0x1a0,0x200,0x220)],*imports]:
                    u.hook_add(UC_HOOK_CODE,primitive,begin=target,end=target)
                stop=ext+0xf000
                recent=[]
                def trace(machine,address,size,data):
                    recent.append(address);del recent[:-12]
                u.hook_add(UC_HOOK_CODE,trace)
                def call(at,rcx,rdx,r8):
                    put(rsp,'<Q',stop)
                    for register,value in [('RSP',rsp),('RCX',rcx),('RDX',rdx),('R8',r8),('R9',out)]:u.reg_write(getattr(X,'UC_X86_REG_'+register),value)
                    try:u.emu_start(base+at,stop,count=100000)
                    except Exception as exc:raise AssertionError((profile,name,typ,hex(base),hex(at),hex(u.reg_read(X.UC_X86_REG_RIP)),[hex(x-base)for x in recent])) from exc
                    self.assertEqual(u.reg_read(X.UC_X86_REG_RIP),stop)
                    return u.reg_read(X.UC_X86_REG_RAX)&0xffffffff
                policies=[0xa5]+([f.PIRATE_TAG|(freq<<8)|(strength<<10)|0xa5 for freq,strength in itertools.product(range(3),range(3))] if typ==15 else [f.MERCHANT_TAG|(freq<<8)|0xa5 for freq in range(3)])
                for flags in policies:
                    output_chunks.clear();put(ctrl+0xab8,'<I',flags)
                    self.assertEqual(call(save,ctrl,io,out),1)
                    tokens=b''.join(output_chunks).split(b'\0');token=('SPEZFLAG='+str(flags)).encode()
                    self.assertIn(token,tokens)
                    input_text[0]=token+b'\0';put(ctrl+0xab8,'<I',0)
                    self.assertEqual(call(load,ctrl,io,len(input_text[0])),1)
                    self.assertEqual(struct.unpack('<I',u.mem_read(ctrl+0xab8,4))[0],flags)

    @unittest.skipUnless(os.name=='nt','Windows native unwind API is required.')
    def test_windows_unwind_at_every_gate_instruction_matches_original_native_context(self):
        class Function(C.Structure):
            _fields_=[('begin',C.c_uint32),('end',C.c_uint32),('unwind',C.c_uint32)]
        virtual=C.WinDLL('ntdll').RtlVirtualUnwind
        virtual.argtypes=[C.c_uint32,C.c_uint64,C.c_uint64,C.POINTER(Function),C.c_void_p,C.POINTER(C.c_void_p),C.POINTER(C.c_uint64),C.c_void_p]
        decoder=self.capstone.Cs(self.capstone.CS_ARCH_X86,self.capstone.CS_MODE_64)
        for profile,name,raw,output,proof in self.variants:
            image=self.PE(data=output).get_memory_mapped_image();memory=C.create_string_buffer(image);base=C.addressof(memory)
            original_memory=C.create_string_buffer(self.PE(data=raw).get_memory_mapped_image());original_base=C.addressof(original_memory)
            stack=(C.c_uint64*512)(*[0x1100000000000000+i for i in range(512)])
            def unwind(entry,pc,image_base):
                storage=C.create_string_buffer(1264);ctx=(C.addressof(storage)+15)&~15
                C.c_uint32.from_address(ctx+48).value=0x10000b
                C.c_uint64.from_address(ctx+152).value=C.addressof(stack)
                C.c_uint64.from_address(ctx+248).value=image_base+pc
                for offset in range(120,248,8):
                    if offset!=152:C.c_uint64.from_address(ctx+offset).value=0x22330000+offset
                handler=C.c_void_p();frame=C.c_uint64()
                virtual(0,image_base,image_base+pc,C.byref(Function(*entry)),ctx,C.byref(handler),C.byref(frame),None)
                return bytes(C.string_at(ctx+120,136))
            for row in proof['functions']:
                reference_pc=f.SPEC[name][{'pirate_interval':'threshold','merchant_native_fleet_target':'merchant','special_native_flag_preserver':'setter'}.get(row['name'],'spawn')]
                # The approved input setter already starts with its old E9
                # hook; use the unchanged native continuation as the active
                # frame reference, not that branch's tail-epilogue decoding.
                if row['name']=='special_native_flag_preserver':reference_pc+=6
                reference=unwind(row['parent'],reference_pc,original_base) if row['parent'] else None
                for ins in decoder.disasm(image[row['start']:row['end']],row['start']):
                    actual=unwind((row['start'],row['end'],row['unwind']),ins.address,base)
                    if reference is not None:self.assertEqual(actual,reference,(profile,name,row['name'],hex(ins.address)))
                    else:
                        self.assertEqual(struct.unpack_from('<Q',actual,128)[0],stack[0])


SOURCE = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static unsigned char *worldModule,*approvedModule,*world,*table,*players[2],*controllers[2];
static DWORD priorProtection;static int readonlyIndex=-1;
static int memoryRange(const void*p,size_t size,int write){
 uintptr_t at=(uintptr_t)p,end;if(!at||size>UINTPTR_MAX-at)return 0;end=at+size;
 while(at<end){MEMORY_BASIC_INFORMATION m;if(!VirtualQuery((void*)at,&m,sizeof m)||m.State!=MEM_COMMIT||m.Protect&(PAGE_GUARD|PAGE_NOACCESS))return 0;
 DWORD v=m.Protect&255u;if(write?(v!=PAGE_READWRITE&&v!=PAGE_WRITECOPY&&v!=PAGE_EXECUTE_READWRITE&&v!=PAGE_EXECUTE_WRITECOPY):(v!=PAGE_READONLY&&v!=PAGE_READWRITE&&v!=PAGE_WRITECOPY&&v!=PAGE_EXECUTE_READ&&v!=PAGE_EXECUTE_READWRITE&&v!=PAGE_EXECUTE_WRITECOPY))return 0;
 uintptr_t base=(uintptr_t)m.BaseAddress;if(m.RegionSize>UINTPTR_MAX-base||base+m.RegionSize<=at)return 0;at=base+m.RegionSize;
 }return 1;
}
static int wsAIRead(const void*p,void*out,size_t size){if(!out||!memoryRange(p,size,0))return 0;memcpy(out,p,size);return 1;}
static int wsAIWritable(const void*p,size_t size){return memoryRange(p,size,1);}
static void*wsAIPointer(const void*p,size_t offset){void*out=NULL;if(p&&offset<=UINTPTR_MAX-(uintptr_t)p)wsAIRead((const unsigned char*)p+offset,&out,sizeof out);return out;}
static int wsAIError(char*out,uint32_t size,const char*message){if(out&&size)snprintf(out,size,"%s",message);return 0;}
#define WS_AI_WORLD_MODULE() worldModule
#define WS_FACTION_ACTIVITY_APPROVED_MODULE() approvedModule
#include "faction_activity.inc"
static void put(void*p,size_t offset,uintptr_t v){memcpy((unsigned char*)p+offset,&v,8);}
static void put32(void*p,size_t offset,uint32_t v){memcpy((unsigned char*)p+offset,&v,4);}
static void put16(void*p,size_t offset,uint16_t v){memcpy((unsigned char*)p+offset,&v,2);}
static void writableAgain(void){if(readonlyIndex>=0){DWORD ignored;VirtualProtect(controllers[readonlyIndex],4096u,priorProtection,&ignored);readonlyIndex=-1;}}
__declspec(dllexport) int fixture_setup(uint32_t factions,int classic){
 writableAgain();WorldSettingsResetFactionActivity();
 if(!worldModule){worldModule=VirtualAlloc(NULL,0x110000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);approvedModule=VirtualAlloc(NULL,0xa0000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);world=VirtualAlloc(NULL,0x8000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);table=VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
  for(int i=0;i<2;i++){players[i]=VirtualAlloc(NULL,4096,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);controllers[i]=VirtualAlloc(NULL,0x3000,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);}
 }
 if(!worldModule||!approvedModule||!world||!table||!players[0]||!players[1]||!controllers[0]||!controllers[1])return 0;
 memset(worldModule,0,0x110000);memset(approvedModule,0,0xa0000);memset(world,0,0x8000);memset(table,0,4096);
 put(world,0,(uintptr_t)(worldModule+0xff650));put(world,0x210,(uintptr_t)table);put(worldModule+0xff650,0xf0,(uintptr_t)(worldModule+0xd1910));
 put(table,0,(uintptr_t)(worldModule+0xfdbc0));put(worldModule+0xfdbc0,0x10,(uintptr_t)(worldModule+0xc6d80));put(worldModule+0xfdbc0,0x18,(uintptr_t)(worldModule+0x95990));
 for(uint32_t i=0;i<2;i++){
  memset(players[i],0,4096);memset(controllers[i],0,0x3000);if(!(factions&(1u<<i)))continue;
  uint32_t type=15u+i,id=6u-i,vt=classic?(i?0x85258u:0x85aa0u):(i?0x883c0u:0x88ba8u);
  put(table,8u+id*8u,(uintptr_t)players[i]);put(players[i],0,(uintptr_t)(worldModule+0xfabe0));put32(players[i],8,id);put(players[i],0x10,(uintptr_t)world);put(players[i],0x18,(uintptr_t)controllers[i]);
  put16(players[i],0x9c,(uint16_t)type);put16(players[i],0x9e,(uint16_t)(11u+i));memcpy(players[i]+0x68,i?"VENEZIA01":"PIRAT01",i?10u:8u);
  put(controllers[i],0,(uintptr_t)(approvedModule+vt));put(controllers[i],8,(uintptr_t)world);put32(controllers[i],0xa4c,type);put16(controllers[i],0xa64,(uint16_t)id);put32(controllers[i],0xab8,0xa5u+i);
  put(approvedModule+vt,0,(uintptr_t)(approvedModule+(classic?0x6480u:0x80e0u)));put(approvedModule+vt,8,(uintptr_t)(approvedModule+(classic?0x4260u:0x6090u)));put(approvedModule+vt,0x10,(uintptr_t)(approvedModule+(classic?0x4a10u:0x6640u)));
 }return 1;
}
__declspec(dllexport) void fixture_fault(int fault){
 switch(fault){case 1:put16(players[0],0x9e,12);break;case 2:put16(controllers[0],0xa64,5);break;
 case 3:put(controllers[0],8,(uintptr_t)(world+8));break;case 4:put32(controllers[0],0xa4c,12);break;
 case 5:players[0][0x68]='X';break;case 6:put(controllers[0],0,(uintptr_t)(approvedModule+0x88128));break;
 case 7:put32(controllers[1],0xab8,0x100u);break;
 case 8:if(VirtualProtect(controllers[1],4096u,PAGE_READONLY,&priorProtection))readonlyIndex=1;break;
 case 9:put(table,8u+7u*8u,(uintptr_t)players[0]);break;
 case 10:put32(players[0],8,5);break;
 case 11:put(worldModule+0xfdbc0,0x10,(uintptr_t)(worldModule+0xc6d81));break;
 case 12:put(approvedModule+0x88ba8,8,(uintptr_t)(approvedModule+0x6091));break;
 }
}
__declspec(dllexport) int fixture_bind(uint32_t factions,int frequency,int strength,int merchant){char error[512];WorldSettingsExpectFactionActivity(factions,frequency,strength,merchant);return WorldSettingsBindFactionActivity(world,approvedModule,error,sizeof error);}
__declspec(dllexport) int fixture_bind_again(void){char error[512];return WorldSettingsBindFactionActivity(world,approvedModule,error,sizeof error);}
__declspec(dllexport) uint32_t fixture_flags(int index){uint32_t out=0;memcpy(&out,controllers[index]+0xab8,4);return out;}
__declspec(dllexport) void fixture_saved_flags(int index,uint32_t value){put32(controllers[index],0xab8,value);}
__declspec(dllexport) int fixture_validate(void){char error[512];return WorldSettingsValidateFactionActivityWorld(world,error,sizeof error);}
__declspec(dllexport) int fixture_decode(uint32_t flags,uint32_t type){uint32_t frequency=99,strength=99;return wsFactionActivityDecode(flags,type,&frequency,&strength)?(int)(frequency+strength*3u):-1;}
__declspec(dllexport) void fixture_cancel(void){WorldSettingsExpectFactionActivity(3,0,0,0);WorldSettingsResetFactionActivity();}
__declspec(dllexport) void fixture_close(void){writableAgain();for(int i=0;i<2;i++){if(players[i])VirtualFree(players[i],0,MEM_RELEASE);if(controllers[i])VirtualFree(controllers[i],0,MEM_RELEASE);players[i]=controllers[i]=NULL;}if(worldModule)VirtualFree(worldModule,0,MEM_RELEASE);if(approvedModule)VirtualFree(approvedModule,0,MEM_RELEASE);if(world)VirtualFree(world,0,MEM_RELEASE);if(table)VirtualFree(table,0,MEM_RELEASE);worldModule=approvedModule=world=table=NULL;}
'''


def staged_sources():
    from anno1503_overhaul.world_options import apply_options
    import json
    provenance=json.loads((ROOT/'provenance/legacy_import.json').read_bytes())
    files={row['path'].removeprefix('legacy/world_settings/'):(ROOT/row['path']).read_bytes()
           for row in provenance['source_files'] if row['path'].startswith('legacy/world_settings/')}
    return files,apply_options(files)


def staged_function(text, name):
    start=text.rfind('\n',0,text.index(name+'('))+1
    begin=text.index('{',text.index(name+'(',start));end=begin+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]


def lifecycle_source():
    _,staged=staged_sources();text=staged[f.PRIVATE+'world_ai.c'].decode()
    names=('WorldSettingsBeginNativeWorldStart','WorldSettingsEndNativeWorldStart',
           'WorldSettingsExpectAIProfiles','WorldSettingsAIProfileAttemptFinished',
           'WorldSettingsAfterProfiles','WorldSettingsBindAIProfileWorld')
    code='\n'.join(staged_function(text,name) for name in names)
    prelude=r'''
static int wsProfilesExpected=-1;static int32_t wsDiplomacyExpected;static char wsProfileError[512];static volatile LONG wsProfileStatus;
static uint32_t wsNativeSequence,wsNativeActive,wsFactionsExpected,wsNativeFactions;static int wsNativeExpected,wsNativeChecked;static void*wsNativeWorld;
static int WorldSettingsIsActive(void){return 1;}
void WorldSettingsAIProfileAttemptFinished(int);
static void WorldSettingsFinishAttempt(int success){WorldSettingsAIProfileAttemptFinished(success);}
static void WorldSettingsVisibilityReset(void){}
/* These finalizers have independent compiled lifecycle/rollback fixtures.
 * This fixture retains their typed call boundary while testing faction state. */
static void WorldSettingsFinishDisasterAttempt(int complete){(void)complete;}
static int WorldSettingsFinishNativeSetup(int complete){(void)complete;return 1;}
static void*WorldSettingsLoadedAIModule(void){return approvedModule;}
static int WorldSettingsCheckAIControllers(void*w,int n,void*a,char*e,uint32_t c){(void)w;(void)n;(void)a;(void)e;(void)c;return 1;}
static int WorldSettingsCheckSpecialControllers(void*w,uint32_t n,void*a,char*e,uint32_t c){(void)w;(void)n;(void)a;(void)e;(void)c;return 1;}
static int WorldSettingsBindAIDiplomacy(void*w,int n,int m,void*a,char*e,uint32_t c){(void)w;(void)n;(void)m;(void)a;(void)e;(void)c;return 1;}
static int WorldSettingsValidateChosenDisasters(void*w,char*e,uint32_t c){(void)w;(void)e;(void)c;return 1;}
/* This fixture isolates faction lifecycle; disaster binding has its own native fixtures. */
static int WorldSettingsBindDisasterOptions(void*w,char*e,uint32_t c){(void)w;(void)e;(void)c;return 1;}
#undef MessageBoxA
#define MessageBoxA(a,b,c,d) ((void)0)
'''
    post=r'''
__declspec(dllexport) int fixture_lifecycle(int failure){
 unsigned char scene[0x168]={0};char error[512];put(scene,0x160,(uintptr_t)world);
 WorldSettingsExpectFactionActivity(3,2,0,0);WorldSettingsExpectAIProfiles(0,3,1);
 uint32_t token=WorldSettingsBeginNativeWorldStart();if(!token)return 1;
 if(!WorldSettingsBindAIProfileWorld(scene,error,sizeof error))return 2;
 if(failure)fixture_fault(5);
 int valid=WorldSettingsAfterProfiles(world);int ended=WorldSettingsEndNativeWorldStart(token,!failure);
 if(failure){if(valid||ended||wsFactionActivityExpected)return 3;}
 else if(!valid||!ended||wsFactionActivityExpected)return 4;
 return 0;
}
__declspec(dllexport) int fixture_original_after_cancel(void){
 /* Generation chooser calls this exact finalizer before Original/tutorial/
  * campaign start. Conflicting native factions must not acquire old choices. */
 WorldSettingsExpectFactionActivity(3,2,2,2);WorldSettingsExpectAIProfiles(3,3,3);
 WorldSettingsFinishAttempt(0);
 if(wsFactionActivityExpected||wsProfilesExpected>=0)return 1;
 uint32_t token=WorldSettingsBeginNativeWorldStart();if(!token||wsNativeExpected)return 2;
 if(!WorldSettingsAfterProfiles(world))return 3;
 if(!WorldSettingsEndNativeWorldStart(token,1))return 4;
 return wsFactionActivityExpected?5:0;
}
__declspec(dllexport) void fixture_stage_old_choices(void){WorldSettingsExpectFactionActivity(3,2,2,2);WorldSettingsExpectAIProfiles(3,3,3);}
__declspec(dllexport) int fixture_old_choices_pending(void){return wsFactionActivityExpected&&wsProfilesExpected>=0;}
'''
    return prelude+code+post


def load_boundary_source():
    """Execute the actual final staged AfterLoad with bounded I/O substitutes.

    Faction validation remains the real compiled certificate above, including
    controller identities and tags. File/chart/disaster boundaries are counted
    substitutes; their independent native fixtures test their implementation.
    """
    _,staged=staged_sources()
    code=staged_function(staged[f.PRIVATE+'start_visibility_memory_io.inc'].decode(),
                         'WorldSettingsVisibilityAfterLoad')
    prelude=r'''
typedef struct WSMemoryFile {uint32_t width,height,policy;unsigned char guid[16];} WSMemoryFile;
typedef struct WSMemoryPendingLoad {void*data;HANDLE file;BY_HANDLE_FILE_INFORMATION info;WSMemoryFile parsed;} WSMemoryPendingLoad;
typedef struct WSVisibilityWorld {unsigned char*world;uint32_t width,height,flags;int marked;} WSVisibilityWorld;
typedef struct WSDisasterContext {int placeholder;} WSDisasterContext;
static WSMemoryPendingLoad wsMemoryLoad;
static int loadMarked,loadCounts[6];
#define WS_VISIBILITY_POLICY_MASK 0x7000u
static void*wsCertPointer(const void*p,size_t offset){return wsAIPointer(p,offset);}
static int wsCertRead(const void*p,void*out,size_t size){return wsAIRead(p,out,size);}
static int wsMemoryRegular(HANDLE file,BY_HANDLE_FILE_INFORMATION*out){(void)file;(void)out;return 1;}
static int wsMemorySameFile(const BY_HANDLE_FILE_INFORMATION*a,const BY_HANDLE_FILE_INFORMATION*b){(void)a;(void)b;return 1;}
static int wsVisibilityWorldRead(void*object,WSVisibilityWorld*out){
 loadCounts[0]++;if(object!=world)return 0;
 *out=(WSVisibilityWorld){world,1024,1024,loadMarked?0x1000u:0u,loadMarked};return 1;
}
static int wsMemoryError(char*error,uint32_t cap,const char*message){return wsAIError(error,cap,message);}
static void wsDisasterClearLoaded(void){loadCounts[1]++;}
static int wsDisasterLoadContext(void*w,const WSMemoryFile*f,WSDisasterContext*out,char*e,uint32_t c){
 (void)w;(void)f;(void)out;(void)e;(void)c;loadCounts[2]++;return 1;
}
static int WorldSettingsVisibilityApplyBlob(void*w,char*e,uint32_t c){(void)w;(void)e;(void)c;loadCounts[3]++;return 1;}
static void wsDisasterPublish(const WSDisasterContext*c){(void)c;loadCounts[4]++;}
static void WorldSettingsVisibilityCancelLoad(void){wsMemoryLoad.data=NULL;loadCounts[5]++;}
'''
    post=r'''
__declspec(dllexport) int fixture_after_load(int pending,int marked,int badIdentity){
 unsigned char scene[0x168]={0};char error[512];put(scene,0x160,(uintptr_t)world);
 memset(&wsMemoryLoad,0,sizeof wsMemoryLoad);memset(loadCounts,0,sizeof loadCounts);loadMarked=marked;
 if(pending){wsMemoryLoad.data=(void*)1;wsMemoryLoad.file=(HANDLE)1;wsMemoryLoad.parsed.width=1024;
  wsMemoryLoad.parsed.height=1024;wsMemoryLoad.parsed.policy=marked?0x1000u:0u;}
 if(badIdentity)wsMemoryLoad.parsed.guid[0]=1;
 return WorldSettingsVisibilityAfterLoad(scene,error,sizeof error);
}
__declspec(dllexport) int fixture_load_count(int index){return index>=0&&index<6?loadCounts[index]:-1;}
'''
    return prelude+code+post


class FactionStagingTests(unittest.TestCase):
    def test_staging_preserves_draw_sources_and_separates_fresh_from_load(self):
        original,staged=staged_sources()
        ai=staged[f.PRIVATE+'world_ai.c'].decode();menu=staged[f.PRIVATE+'WorldSettings.c'].decode()
        self.assertIn('WorldSettingsExpectFactionActivity(d->settings.factions',menu)
        begin=ai.split('WorldSettingsBeginNativeWorldStart(void){',1)[1].split('return wsNativeActive;',1)[0]
        self.assertNotIn('WorldSettingsResetFactionActivity',begin)
        self.assertLess(ai.index('valid=WorldSettingsCheckSpecialControllers'),ai.index('valid=WorldSettingsBindFactionActivity'))
        memory=staged[f.PRIVATE+'start_visibility_memory_io.inc'].decode()
        boundary=memory.split('WorldSettingsVisibilityAfterLoad(void*scene,char*error,uint32_t cap){',1)[1]
        self.assertTrue(boundary.startswith('\n if(!wsMemoryLoad.data){'))
        self.assertIn('else if(v.marked&&!WorldSettingsValidateFactionActivityWorld(v.world,error,cap))ok=0;',boundary)
        self.assertLess(boundary.index('wsMemorySameFile'),boundary.index('WorldSettingsValidateFactionActivityWorld'))
        self.assertNotIn('WorldSettingsExpectFactionActivity',memory)
        from anno1503_overhaul.world_options import authored
        for name in ('start_visibility_runtime.inc','start_visibility_chart.inc','start_visibility_frame.inc','start_visibility_performance.inc'):
            self.assertEqual(staged[f.PRIVATE+name],authored(name))


@unittest.skipUnless(os.name=='nt','Isolated native Windows fixture requires Windows.')
class FactionBinderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=ROOT/'.local/toolchain/ziglang/zig.exe'
        if not compiler.is_file():raise unittest.SkipTest('Reviewed local native fixture compiler is unavailable.')
        cls.temp=tempfile.TemporaryDirectory(prefix='anno-faction-fixture-');folder=Path(cls.temp.name)
        source=folder/'fixture.c';source.write_text(SOURCE+lifecycle_source()+load_boundary_source(),encoding='utf-8');output=folder/'fixture.dll'
        env=dict(os.environ,ZIG_GLOBAL_CACHE_DIR=str(folder/'global'),ZIG_LOCAL_CACHE_DIR=str(folder/'local'))
        compiled=subprocess.run([str(compiler),'cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-shared','-I',str(ROOT/'src/anno1503_overhaul/native/world_options'),str(source),'-o',str(output)],env=env,capture_output=True,text=True)
        if compiled.returncode:raise AssertionError(compiled.stdout+compiled.stderr)
        cls.lib=C.CDLL(str(output))
        cls.lib.fixture_setup.argtypes=[C.c_uint32,C.c_int]
        cls.lib.fixture_bind.argtypes=[C.c_uint32,C.c_int,C.c_int,C.c_int]
        cls.lib.fixture_flags.argtypes=[C.c_int];cls.lib.fixture_flags.restype=C.c_uint32
        cls.lib.fixture_saved_flags.argtypes=[C.c_int,C.c_uint32]
        cls.lib.fixture_decode.argtypes=[C.c_uint32,C.c_uint32]
    @classmethod
    def tearDownClass(cls):
        cls.lib.fixture_close();import _ctypes;_ctypes.FreeLibrary(cls.lib._handle);cls.temp.cleanup()
    def test_fresh_choices_atomic_native_low_bits_and_off_switches(self):
        for classic,factions,frequency,strength,merchant in itertools.product(range(2),range(4),range(3),range(3),range(3)):
            self.assertEqual(self.lib.fixture_setup(factions,classic),1)
            self.assertEqual(self.lib.fixture_bind(factions,frequency,strength,merchant),1)
            self.assertEqual(self.lib.fixture_flags(0),f.PIRATE_TAG|(frequency<<8)|(strength<<10)|0xa5 if factions&1 else 0)
            self.assertEqual(self.lib.fixture_flags(1),f.MERCHANT_TAG|(merchant<<8)|0xa6 if factions&2 else 0)
            self.assertEqual(self.lib.fixture_validate(),1)
            self.assertEqual(self.lib.fixture_bind_again(),0)
    def test_identity_flags_and_protected_second_target_fail_before_any_write(self):
        for fault in range(1,13):
            self.assertEqual(self.lib.fixture_setup(3,0),1);self.lib.fixture_fault(fault)
            before=[self.lib.fixture_flags(i) for i in range(2)]
            self.assertEqual(self.lib.fixture_bind(3,2,2,2),0,fault)
            self.assertEqual([self.lib.fixture_flags(i) for i in range(2)],before,fault)
            self.assertEqual(self.lib.fixture_bind_again(),0)
    def test_saved_policy_validation_is_read_only_legacy_normal_and_corrupt_refusal(self):
        for classic in range(2):
            self.assertEqual(self.lib.fixture_setup(3,classic),1)
            for pirate,merchant,want in [(0xa5,0xa6,1),(f.PIRATE_TAG|0x900|0xa5,f.MERCHANT_TAG|0x200|0xa6,1),
                (f.PIRATE_TAG|0x300,0,0),(f.PIRATE_TAG|0xc00,0,0),(f.PIRATE_TAG|0x1000,0,0),
                (0,f.MERCHANT_TAG|0x300,0),(0,f.MERCHANT_TAG|0x400,0),(f.MERCHANT_TAG,0,0),(0,f.PIRATE_TAG,0)]:
                self.lib.fixture_saved_flags(0,pirate);self.lib.fixture_saved_flags(1,merchant)
                self.assertEqual(self.lib.fixture_validate(),want)
                self.assertEqual([self.lib.fixture_flags(i) for i in range(2)],[pirate,merchant])
            self.lib.fixture_cancel();self.assertEqual(self.lib.fixture_bind_again(),0)
    def test_decode_rejects_all_reserved_modes_and_bits(self):
        for typ,tag,limit in [(15,f.PIRATE_TAG,0x1000),(16,f.MERCHANT_TAG,0x400)]:
            for low in range(256):self.assertEqual(self.lib.fixture_decode(low,typ),4)
            for frequency,strength in itertools.product(range(4),range(4) if typ==15 else range(1)):
                flags=tag|(frequency<<8)|(strength<<10)
                expected=frequency+3*(strength if typ==15 else 1) if frequency<3 and strength<3 else -1
                self.assertEqual(self.lib.fixture_decode(flags,typ),expected)
            for bit in range(limit.bit_length()-1,16):self.assertEqual(self.lib.fixture_decode(tag|(1<<bit),typ),-1)

    def test_actual_staged_expect_begin_afterprofiles_end_and_cancel_then_legacy_load(self):
        for classic in range(2):
            self.assertEqual(self.lib.fixture_setup(3,classic),1)
            self.assertEqual(self.lib.fixture_lifecycle(0),0)
            self.assertEqual(self.lib.fixture_flags(0),f.PIRATE_TAG|0x200|0xa5)
            self.assertEqual(self.lib.fixture_flags(1),f.MERCHANT_TAG|0xa6)
            self.assertEqual(self.lib.fixture_setup(3,classic),1)
            self.assertEqual(self.lib.fixture_lifecycle(1),0)
            self.assertEqual(self.lib.fixture_setup(3,classic),1)
            self.assertEqual(self.lib.fixture_validate(),1)
            self.assertEqual([self.lib.fixture_flags(i) for i in range(2)],[0xa5,0xa6])

    def test_original_scene_and_native_save_bypass_custom_faction_certificate(self):
        for classic,fault in itertools.product(range(2),(1,5,6,9)):
            with self.subTest(classic=classic,fault=fault):
                self.assertEqual(self.lib.fixture_setup(3,classic),1);self.lib.fixture_fault(fault)
                before=[self.lib.fixture_flags(i)for i in range(2)]
                self.assertEqual(self.lib.fixture_validate(),0)
                self.lib.fixture_stage_old_choices()
                # BeforeLoad stages neither an original scene nor an unmarked
                # full save: both take the same native passthrough boundary.
                for unused in ('new Original scene','unmarked native saved world'):
                    self.assertEqual(self.lib.fixture_after_load(0,0,0),1)
                    self.assertEqual([self.lib.fixture_load_count(i)for i in range(6)],[0,1,0,0,0,0])
                    self.assertEqual(self.lib.fixture_old_choices_pending(),1)
                self.assertEqual(self.lib.fixture_original_after_cancel(),0)
                self.assertEqual(self.lib.fixture_old_choices_pending(),0)
                self.assertEqual([self.lib.fixture_flags(i)for i in range(2)],before)

    def test_marked_checkpoint_retains_identity_tag_and_atomic_publication_checks(self):
        for classic in range(2):
            self.assertEqual(self.lib.fixture_setup(3,classic),1)
            self.assertEqual(self.lib.fixture_bind(3,2,2,0),1)
            before=[self.lib.fixture_flags(i)for i in range(2)]
            self.assertEqual(self.lib.fixture_after_load(1,1,0),1)
            self.assertEqual([self.lib.fixture_load_count(i)for i in range(6)],[1,0,1,1,1,1])
            self.assertEqual(self.lib.fixture_after_load(1,1,1),0)
            self.assertEqual([self.lib.fixture_load_count(i)for i in range(6)],[1,0,0,0,0,1])
            for fault in (5,6,9):
                self.assertEqual(self.lib.fixture_setup(3,classic),1)
                self.assertEqual(self.lib.fixture_bind(3,2,2,0),1)
                self.lib.fixture_fault(fault)
                self.assertEqual(self.lib.fixture_after_load(1,1,0),0)
                self.assertEqual([self.lib.fixture_load_count(i)for i in range(6)],[1,0,0,0,0,1])
                self.assertEqual([self.lib.fixture_flags(i)for i in range(2)],before)
            self.assertEqual(self.lib.fixture_setup(3,classic),1)
            self.lib.fixture_saved_flags(0,f.PIRATE_TAG|0x300)
            self.assertEqual(self.lib.fixture_after_load(1,1,0),0)
            self.assertEqual([self.lib.fixture_load_count(i)for i in range(6)],[1,0,0,0,0,1])


if __name__=='__main__':unittest.main()
