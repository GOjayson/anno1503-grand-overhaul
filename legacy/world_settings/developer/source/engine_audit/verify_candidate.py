"""Automated pure DLL settings checks and copied Frame PE integrity checks.
This does not launch Anno, render the modal, generate a world, or validate any
complete generated scene. Native Windows loader is used for the standalone DLL.
"""
import ctypes as c,sys,struct,hashlib,json,itertools
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'_tools'))
import pefile
from patch_frame_copy import transform_frame,pe_info,checksum
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
class Settings(c.Structure):_fields_=[('size',c.c_uint32),('difficulty',c.c_int32),('islandSize',c.c_int32),('islandCount',c.c_int32),('spacing',c.c_int32),('aiCount',c.c_int32),('cultures',c.c_uint32)]
dll=c.CDLL(str(HERE/'runtime/WorldSettings.dll'));dll.WorldSettingsValidateSettings.argtypes=[c.POINTER(Settings),c.c_void_p,c.c_uint32];dll.WorldSettingsValidateSettings.restype=c.c_int
assert dll.WorldSettingsSettingsSize()==c.sizeof(Settings)==28
s=Settings(28,1,3,24,16,0,255);err=c.create_string_buffer(512);n=0
for difficulty,size,bits in itertools.product(range(3),range(4),range(256)):
 s.difficulty=difficulty;s.islandSize=size;s.cultures=bits
 assert dll.WorldSettingsValidateSettings(c.byref(s),err,len(err))==1
 n+=1
s=Settings(28,1,3,24,16,0,255)
invalid=[('size',0),('difficulty',-1),('difficulty',3),('islandSize',-1),('islandSize',4),('islandCount',0),('islandCount',129),('spacing',-1),('spacing',257),('aiCount',1),('aiCount',7),('cultures',256)]
for name,value in invalid:
 old=getattr(s,name);setattr(s,name,value)
 assert dll.WorldSettingsValidateSettings(c.byref(s),err,len(err))==0 and err.value,(name,value)
 setattr(s,name,old)
assert dll.WorldSettingsValidateSettings(None,err,len(err))==0
small=c.create_string_buffer(2);s.aiCount=1;assert dll.WorldSettingsValidateSettings(c.byref(s),small,2)==0 and small.raw[-1]==0
original=(ROOT/'AnnoFrame.dll').read_bytes();patched=(HERE/'AnnoFrame.candidate.dll').read_bytes();reproduced,info=transform_frame(original);assert patched==reproduced
pe,opt,tab,sections,off=pe_info(original);permitted=set()
for at,size in [(pe+6,2),(opt+4,4),(opt+56,4),(opt+64,4),(opt+112+24,8),(tab+len(sections)*40,40),(off(0x44bb0),9)]:permitted.update(range(at,at+size))
assert all(i in permitted for i,(a,b) in enumerate(zip(original,patched)) if a!=b)
p=pefile.PE(data=patched);assert p.FILE_HEADER.Machine==0x8664 and p.OPTIONAL_HEADER.Magic==0x20b
assert p.OPTIONAL_HEADER.CheckSum==p.generate_checksum()==checksum(patched)
assert p.sections[-1].Name==b'.wset\0\0\0' and p.sections[-1].Characteristics==0x60000020
old=pefile.PE(data=original);new_entries=[(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in p.DIRECTORY_ENTRY_EXCEPTION];old_entries=[(e.struct.BeginAddress,e.struct.EndAddress,e.struct.UnwindData) for e in old.DIRECTORY_ENTRY_EXCEPTION]
assert new_entries==sorted(new_entries) and len(new_entries)==len(old_entries)+2
assert set(old_entries)<=set(new_entries)
assert all(a[1]<=b[0] for a,b in zip(new_entries,new_entries[1:]))
for o in old.sections:
 if o.Name==b'.fmarket':assert original[o.PointerToRawData:o.PointerToRawData+o.SizeOfRawData]==patched[o.PointerToRawData:o.PointerToRawData+o.SizeOfRawData]
for i in [0,1,2,4,5,6,7,8,9,10,11,12,13,14,15]:assert old.OPTIONAL_HEADER.DATA_DIRECTORY[i].VirtualAddress==p.OPTIONAL_HEADER.DATA_DIRECTORY[i].VirtualAddress and old.OPTIONAL_HEADER.DATA_DIRECTORY[i].Size==p.OPTIONAL_HEADER.DATA_DIRECTORY[i].Size
print(json.dumps({'scope':'Standalone DLL native loading/settings validation and copied Frame PE metadata; no Anno UI/game/world run','valid_setting_combinations':n,'invalid_settings_rejected':len(invalid)+1,'truncated_error_terminated':True,'frame_extra_runtime_functions':2,'existing_food_section_byte_identical':True,'only_expected_original_bytes_changed':True,'pe_checksum_valid':True,'copied_frame_sha256':hashlib.sha256(patched).hexdigest(),'dll_sha256':hashlib.sha256((HERE/'runtime/WorldSettings.dll').read_bytes()).hexdigest()},indent=2))


