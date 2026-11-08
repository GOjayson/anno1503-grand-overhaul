"""Generate nine fingerprint-bound transient hooks for the private start-options build."""
from pathlib import Path
import hashlib
import struct
import sys
import os

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
sys.path[:0]=[str(WORK),str(WORK/'_tools'),str(WORK/'engine_audit'),str(WORK/'native_world'),
              str(WORK/'engine_resume/ai_loader'),str(WORK/'engine_resume/route_coverage'),
              str(WORK/'engine_resume/ai_food/experiment_runtime')]
from generate_runtime_test_blobs import bytes_array,relocated_fields
from bridge_codegen import build_bridge,COMMON_UNWIND
from frame_factory_bridge import build_factory_code,FACTORY_CALL_RVA,FACTORY_CALL_BYTES
from patch_scene_copy import build_code,PREPARE_RVA,PREPARE_BEFORE,GUARD_RVA,GUARD_BEFORE
from patch_frame_copy import pe_info
from loader_bridge import build_loader_bridge,LOADER_RVA,LOADER_BEFORE,LEAF_UNWIND
from direct_bridge import build_direct_bridge
from postprofile_bridge import build_postprofile_code,SITE,BEFORE
from attempt_bridge import build_attempt_code,SITE as ATTEMPT_SITE,BEFORE as ATTEMPT_BEFORE
from world_policy_bridge import build_world_policy_code,HOOK as POLICY_SITE,BEFORE as POLICY_BEFORE,LEAF_UNWIND as POLICY_UNWIND

