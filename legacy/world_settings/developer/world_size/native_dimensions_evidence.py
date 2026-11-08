"""Read exact original HE files and emulate bounded native getter/index blocks.

This starts no game and changes no game/copy file. Synthetic Unicorn objects
establish dimension transport and lookup addresses, not full engine behavior.
2048 is rejected because the actual native lookup crosses an inline array.
"""
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'WorldSettings_Work/_tools'))
import pefile
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_RAX,UC_X86_REG_RSP
EXPECTED={'AnnoScene.dll':'f7d0685cf6156ff25c518f2f558863b351d7738280467e48dd585a1fefa9537a',
          'AnnoWelt.dll':'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'}
def sha(data):return hashlib.sha256(data).hexdigest()
def scene_head(path):
    data=path.read_bytes()
    assert data[:12].rstrip(b'\0') in [b'ANNO',b'ANNOADDON1']
    assert struct.unpack_from('<I',data,12)[0]==len(data)-16
    assert data[16:28].rstrip(b'\0')==b'SCENE'
    assert struct.unpack_from('<I',data,28)[0]==len(data)-32
    found=[];at=32
    while at<len(data):
        assert len(data)-at>=16
        tag=data[at:at+12].rstrip(b'\0');n=struct.unpack_from('<I',data,at+12)[0]
        assert n<=len(data)-at-16
        if tag==b'HEAD':
            assert n==32
            found.append(struct.unpack_from('<8I',data,at+16))
        at+=16+n
    assert len(found)==1
    return dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(data),head_dwords=list(found[0]),width=found[0][0],height=found[0][1])
