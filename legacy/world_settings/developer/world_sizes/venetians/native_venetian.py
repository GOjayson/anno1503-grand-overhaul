"""Execute current History x64 alias selection and native coordinate additions.

The entire native CEB00 named-profile selector runs, with explicit file, text
comparison and PlayerLoad boundaries. Separately, unchanged PlayerLoad city
anchor instructions and production-entry coordinate instructions run against
the real town anchors at several destination rectangles. Allocation, city and
building construction remain game-run requirements.
"""
from pathlib import Path
import hashlib,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[2]
GAME=next(p for p in HERE.parents if (p/'Anno1503.exe').is_file() and not (p/'.anno1503-worldsettings-test-copy.json').is_file())
WORK=GAME/'WorldSettings_Work'
sys.path[:0]=[str(HERE),str(PACKAGE/'support'),str(WORK/'_tools'),str(WORK/'engine_audit')]
from audit import Module
import package_world_assets as a
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *


def sha(data):return hashlib.sha256(data).hexdigest()


def relocated(m,base):
    image=bytearray(m.image)
    for block in m.pe.DIRECTORY_ENTRY_BASERELOC:
        for e in block.entries:
            if e.type==10:struct.pack_into('<Q',image,e.rva,struct.unpack_from('<Q',image,e.rva)[0]+base-m.base)
            else:assert e.type==0
    return bytes(image)