def main():
    game=Path(os.environ.get('ANNO1503_SOURCE_GAME',WORK.parent))
    frame=(game/'AnnoFrame.dll').read_bytes();scene=(game/'AnnoScene.dll').read_bytes()
    welt=(game/'AnnoWelt.dll').read_bytes()
    _,opt,_,_,off=pe_info(scene)
    pdata,size=struct.unpack_from('<II',scene,opt+112+3*8)
    entries=[struct.unpack_from('<III',scene,off(pdata)+i) for i in range(0,size,12)]
    prepare_parent=struct.unpack_from('<III',scene,off(0x4a180)+4)
    application_parent=next(e for e in entries if e[0]==0xc250)
    delta=0x123456
    flag,names,hooks,functions=build_bridge(0);flag2,*_=build_bridge(delta)
    factory,fn=build_factory_code(0);factory2,_=build_factory_code(delta)
    sc,sn,_=build_code(0);sc2,*_=build_code(delta)
    direct,dn,dh,df=build_direct_bridge(0);direct2,*_=build_direct_bridge(delta)
    post,pn,pf=build_postprofile_code(0);post2,*_=build_postprofile_code(delta)
    attempt,an,af=build_attempt_code(0);attempt2,*_=build_attempt_code(delta)
    loader,ln=build_loader_bridge(0);loader2,_=build_loader_bridge(delta)
    policy,pwn=build_world_policy_code(0);policy2,_=build_world_policy_code(delta)
    blobs=[
      ('flag','AnnoFrame.dll',frame,flag,flag2,functions,[],[(hooks[0][0],hooks[0][1],names['worldsettings_start'],0)]),
      ('factory','AnnoFrame.dll',frame,factory,factory2,[(fn['factory_bridge'],fn['factory_bridge_end'],COMMON_UNWIND)],
       [(fn['factory_export_iat'],'WorldSettingsCreateScene')],[(FACTORY_CALL_RVA,FACTORY_CALL_BYTES,fn['factory_bridge'],1)]),
      ('scene','AnnoScene.dll',scene,sc,sc2,
       [(sn['prepare'],sn['prepare_end'],bytes.fromhex('21000000')+struct.pack('<III',*prepare_parent)),
        (sn['resource_guard'],sn['resource_guard_end'],bytes.fromhex('21000000')+struct.pack('<III',*application_parent))],
       [(sn['prepare_iat'],'WorldSettingsPrepareScene'),(sn['active_iat'],'WorldSettingsIsActive')],
       [(PREPARE_RVA,PREPARE_BEFORE,sn['prepare'],0),(GUARD_RVA,GUARD_BEFORE,sn['resource_guard'],0)]),
      ('direct','AnnoFrame.dll',frame,direct,direct2,df,[],[(dh[0][0],dh[0][1],dn['direct_start'],1)]),
      ('postprofile','AnnoFrame.dll',frame,post,post2,pf,[(pn['after_profiles_iat'],'WorldSettingsAfterProfiles')],[(SITE,BEFORE,pn['postprofile'],1)]),
      ('native_attempt','AnnoFrame.dll',frame,attempt,attempt2,af,
       [(an['begin_attempt_iat'],'WorldSettingsBeginNativeWorldStart'),(an['end_attempt_iat'],'WorldSettingsEndNativeWorldStart')],
       [(ATTEMPT_SITE,ATTEMPT_BEFORE,an['native_attempt'],1)]),
      ('ai_loader','AnnoWelt.dll',welt,loader,loader2,[(ln['entry'],ln['end'],LEAF_UNWIND)],[(ln['iat'],'WorldSettingsLoadAiModule')],[(LOADER_RVA,LOADER_BEFORE,ln['entry'],1)]),
      ('world_policy','AnnoWelt.dll',welt,policy,policy2,[(pwn['entry'],pwn['end'],POLICY_UNWIND)],[],[(POLICY_SITE,POLICY_BEFORE,pwn['entry'],0)])]
    output=['/* Generated private dev3 native hook metadata. */\n#include <stdint.h>\n#include <wchar.h>\n',
      'typedef struct {uint32_t offset;} WSRelocation;\n',
      'typedef struct {uint32_t offset;const char *name;} WSImportCell;\n',
      'typedef struct {uint32_t begin,end;const unsigned char *unwind;uint32_t unwindSize;} WSFunctionMeta;\n',
      'typedef struct {uint32_t rva,length;const unsigned char *before;uint32_t target;int call;} WSHook;\n',
      'typedef struct {const wchar_t *module;unsigned char sha256[32];const unsigned char *code;uint32_t codeSize;const WSRelocation *relocs;uint32_t relocCount;const WSImportCell *imports;uint32_t importCount;const WSFunctionMeta *functions;uint32_t functionCount;const WSHook *hooks;uint32_t hookCount;} WSBlob;\n']
    descriptors=[];report=[]
    for label,module,original,code,code2,functions,imports,hooks in blobs:
        fields=relocated_fields(code,code2,[(f[0],f[1]) for f in functions],delta)
        output.append(bytes_array(label+'_code',code))
        output.append('static const WSRelocation '+label+'_relocs[] = {'+','.join('{'+str(v)+'}' for v in fields)+'};\n')
        if imports:output.append('static const WSImportCell '+label+'_imports[] = {'+','.join('{'+str(at)+',"'+name+'"}' for at,name in imports)+'};\n')
        for index,f in enumerate(functions):output.append(bytes_array(label+'_unwind_'+str(index),f[2]))
        output.append('static const WSFunctionMeta '+label+'_functions[] = {'+','.join('{'+f'{b},{e},{label}_unwind_{i},{len(u)}'+'}' for i,(b,e,u) in enumerate(functions))+'};\n')
        for index,(_,before,_,_) in enumerate(hooks):output.append(bytes_array(label+'_before_'+str(index),before))
        output.append('static const WSHook '+label+'_hooks[] = {'+','.join('{'+f'{r},{len(b)},{label}_before_{i},{t},{call}'+'}' for i,(r,b,t,call) in enumerate(hooks))+'};\n')
        sha=','.join(f'0x{x:02x}' for x in hashlib.sha256(original).digest())
        descriptors.append('{L"'+module+'",{'+sha+'},'+f'{label}_code,{len(code)},{label}_relocs,{len(fields)},'+(f'{label}_imports,{len(imports)},' if imports else '0,0,')+f'{label}_functions,{len(functions)},{label}_hooks,{len(hooks)}'+'}')
        report.append(dict(label=label,module=module,code_bytes=len(code),relocations=len(fields),hooks=len(hooks)))
    output.append('static const WSBlob wsBlobs[] = {'+','.join(descriptors)+'};\n')
    (HERE/'runtime_test_blobs.h').write_text(''.join(output))
    print(report)

if __name__=='__main__':main()
