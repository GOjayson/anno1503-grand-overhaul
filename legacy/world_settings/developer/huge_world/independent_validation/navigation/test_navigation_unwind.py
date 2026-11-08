"""Use Windows RtlVirtualUnwind on a private memory image; load/run no DLL."""
from pathlib import Path
import ctypes,hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/_tools'));sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent/'grid'))
import pefile
from navigation_patch import transform_welt_navigation,PATCH_MANIFEST
from world_grid_patch import transform_welt_grid
k=ctypes.WinDLL('kernel32',use_last_error=True);nt=ctypes.WinDLL('ntdll')
k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32];k.VirtualAlloc.restype=ctypes.c_void_p
k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32];k.VirtualFree.restype=ctypes.c_int
nt.RtlVirtualUnwind.argtypes=[ctypes.c_uint32,ctypes.c_uint64,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];nt.RtlVirtualUnwind.restype=ctypes.c_void_p
inputs=[('original',(ROOT/'AnnoWelt.dll').read_bytes()),('dev7',(ROOT/'WorldSettings_Work/anno1503_food_world_dev7/native/AnnoWelt.world.dll').read_bytes())]
inputs+=[(name+'_grid',transform_welt_grid(blob)[0])for name,blob in inputs[:]]
reports=[]
for name,blob in inputs:
 out=transform_welt_navigation(blob);p=pefile.PE(data=out);im=p.get_memory_mapped_image()
 entries=[e for e in p.DIRECTORY_ENTRY_EXCEPTION if 0x67fe0<=e.struct.BeginAddress<0x68060]
 assert[(e.struct.BeginAddress,e.struct.EndAddress)for e in entries]==[(0x67fe0,0x68024),(0x68024,0x68059),(0x68059,0x6805f)]
 allocation=k.VirtualAlloc(None,len(im),0x3000,0x40)
 if not allocation:raise ctypes.WinError(ctypes.get_last_error())
 try:
  ctypes.memmove(allocation,bytes(im),len(im))
  stack=ctypes.create_string_buffer(4096);sp=((ctypes.addressof(stack)+2048)&~15)-8
  expected_rip=0x60000000;original_rdi=0x1111222233334444;original_rbx=0x5555666677778888
  tests=[(0x67fe0,sp,True,False),(0x67fe2,sp-8,False,False),(0x67fe6,sp-40,False,False),(0x68012,sp-40,False,False),(0x68024,sp-40,False,False),(0x68029,sp-40,False,True),(0x6803b,sp-40,False,True),(0x6804f,sp-40,False,True),(0x68054,sp-40,False,True),(0x68059,sp-40,False,False),(0x6805d,sp-8,False,False),(0x6805e,sp,True,False)]
  cases=[]
  for pc,rsp,rdi_restored,rbx_saved in tests:
   ctypes.memset(ctypes.addressof(stack),0,4096)
   ctypes.c_uint64.from_address(sp).value=expected_rip
   ctypes.c_uint64.from_address(sp-8).value=original_rdi
   ctypes.c_uint64.from_address(sp+8).value=original_rbx
   raw=ctypes.create_string_buffer(0x4d0+15);ctx=(ctypes.addressof(raw)+15)&~15
   def put(off,v):ctypes.c_uint64.from_address(ctx+off).value=v
   def get(off):return ctypes.c_uint64.from_address(ctx+off).value
   ctypes.c_uint32.from_address(ctx+0x30).value=0x10001f
   put(0x90,0xaaaa if rbx_saved else original_rbx);put(0x98,rsp);put(0xb0,original_rdi if rdi_restored else 0xbbbb);put(0xf8,allocation+pc)
   entry=next(e for e in entries if e.struct.BeginAddress<=pc<e.struct.EndAddress)
   entry_address=allocation+p.get_rva_from_offset(entry.struct.get_file_offset())
   handler_data=ctypes.c_void_p();establisher=ctypes.c_uint64()
   nt.RtlVirtualUnwind(0,allocation,allocation+pc,entry_address,ctx,ctypes.byref(handler_data),ctypes.byref(establisher),None)
   assert get(0xf8)==expected_rip,(name,hex(pc),'rip',hex(get(0xf8)))
   assert get(0x98)==sp+8,(name,hex(pc),'rsp',hex(get(0x98)),hex(sp+8))
   assert get(0xb0)==original_rdi,(name,hex(pc),'rdi',hex(get(0xb0)))
   assert get(0x90)==original_rbx,(name,hex(pc),'rbx',hex(get(0x90)))
   cases.append(dict(pc_rva=hex(pc),status='PASS'))
  guard_stack=ctypes.create_string_buffer(0x4000);entry_sp=((ctypes.addressof(guard_stack)+0x3000)&~15)-8;frame=entry_sp-0x1088
  offsets={0x90:0x1080,0xa0:0x1078,0xa8:0x1070,0xb0:0x1068,0xd8:0x1060,0xe0:0x1058,0xf0:0x1050}
  original_regs={off:0x1234567800000000+off for off in offsets};original_r14=0x9999888877776666
  original_xmm6=bytes.fromhex('112233445566778899aabbccddeeff00');original_xmm7=bytes.fromhex('ffeeddccbbaa99887766554433221100')
  guard_cases=[]
  for pc in [0x6ab4b,0x6ab50,0x6ab5d,0x6ac2b,0x6ac33,0x6ac3b,0x6ac40,0x6ac47,0x6ac51,0x6b476,0x6b47d,0x6b487]:
   ctypes.memset(ctypes.addressof(guard_stack),0,0x4000)
   ctypes.c_uint64.from_address(entry_sp).value=expected_rip
   for off,slot in offsets.items():ctypes.c_uint64.from_address(frame+slot).value=original_regs[off]
   ctypes.memmove(frame+0x1040,original_xmm6,16);ctypes.memmove(frame+0x1030,original_xmm7,16)
   raw=ctypes.create_string_buffer(0x4d0+15);ctx=(ctypes.addressof(raw)+15)&~15
   ctypes.c_uint32.from_address(ctx+0x30).value=0x10001f
   restored_gprs=pc in[0x6ac51,0x6b487]
   for off in offsets:put(off,original_regs[off]if restored_gprs else 0xaaaa)
   put(0xe8,original_r14)
   rsp=(entry_sp if pc in[0x6ac51,0x6b487]else entry_sp-56 if pc in[0x6ac47,0x6b47d]else frame)
   put(0x98,rsp);put(0xf8,allocation+pc)
   # The early failure stub restores these two registers in sequence; the
   # native epilog starts only after both have been restored.
   xmm6_ready=pc in[0x6ac33,0x6ac3b,0x6ac40,0x6ac47,0x6ac51,0x6b476,0x6b47d,0x6b487]
   xmm7_ready=pc in[0x6ac3b,0x6ac40,0x6ac47,0x6ac51,0x6b476,0x6b47d,0x6b487]
   ctypes.memmove(ctx+0x200,original_xmm6 if xmm6_ready else b'\xaa'*16,16)
   ctypes.memmove(ctx+0x210,original_xmm7 if xmm7_ready else b'\xbb'*16,16)
   entry=next(e for e in p.DIRECTORY_ENTRY_EXCEPTION if e.struct.BeginAddress<=pc<e.struct.EndAddress)
   entry_address=allocation+p.get_rva_from_offset(entry.struct.get_file_offset())
   handler_data=ctypes.c_void_p();establisher=ctypes.c_uint64()
   nt.RtlVirtualUnwind(0,allocation,allocation+pc,entry_address,ctx,ctypes.byref(handler_data),ctypes.byref(establisher),None)
   assert get(0xf8)==expected_rip,(name,hex(pc),'guard_rip',hex(get(0xf8)))
   assert get(0x98)==entry_sp+8,(name,hex(pc),'guard_rsp')
   for off,val in original_regs.items():assert get(off)==val,(name,hex(pc),'gpr',hex(off),hex(get(off)),hex(val))
   assert get(0xe8)==original_r14,(name,hex(pc),'r14')
   assert ctypes.string_at(ctx+0x200,16)==original_xmm6,(name,hex(pc),'xmm6')
   assert ctypes.string_at(ctx+0x210,16)==original_xmm7,(name,hex(pc),'xmm7')
   guard_cases.append(dict(pc_rva=hex(pc),status='PASS'))
  reports.append(dict(input=name,input_sha256=hashlib.sha256(blob).hexdigest(),output_sha256=hashlib.sha256(out).hexdigest(),active_exception_directory_rva=hex(p.OPTIONAL_HEADER.DATA_DIRECTORY[3].VirtualAddress),ranges=[[hex(e.struct.BeginAddress),hex(e.struct.EndAddress)]for e in entries],native_windows_virtual_unwind=cases,native_windows_backtrack_failure_unwind=guard_cases,status='PASS'))
 finally:assert k.VirtualFree(allocation,0,0x8000)
report=dict(status='PASS',test='Windows RtlVirtualUnwind; privately allocated image and synthetic stack/context; no DLL loaded or game started',profiles=reports,limitation='Synthetic frame unwind at selected instruction boundaries, not actual asynchronous faults or gameplay.')
(HERE/'navigation_unwind_results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status='PASS',profiles=len(reports),native_windows_unwind_cases=sum(len(r['native_windows_virtual_unwind'])+len(r['native_windows_backtrack_failure_unwind'])for r in reports))))
