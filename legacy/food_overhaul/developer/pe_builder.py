"""Build reviewed, fingerprinted PE additions; no Windows tooling is required."""
from pathlib import Path
import struct
import subprocess
import tempfile


def align(value, boundary):
    return (value + boundary - 1) & -boundary


def pe_info(data):
    pe = struct.unpack_from('<I', data, 60)[0]
    assert data[pe:pe+4] == b'PE\0\0'
    assert struct.unpack_from('<H', data, pe+4)[0] == 0x8664
    opt = pe+24
    table = opt+struct.unpack_from('<H', data, pe+20)[0]
    count = struct.unpack_from('<H', data, pe+6)[0]
    sections = [struct.unpack_from('<8sIIIIIIHHI', data, table+i*40) for i in range(count)]
    def offset(rva):
        return next(raw+rva-va for name,vs,va,rs,raw,*rest in sections if va <= rva < va+rs)
    return pe,opt,table,sections,offset


def checksum(data):
    pe = struct.unpack_from('<I',data,60)[0]
    at = pe+24+64
    total=0
    for i in range(0,len(data),2):
        word=int.from_bytes(data[i:i+2],'little') if not at<=i<at+4 else 0
        total+=word
        total=(total&65535)+(total>>16)
    return ((total&65535)+(total>>16))+len(data)


def assemble(source, rva, native_symbols):
    source=Path(source).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        obj=Path(tmp)/'code.o';elf=Path(tmp)/'code.elf';raw=Path(tmp)/'code.bin'
        subprocess.run(['as','--64','-I',str(source.parent),str(source),'-o',str(obj)],check=True,capture_output=True)
        args=['ld','-Ttext='+hex(rva),'-e','0','--build-id=none','-o',str(elf),str(obj)]
        for name,value in native_symbols.items():args+=['--defsym',name+'='+hex(value)]
        subprocess.run(args,check=True,capture_output=True)
        subprocess.run(['objcopy','-O','binary','-j','.text',str(elf),str(raw)],check=True,capture_output=True)
        names={}
        for line in subprocess.check_output(['nm','-n',str(elf)],text=True).splitlines():
            parts=line.split()
            if len(parts)==3:names[parts[2]]=int(parts[0],16)
        return raw.read_bytes(),names


def extend_pe(original, source, native_symbols=None, edits=None, new_pointers=None):
    pe,opt,table,sections,offset=pe_info(original)
    image_base=struct.unpack_from('<Q',original,opt+24)[0]
    va_align,raw_align=struct.unpack_from('<II',original,opt+32)
    new_rva=align(max(s[2]+max(s[1],s[3]) for s in sections),va_align)
    raw=align(len(original),raw_align)
    assert table+(len(sections)+1)*40 <= min(s[4] for s in sections)
    assert original[table+len(sections)*40:table+(len(sections)+1)*40] == bytes(40)
    code,names=assemble(source,new_rva,native_symbols or {})
    payload=bytearray(code)
    function_entries=[]
    # Every nonleaf assembly helper uses the exact shared prolog in common.inc.
    for name,start in sorted(names.items(),key=lambda pair:pair[1]):
        if name+'_prolog_end' not in names:continue
        assert names[name+'_prolog_end']-start==18
        payload+=bytes(align(len(payload),4)-len(payload))
        unwind_rva=new_rva+len(payload)
        payload+=bytes([1,18,8,0,18,0xf2,11,0xf0,9,0xe0,7,0xd0,5,0xc0,3,0x70,2,0x60,1,0x30])
        function_entries.append((start,names[name+'_end'],unwind_rva))
    exception=None
    if function_entries:
        old_rva,old_size=struct.unpack_from('<II',original,opt+112+3*8)
        old=original[offset(old_rva):offset(old_rva)+old_size]
        assert len(old)%12==0
        entries=[struct.unpack_from('<III',old,i) for i in range(0,len(old),12)]
        entries=sorted(entries+function_entries)
        assert all(a[1]<=b[0] for a,b in zip(entries,entries[1:]))
        payload+=bytes(align(len(payload),4)-len(payload))
        exception=(new_rva+len(payload),len(entries)*12)
        payload+=b''.join(struct.pack('<III',*entry) for entry in entries)
    reloc=None
    pointers=[]
    for at,label in (new_pointers or []):
        ptr_rva=next(va+at-file_at for n,vs,va,rs,file_at,*rest in sections if file_at<=at<file_at+rs)
        pointers.append((at,ptr_rva,image_base+names[label]))
    if pointers:
        old_rva,old_size=struct.unpack_from('<II',original,opt+112+5*8)
        old=original[offset(old_rva):offset(old_rva)+old_size]
        existing=[];position=0
        while position<len(old):
            page,size=struct.unpack_from('<II',old,position)
            assert size>=8 and size%4==0
            for at in range(position+8,position+size,2):
                entry=struct.unpack_from('<H',old,at)[0]
                if entry>>12:existing.append(page+(entry&4095))
            position+=size
        extra=sorted({rva for _,rva,_ in pointers}-set(existing))
        blocks=bytearray(old)
        for page in sorted({rva&~4095 for rva in extra}):
            values=[0xa000|(rva&4095) for rva in extra if rva&~4095==page]
            if len(values)%2:values.append(0)
            blocks+=struct.pack('<II',page,8+len(values)*2)+struct.pack('<'+'H'*len(values),*values)
        payload+=bytes(align(len(payload),4)-len(payload))
        reloc=(new_rva+len(payload),len(blocks));payload+=blocks
    result=bytearray(original)
    for at,before,after in (edits(names) if edits else []):
        assert len(before)==len(after) and result[at:at+len(before)]==before,(hex(at),before.hex())
        result[at:at+len(after)]=after
    for at,ptr_rva,value in pointers:struct.pack_into('<Q',result,at,value)
    struct.pack_into('<H',result,pe+6,len(sections)+1)
    struct.pack_into('<I',result,opt+4,struct.unpack_from('<I',original,opt+4)[0]+align(len(payload),raw_align))
    struct.pack_into('<I',result,opt+56,align(new_rva+len(payload),va_align))
    header=struct.pack('<8sIIIIIIHHI',b'.fmarket',len(payload),new_rva,align(len(payload),raw_align),raw,0,0,0,0,0x60000020)
    result[table+len(sections)*40:table+(len(sections)+1)*40]=header
    if exception:struct.pack_into('<II',result,opt+112+3*8,*exception)
    if reloc:struct.pack_into('<II',result,opt+112+5*8,*reloc)
    result+=bytes(raw-len(result))+payload+bytes(align(len(payload),raw_align)-len(payload))
    struct.pack_into('<I',result,opt+64,checksum(result))
    return bytes(result),names,{'rva':new_rva,'raw':raw,'size':len(payload),'new_functions':function_entries}
