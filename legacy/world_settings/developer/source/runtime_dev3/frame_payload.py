"""Add direct-start, post-profile and native-attempt gates to the Frame copy."""
from pathlib import Path
import hashlib
import struct
import sys
HERE=Path(__file__).resolve().parent
WORK=HERE.parent
sys.path[:0]=[str(WORK),str(WORK/'_tools'),str(WORK/'engine_audit'),
              str(WORK/'engine_resume/route_coverage'),str(WORK/'engine_resume/ai_food/experiment_runtime')]
from frame_factory_bridge import transform_full_frame
from patch_frame_copy import align,pe_info,checksum
from direct_bridge import build_direct_bridge
from postprofile_bridge import build_postprofile_code,SITE,BEFORE
from attempt_bridge import build_attempt_code,SITE as ATTEMPT_SITE,BEFORE as ATTEMPT_BEFORE

def transform_full_frame3(original):
    intermediate,metadata=transform_full_frame(original)
    pe,opt,table,sections,off=pe_info(intermediate)
    header_at=table+len(sections)*40
    if intermediate[header_at:header_at+40]!=bytes(40) or header_at+40>min(s[4] for s in sections):
        raise ValueError('No additional Frame section header available')
    sa,fa=struct.unpack_from('<II',intermediate,opt+32)
    rva=align(max(s[2]+max(s[1],s[3]) for s in sections),sa)
    raw=align(len(intermediate),fa)
    direct,names,hooks,functions=build_direct_bridge(rva)
    payload=bytearray(direct)
    payload+=bytes(align(len(payload),16)-len(payload))
    post,pn,pf=build_postprofile_code(rva+len(payload));payload+=post;functions+=pf
    hooks.append((SITE,BEFORE,b'\xe8'+struct.pack('<i',pn['postprofile']-SITE-5)+b'\x90'*(len(BEFORE)-5)))
    payload+=bytes(align(len(payload),16)-len(payload))
    attempt,an,af=build_attempt_code(rva+len(payload));payload+=attempt;functions+=af
    hooks.append((ATTEMPT_SITE,ATTEMPT_BEFORE,b'\xe8'+struct.pack('<i',an['native_attempt']-ATTEMPT_SITE-5)))
    # Resolve every added callback through complete, terminated import tables.
    # Direct-start retains its reviewed native LoadLibrary/GetProcAddress path.
    cells=[(post,pn['postprofile'],pn['postprofile_end'],pn['after_profiles_iat'],'WorldSettingsAfterProfiles'),
           (attempt,an['native_attempt'],an['native_attempt_end'],an['begin_attempt_iat'],'WorldSettingsBeginNativeWorldStart'),
           (attempt,an['native_attempt'],an['native_attempt_end'],an['end_attempt_iat'],'WorldSettingsEndNativeWorldStart')]
    payload+=bytes(align(len(payload),8)-len(payload))
    ilt=rva+len(payload);payload+=bytes((len(cells)+1)*8)
    dllname=rva+len(payload);payload+=b'AnnoWorldSettings.dll\0'
    exportnames=[]
    for _,_,_,_,name in cells:
        payload+=bytes(align(len(payload),2)-len(payload))
        exportnames.append(rva+len(payload));payload+=b'\0\0'+name.encode('ascii')+b'\0'
    values=exportnames+[0]
    struct.pack_into('<'+'Q'*len(values),payload,ilt-rva,*values)
    payload+=bytes(align(len(payload),8)-len(payload))
    iat=rva+len(payload);payload+=struct.pack('<'+'Q'*len(values),*values)
    from capstone import Cs,CS_ARCH_X86,CS_MODE_64
    md=Cs(CS_ARCH_X86,CS_MODE_64);md.detail=True
    for index,(code,begin,end,cell,name) in enumerate(cells):
        found=0
        for ins in md.disasm(code[:end-begin],begin):
            if ins.mnemonic=='call' and ins.disp_size==4 and ins.address+ins.size+ins.disp==cell:
                struct.pack_into('<i',payload,ins.address-rva+ins.disp_offset,iat+index*8-(ins.address+ins.size));found+=1
        if found!=1:raise ValueError(name+' import call not uniquely identified')
    old_import,old_size=struct.unpack_from('<II',intermediate,opt+112+8)
    descriptors=[]
    for n in range(128):
        item=intermediate[off(old_import)+n*20:off(old_import)+n*20+20]
        if len(item)!=20:raise ValueError('Truncated Frame import descriptor')
        if item==bytes(20):break
        descriptors.append(item)
    else:raise ValueError('Unbounded Frame imports')
    payload+=bytes(align(len(payload),4)-len(payload))
    imports=rva+len(payload)
    payload+=b''.join(descriptors)+struct.pack('<IIIII',ilt,0,0,dllname,iat)+bytes(20)
    pdata,pdata_size=struct.unpack_from('<II',intermediate,opt+112+3*8)
    if pdata_size%12:raise ValueError('Malformed Frame unwind table')
    entries=[struct.unpack_from('<III',intermediate,off(pdata)+i) for i in range(0,pdata_size,12)]
    original_entries=set(entries)
    for begin,end,unwind in functions:
        if unwind[0]>>3==4:
            count=unwind[2];at=align(4+count*2,4)
            if struct.unpack_from('<III',unwind,at) not in original_entries:raise ValueError('Chained Frame parent is absent')
        payload+=bytes(align(len(payload),4)-len(payload));unwind_rva=rva+len(payload);payload+=unwind
        entries.append((begin,end,unwind_rva))
    entries.sort()
    if any(a[1]>b[0] for a,b in zip(entries,entries[1:])):raise ValueError('Overlapping Frame unwind functions')
    payload+=bytes(align(len(payload),4)-len(payload));new_pdata=rva+len(payload)
    payload+=b''.join(struct.pack('<III',*entry) for entry in entries)
    result=bytearray(intermediate)
    for at,before,after in hooks:
        pos=off(at)
        if result[pos:pos+len(before)]!=before:raise ValueError('Frame hook preimage differs')
        result[pos:pos+len(before)]=after
    struct.pack_into('<H',result,pe+6,len(sections)+1)
    struct.pack_into('<I',result,opt+4,struct.unpack_from('<I',result,opt+4)[0]+align(len(payload),fa))
    struct.pack_into('<I',result,opt+56,align(rva+len(payload),sa))
    struct.pack_into('<II',result,opt+112+8,imports,(len(descriptors)+2)*20)
    struct.pack_into('<II',result,opt+112+3*8,new_pdata,len(entries)*12)
    result[header_at:header_at+40]=struct.pack('<8sIIIIIIHHI',b'.wsextra',len(payload),rva,align(len(payload),fa),raw,0,0,0,0,0x60000020)
    result+=bytes(raw-len(result))+payload+bytes(align(len(payload),fa)-len(payload))
    struct.pack_into('<I',result,opt+64,checksum(result))
    metadata['additional_hooks']=[dict(rva=a,preimage=b.hex()) for a,b,_ in hooks]
    metadata['output_sha256']=hashlib.sha256(result).hexdigest()
    return bytes(result),metadata