def main():
    w=Module(str(GAME/'AnnoWelt.dll'));g=Module(str(GAME/'AnnoGame.dll'))
    assert sha(w.data)=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9'
    assert sha(g.data)=='e6f01d19e8e16e6716c0a6c7d3ba00273c9df493e051b8ba62865ee4b53dfdea'
    assert all(m.pe.FILE_HEADER.Machine==0x8664 and m.pe.OPTIONAL_HEADER.Magic==0x20b for m in [w,g])
    data=(PACKAGE/'assets'/a.ASSET).read_bytes();info=a.inspect_venetian(data);profile=info['profile'][8:]
    stack,obj,ext=0x40000000,0x41000000,0x42000000
    world,table,game,gamevt,file,filevt,rect,count,context=[obj+x for x in [0,0x8000,0x9000,0xa000,0xb000,0xc000,0xd000,0xe000,0xf000]]
    selection=[];coordinates=[]
    for base in [0x180000000,0x280000000]:
        for variant,serialized,expected in [('stock-alias',profile,5),('wrong-alias-rejected-by-policy',profile.replace(b'VENEZIA01\0',b'VENEZIA02\0'),0)]:
            u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x160000);u.mem_write(base,relocated(w,base));gb=base+0x2000000;u.mem_map(gb,0x30000);u.mem_write(gb,relocated(g,gb));u.mem_map(stack,0x30000);u.mem_map(obj,0x11000);u.mem_map(ext,0x1000)
            def put(at,fmt,*v):u.mem_write(at,struct.pack('<'+fmt,*v))
            def get(at,fmt):return struct.unpack('<'+fmt,u.mem_read(at,struct.calcsize('<'+fmt)))[0]
            def cstring(at):
                raw=bytearray()
                for n in range(512):
                    b=bytes(u.mem_read(at+n,1))
                    if b==b'\0':return bytes(raw)
                    raw+=b
                raise AssertionError('Unterminated native text')
            put(world+0x210,'Q',table);put(table,'Q',base+0xfdbc0);put(world+0x200,'Q',game);put(game,'Q',gamevt);put(gamevt+0x98,'Q',gb+0xe3d0)
            players={}
            for ident,typ,culture,alias in [(0,11,1,b'HUMAN01\0'),(5,16,12,b'VENEZIA01\0'),(6,15,11,b'PIRAT01\0'),(31,2,1,b'DUMMYPLAYER\0')]:
                p=obj+0x1000+ident*0x100;players[ident]=p;put(p,'Q',base+0xfabe0);put(p+8,'I',ident);put(p+0x9c,'HH',typ,culture);u.mem_write(p+0x68,alias);put(table+8+ident*8,'Q',p)
            put(file,'Q',filevt);put(filevt+8,'Q',ext);put(filevt+0x10,'Q',ext+0x10)
            compare=next(w.cs.disasm(w.image[0xceec6:0xceecd],w.base+0xceec6));put(base+compare.address+compare.size+compare.disp-w.base,'Q',ext+0x20)
            pos=[0];loaded=[]
            def ret(cpu,value):
                sp=cpu.reg_read(UC_X86_REG_RSP);target=get(sp,'Q');cpu.reg_write(UC_X86_REG_RAX,value);cpu.reg_write(UC_X86_REG_RSP,sp+8);cpu.reg_write(UC_X86_REG_RIP,target)
            def hook(cpu,address,size,user):
                rcx,rdx,r8,r9=[cpu.reg_read(r)for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9]]
                if address==base+0xe58ea:assert r8<=4096;cpu.mem_write(rcx,bytes([rdx&255])*r8);ret(cpu,rcx)
                elif address==ext:
                    assert rcx==file and r8<=65536;part=serialized[pos[0]:pos[0]+r8];cpu.mem_write(rdx,part);put(r9,'I',len(part));pos[0]+=len(part);ret(cpu,int(len(part)==r8))
                elif address==ext+0x10:
                    assert rcx==file and r8==1;pos[0]+=struct.unpack('<i',struct.pack('<I',rdx&0xffffffff))[0];assert 0<=pos[0]<=len(serialized);ret(cpu,pos[0])
                elif address==ext+0x20:ret(cpu,int(cstring(rcx).lower()!=cstring(rdx).lower()))
                elif address==base+0x9bd20:
                    sp=cpu.reg_read(UC_X86_REG_RSP);n=get(sp+0x30,'I');ident=next(i for i,p in players.items()if p==rcx)
                    assert rdx==file and r8==rect and r9==context and pos[0]==0 and n==len(serialized)
                    loaded.append(dict(selected_player=ident,flags=get(sp+0x28,'I'),profile_bytes=n));put(get(sp+0x38,'Q'),'I',n);pos[0]=n;ret(cpu,1)
            u.hook_add(UC_HOOK_CODE,hook)
            sp=stack+0x20008;put(sp,'Q',ext+0x800);put(sp+0x28,'I',len(serialized));put(sp+0x30,'Q',count)
            for reg,v in [(UC_X86_REG_RSP,sp),(UC_X86_REG_RCX,world),(UC_X86_REG_RDX,file),(UC_X86_REG_R8,rect),(UC_X86_REG_R9,context)]:u.reg_write(reg,v)
            u.emu_start(base+0xceb00,ext+0x800,count=200000)
            assert len(loaded)==1 and loaded[0]['selected_player']==expected and loaded[0]['flags']==(expected==0)
            assert get(players[5]+0x9c,'H')==16 and get(players[5]+0x9e,'H')==12 and cstring(players[5]+0x68)==b'VENEZIA01'
            selection.append(dict(base=hex(base),variant=variant,venetian_identity_unchanged=True,**loaded[0]))
        # Execute actual native addition instructions; no translated Python
        # arithmetic substitutes for the engine code being checked.
        for x,y in [(8,8),(176,176),(184,288),(432,432),(936,936)]:
            u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,0x160000);u.mem_write(base,relocated(w,base));u.mem_map(stack,0x30000);u.mem_map(obj,0x11000)
            def put(at,fmt,*v):u.mem_write(at,struct.pack('<'+fmt,*v))
            put(rect,'IIII',x,y,x+80,y+80);bp=stack+0x10000;sp=stack+0x8000;put(bp+0x2d0,'Q',rect);put(bp-0x78,'HHH',0,28,33);put(context+0x400,'I',0)
            for reg,v in [(UC_X86_REG_RBP,bp),(UC_X86_REG_RSP,sp),(UC_X86_REG_R15,context),(UC_X86_REG_R12,13198)]:u.reg_write(reg,v)
            u.emu_start(base+0x9da1b,base+0x9da46,count=100)
            anchor=[u.reg_read(UC_X86_REG_R10),u.reg_read(UC_X86_REG_R8)];assert anchor==[x+28,y+33]
            building=[]
            for lx,ly in info['building_anchors']:
                put(bp+0x200,'Q',rect);put(sp+0x34,'HH',lx,ly)
                for reg,v in [(UC_X86_REG_RBP,bp),(UC_X86_REG_RSP,sp),(UC_X86_REG_RSI,18)]:u.reg_write(reg,v)
                u.emu_start(base+0xa8967,base+0xa899f,count=100)
                actual=[u.reg_read(UC_X86_REG_RDX),u.reg_read(UC_X86_REG_R8)]
                assert actual==[x+lx,y+ly] and x<=actual[0]<x+80 and y<=actual[1]<y+80
                building.append(actual)
            coordinates.append(dict(base=hex(base),destination_origin=[x,y],city_anchor=anchor,native_building_coordinate_cases=len(building),all_building_anchors_inside_selected_island=True))
    instruction_ranges={f'{start:#x}..{end:#x}':sha(w.image[start:end])for start,end in [(0xceb00,0xcf06d),(0x9da1b,0x9da46),(0xa8967,0xa899f)]}
    result=dict(scope=__doc__,passed=True,actual_game_executed=False,native_amd64_modules={'AnnoWelt.dll':sha(w.data),'AnnoGame.dll':sha(g.data)},asset_sha256=sha(data),native_instruction_range_sha256=instruction_ranges,native_owner_selection_cases=selection,native_relocation_cases=coordinates,native_building_coordinate_cases=sum(c['native_building_coordinate_cases']for c in coordinates),script_sha256=sha(Path(__file__).read_bytes()),boundaries=['File reads/seeks','Case insensitive alias compare','PlayerLoad city/building construction','Full game/save/reload not executed by this fixture'])
    (HERE/'native_results.json').write_text(json.dumps(result,indent=2)+'\n')
    (HERE/'native_relocation.asm').write_text(w.dis(0x9da1b,0x9db7c)+'\n\n'+w.dis(0xa8967,0xa89b1)+'\n')
    print(json.dumps(dict(passed=True,owner_selection_cases=len(selection),native_relocation_cases=len(coordinates),native_building_coordinate_cases=result['native_building_coordinate_cases'],actual_game_executed=False),indent=2))


if __name__=='__main__':main()