def main():
    modules={};fingerprints={};asm=[];cs=Cs(CS_ARCH_X86,CS_MODE_64)
    for name,digest in EXPECTED.items():
        blob=(ROOT/name).read_bytes();assert sha(blob)==digest
        pe=pefile.PE(data=blob);assert pe.FILE_HEADER.Machine==0x8664 and pe.OPTIONAL_HEADER.Magic==0x20b
        modules[name]=pe;fingerprints[name]=dict(sha256=digest,machine='AMD64',optional_header='PE32+')
    w=modules['AnnoWelt.dll'];image=w.get_memory_mapped_image();base=w.OPTIONAL_HEADER.ImageBase
    s=modules['AnnoScene.dll'].get_memory_mapped_image()
    assert s[0xe4cb:0xe4dd].hex()=='448b4424448b542440488bcfff90d0000000'
    assert image[0xc7c90:0xc7c97].hex()=='8b81d8010000c3'
    assert image[0xc7ca0:0xc7ca7].hex()=='8b81dc010000c3'
    assert image[0xd2053:0xd206a].hex()=='488d8f40020000baff00000041b800640000e880380100'
    for vt in [0xff1d8,0xff650]:
        for slot,method in [(0xb0,0xc7c90),(0xb8,0xc7ca0)]:
            assert struct.unpack_from('<Q',image,vt+slot)[0]-base==method
    spans={'AnnoScene.dll':[(0xe400,0xe4f0),(0x40f0,0x4167),(0x7650,0x76ac)],
           'AnnoWelt.dll':[(0xc8760,0xc878d),(0xc7c90,0xc7ca7),(0xd1f7b,0xd1f9b),(0xd2053,0xd206a),
                           (0xc8b20,0xc8b7a),(0xc8be0,0xc8c3e),(0xc8cc0,0xc8d22),(0xc8db0,0xc8df8),
                           (0xce940,0xceafc),(0xbfdf0,0xc000d),(0xdbef5,0xdc010)]}
    for name,ranges in spans.items():
        mapped=modules[name].get_memory_mapped_image()
        for a,b in ranges:
            asm.append(f'\n; {name} RVA {a:x}..{b:x}\n'+'\n'.join(f'{i.address:08x} {i.bytes.hex():24} {i.mnemonic:7} {i.op_str}' for i in cs.disasm(mapped[a:b],a)))
    results=[];getters=[]
    for mapped_base in [0x180000000,0x280000000]:
        for size in [256,512,1024,2048]:
            u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(mapped_base,(len(image)+4095)&~4095);u.mem_write(mapped_base,image)
            obj=0x40000000;stack=0x50000000;stop=0x60000000
            u.mem_map(obj,0x20000);u.mem_map(stack,0x10000);u.mem_map(stop,0x1000)
            u.mem_write(obj+0x1d8,struct.pack('<II',size,size))
            for rva,label in [(0xc7c90,'width'),(0xc7ca0,'height')]:
                rsp=stack+0xf008;u.mem_write(rsp,struct.pack('<Q',stop));u.reg_write(UC_X86_REG_RSP,rsp);u.reg_write(UC_X86_REG_RCX,obj)
                u.emu_start(mapped_base+rva,stop,count=20);value=u.reg_read(UC_X86_REG_RAX);assert value==size
                getters.append(dict(base=hex(mapped_base),size=size,dimension=label,value=value,rva=hex(rva)))
            trace=[]
            def on_code(uc,address,length,_):
                if address==mapped_base+0xc8b5d:
                    trace.append(uc.reg_read(UC_X86_REG_RAX)+uc.reg_read(UC_X86_REG_RCX)+0x240-obj);uc.emu_stop()
            u.hook_add(UC_HOOK_CODE,on_code)
            for x,y in [(0,0),(size-1,0),(0,size-1),(size-1,size-1),(size//2,size//2)]:
                trace.clear();u.reg_write(UC_X86_REG_RSP,stack+0xf008);u.reg_write(UC_X86_REG_RCX,obj);u.reg_write(UC_X86_REG_RDX,x);u.reg_write(UC_X86_REG_R8,y)
                u.emu_start(mapped_base+0xc8b20,stop,count=100)
                offset=0x240+(y//8)*(size//8)+(x//8);assert trace==[offset]
                results.append(dict(base=hex(mapped_base),world_size=size,x=x,y=y,native_lookup_offset=hex(offset),inside_fixed_lookup=0x240<=offset<0x6640,inside_native_world_object=offset<0x7068))
    files=sorted(set((ROOT/'Scenes').rglob('*.sze'))|set((ROOT/'Languages').rglob('*.sze')))
    stock=[scene_head(p) for p in files];counts={}
    for row in stock:
        key=f"{row['width']}x{row['height']}";counts[key]=counts.get(key,0)+1
    assert len(stock)==55 and counts=={'256x256':3,'512x512':14,'608x608':1,'768x768':1,'800x800':10,'1024x1024':26}
    assert all(r['inside_fixed_lookup'] for r in results if r['world_size']<=1024)
    assert any(not r['inside_native_world_object'] for r in results if r['world_size']==2048)
    assembly='\n'.join(asm)+'\n';(HERE/'native_dimensions.asm').write_text(assembly,encoding='utf-8')
    report=dict(scope=__doc__,fingerprints=fingerprints,stock_scene_count=len(stock),stock_dimension_counts=counts,stock_scenes=stock,
                native_world_width_offset='0x1d8',native_world_height_offset='0x1dc',native_dimension_vtable_slots=['0xb0','0xb8'],
                inline_island_lookup_start='0x240',inline_island_lookup_bytes=0x6400,island_pointer_table_start='0x6640',native_world_server_allocation_bytes=0x7068,
                native_lookup_formula='world+0x240 + (y//8)*(width//8) + x//8',native_getter_cases=getters,native_lookup_cases=results,
                supported_generated_sizes=[256,512,1024],blocked_size=2048,blocked_reason='65536 lookup cells exceed the fixed 25600-byte inline table and overlap live object members and object allocation.',
                snippets_sha256=sha(assembly.encode()),game_executed=False,game_or_copy_mutated=False,
                unverified=['Complete navigation/pathfinding, rendering, minimap and save/reload at generated256/512 require live tests.','No claim of a universal engine maximum;2048 is specifically incompatible with this native inline layout.'])
    (HERE/'native_dimensions_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(stock_scenes=len(stock),dimensions=counts,native_getter_cases=len(getters),native_lookup_cases=len(results),blocked2048=True,game_executed=False)))
if __name__=='__main__':main()
