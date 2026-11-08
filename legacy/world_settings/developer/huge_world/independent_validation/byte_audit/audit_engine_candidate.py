"""Independent byte-level audit of the combined experimental native engine.

Uses the two separately reviewed manifests and the root's runtime transaction,
without trusting the combined transform to explain its own changed bytes. No
DLL, process, game copy, release or backup is written by this audit.
"""
from pathlib import Path
import hashlib,importlib.util,json,re,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[2]
PACKAGE=GAME/'WorldSettings_Work/anno1503_food_world_dev8'
ENGINE=PACKAGE/'developer/huge_world'
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(blob):return hashlib.sha256(blob).hexdigest()


def file_sha(path):return sha(path.read_bytes())


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def main():
    original=(GAME/'AnnoWelt.dll').read_bytes()
    dev7=(GAME/'WorldSettings_Work/anno1503_food_world_dev7/native/AnnoWelt.world.dll').read_bytes()
    require(sha(original)=='ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9','Original HE World fingerprint changed')
    require(sha(dev7)=='059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319','Working dev7 Food/world World fingerprint changed')
    p=pefile.PE(data=dev7);require(p.FILE_HEADER.Machine==0x8664 and p.OPTIONAL_HEADER.Magic==0x20b,'Only exact AMD64 PE32+ is reviewed')
    plan=json.loads((ENGINE/'runtime_engine_edits.json').read_bytes())
    grid=json.loads((ENGINE/'grid/runtime_grid_edits.json').read_bytes())
    nav=json.loads((ENGINE/'navigation/navigation_patch_manifest.json').read_bytes())
    visibility=json.loads((ENGINE/'visibility/visibility_repair_plan.json').read_bytes())if plan['engine_instruction_count']>119 else None
    expected=[]
    for edit in grid['edits']:
        expected.append(dict(rva=edit['rva'],before=edit['before_instruction'],after=edit['after_instruction'],component='world_grid'))
    for edit in nav['edits']:
        before,after=bytes.fromhex(edit['before']),bytes.fromhex(edit['after'])
        require(len(before)==len(after)==edit['length'],'Navigation region length differs')
        for k in range(0,len(before),32):expected.append(dict(rva=edit['rva']+k,before=before[k:k+32].hex(),after=after[k:k+32].hex(),component='navigation'))
    if visibility:
        require(len(visibility['edits'])==47 and visibility['new_stack_frame']==0xe0ce8,'Visibility repair layout differs from reviewed128-column producer')
        for edit in visibility['edits']:expected.append(dict(rva=edit['rva'],before=edit['before'],after=edit['after'],component='visibility'))
    expected.sort(key=lambda r:r['rva'])
    require(plan.get('profile')=='history-amd64-world-ship-render-and-recenter-v4'and set(plan.get('modules',{}))=={'AnnoWelt.dll','AnnoFrame.dll'},'Expected exact multi-module depth profile')
    actual=[{k:row[k]for k in ['rva','before','after']}for row in plan['edits']if row['module']=='AnnoWelt.dll']
    require(actual==[{k:row[k]for k in ['rva','before','after']}for row in expected],
        'Combined runtime transaction differs from complete independent grid/navigation manifests')
    world_count=len(expected);visibility_regions=len(visibility['edits'])if visibility else 0;navigation_chunks=world_count-len(grid['edits'])-visibility_regions
    depth_manifest=json.loads((ENGINE/'bias/frame_bias_manifest.json').read_bytes())
    frame_edits=[{k:row[k]for k in ['rva','before','after']}for row in plan['edits']if row['module']=='AnnoFrame.dll']
    expected_frame=sorted([{k:row[k]for k in ['rva','before','after']}for row in depth_manifest['runtime_edits']],key=lambda r:r['rva'])
    require(frame_edits==expected_frame and len(frame_edits)==7,'Frame transaction differs from all independently reviewed leaf/scalar/call chunks')
    engine_count=world_count+len(frame_edits)
    require(engine_count==plan['engine_instruction_count']and world_count==166 and len(grid['edits'])==104,'Expected complete166 World regions and separate Frame depth repair')
    header_path=PACKAGE/'developer/source/engine_resume/ai_loader/engine_patch_plan.h'
    header=header_path.read_text()
    expression=re.compile(r'^\{([01])u,0x([0-9a-f]+)u,(\d+)u,\{([^}]+)\},\{([^}]+)\}\},?$',re.M)
    header_rows=[]
    for match in expression.finditer(header):
        module,rva,length=int(match[1]),int(match[2],16),int(match[3]);before=bytes(int(x,16)for x in match[4].split(','));after=bytes(int(x,16)for x in match[5].split(','))
        require(1<=length<=32 and len(before)==len(after)==length,'Invalid compiled native transaction row')
        header_rows.append(dict(module='AnnoWelt.dll'if module==0 else'AnnoFrame.dll',rva=rva,before=before.hex(),after=after.hex()))
    require(header_rows==[{k:row[k]for k in ['module','rva','before','after']}for row in plan['edits']]and ('#define WS_ENGINE_PATCH_COUNT '+str(engine_count))in header,'Compiled C transaction differs from reviewed multi-module JSON plan')
    disk=nav.get('disk_profile_edits',{}).get('dev7',[])
    require(len(disk)==2 and plan.get('disk_only_exception_edits')==disk,'Copied active exception directory edits differ from navigation profile')
    for edit in disk:
        require(edit['rva']in(0x16319c,0x1631a4),'Unexpected copied exception record')
        expected.append(dict(rva=edit['rva'],before=edit['before'],after=edit['after'],component='copied_active_unwind'))
    expected.sort(key=lambda r:r['rva'])
    changed=bytearray(dev7);covered=set();sections={}
    for i,edit in enumerate(expected):
        before,after=bytes.fromhex(edit['before']),bytes.fromhex(edit['after']);rva=edit['rva'];offset=p.get_offset_from_rva(rva)
        require(dev7[offset:offset+len(before)]==before,'Native full preimage differs at '+hex(rva))
        if edit['component']!='copied_active_unwind':
            require(original[offset:offset+len(before)]==before,'Native HE preimage differs at '+hex(rva))
        require(not covered.intersection(range(offset,offset+len(before))),'Native transaction edits overlap')
        section=p.get_section_by_rva(rva);require(section is not None,'Patch outside PE section')
        require(p.get_offset_from_rva(rva+len(before)-1)==offset+len(before)-1,'Patch crosses raw section geometry')
        if not section.Characteristics&0x20000000:
            require((edit['component']=='navigation'and rva in (0x14be8c,0x14be94))or(edit['component']=='visibility'and rva==0x11f336),'Non-executable patch is not reviewed native unwind metadata')
        for hook,length in [(0xc714d,6),(0xdf460,6)]:
            require(max(rva,hook)>=min(rva+len(before),hook+length),'Expanded engine patch overlaps an existing Food/world hook')
        changed[offset:offset+len(after)]=after;covered.update(range(offset,offset+len(before)))
        name=section.Name.rstrip(b'\0').decode();sections[name]=sections.get(name,0)+1
    output=bytes(changed);changed_bytes=sum(a!=b for a,b in zip(dev7,output))
    require(len(output)==len(dev7)and sha(output)==plan['patched_welt_sha256'],'Independent complete candidate output differs')
    combined=load('independent_checked_combined_huge',ENGINE/'engine_patch.py')
    candidate,manifest=combined.transform_huge_welt(dev7)
    require(candidate==output,'Packaged combined transform differs from independent composition')
    same,idempotent=combined.transform_huge_welt(output);require(same==output and idempotent.get('idempotent')is True,'Exact combined candidate is not idempotent')
    mutations=[]
    for label,blob in [('original_without_Food_world_bridge',original),('wrong_architecture',b'MZ'+bytes(len(dev7)-2)),('partially_applied_plan',bytes(changed[:p.get_offset_from_rva(expected[-1]['rva'])])+dev7[p.get_offset_from_rva(expected[-1]['rva']):])]:
        try:combined.transform_huge_welt(blob)
        except ValueError:mutations.append(label)
        else:raise ValueError('Combined transform accepted '+label)
    for n,(a,b)in enumerate(zip(dev7,output)):
        require(a==b or n in covered,'Byte outside reviewed engine domains changed')
    # Parsing the actual changed .pdata image also verifies the revised chained
    # ranges are consumable PE exception records, not stray code constants.
    modified_pe=pefile.PE(data=output)
    unwind=[dict(begin=hex(e.struct.BeginAddress),end=hex(e.struct.EndAddress),unwind=hex(e.struct.UnwindData))for e in modified_pe.DIRECTORY_ENTRY_EXCEPTION if 0x67fe0<=e.struct.BeginAddress<0x68060]
    require([(int(r['begin'],16),int(r['end'],16))for r in unwind]==[(0x67fe0,0x68024),(0x68024,0x68059),(0x68059,0x6805f)],'Shared navigation accessor revised unwind coverage differs')
    if visibility:
        require(world_count==166,'Retained World visibility profile must include166 atomic World regions')
        entry=next(e for e in modified_pe.DIRECTORY_ENTRY_EXCEPTION if e.struct.BeginAddress==0xca2f0)
        require(entry.struct.EndAddress==0xcafbb and entry.struct.UnwindData==0x11f330 and int.from_bytes(modified_pe.get_data(0x11f336,4),'little')==0xe0ce8,'View producer native unwind allocation differs')
    frame_original=(GAME/'AnnoFrame.dll').read_bytes();frame_input=(GAME/'WorldSettings_Work/anno1503_food_world_dev7/native/AnnoFrame.world.dll').read_bytes()
    require(sha(frame_original)=='046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf','Working Food Frame source differs')
    require(plan['modules']['AnnoFrame.dll']['source_sha256']==sha(frame_original)and plan['modules']['AnnoFrame.dll']['copied_input_sha256']==sha(frame_input),'Frame exact module source/copy binding differs')
    fp=pefile.PE(data=frame_input);frame_changed=bytearray(frame_input);frame_covered=set()
    require(depth_manifest['disk_only_metadata_edits']==plan['disk_only_frame_edits']and len(plan['disk_only_frame_edits'])==1,'Frame disk-only metadata declaration differs')
    for edit in frame_edits:
        before,after=bytes.fromhex(edit['before']),bytes.fromhex(edit['after']);offset=fp.get_offset_from_rva(edit['rva'])
        require(frame_input[offset:offset+len(before)]==frame_original[offset:offset+len(before)]==before,'Exact loaded/copied Frame preimage differs')
        require(not frame_covered.intersection(range(offset,offset+len(before))),'Frame guarded edits overlap')
        frame_changed[offset:offset+len(after)]=after;frame_covered.update(range(offset,offset+len(before)))
        for hook,length in[(0x43e44,6),(0x44bb0,9),(0x55c54,6),(0x55f2e,5),(0x5746b,5)]:
            require(max(edit['rva'],hook)>=min(edit['rva']+len(before),hook+length),'Frame depth repair overlaps gameplay hook')
    for edit in plan['disk_only_frame_edits']:
        before,after=bytes.fromhex(edit['before']),bytes.fromhex(edit['after']);offset=edit['file_offset']
        require(frame_input[offset:offset+len(before)]==before and len(before)==len(after)==4,'Frame text metadata preimage differs')
        frame_changed[offset:offset+len(after)]=after;frame_covered.update(range(offset,offset+len(before)))
    frame_output=bytes(frame_changed)
    require(sha(frame_output)==plan['modules']['AnnoFrame.dll']['patched_sha256']==depth_manifest['output_sha256'],'Independent Frame output differs')
    require(all(a==b or i in frame_covered for i,(a,b)in enumerate(zip(frame_input,frame_output))),'Unexplained Frame byte changed')
    actual_frame,frame_metadata=combined.transform_huge_frame(frame_input)
    require(actual_frame==frame_output,'Combined Frame transform differs from independent byte composition')
    same_frame,idem_frame=combined.transform_huge_frame(frame_output)
    require(same_frame==frame_output and idem_frame.get('idempotent')is True,'Exact Frame output is not idempotent')
    for module,expected_source,expected_input,expected_output in [('AnnoWelt.dll',sha(original),sha(dev7),sha(output)),('AnnoFrame.dll',sha(frame_original),sha(frame_input),sha(frame_output))]:
        require(plan['modules'][module]==dict(source_sha256=expected_source,copied_input_sha256=expected_input,patched_sha256=expected_output),'Module fingerprint table mismatch: '+module)
    report=dict(scope=__doc__,passed=True,architecture='AMD64 PE32+',game_executed=False,
        original_welt_sha256=sha(original),dev7_welt_sha256=sha(dev7),patched_welt_sha256=sha(output),
        patched_frame_sha256=sha(frame_output),engine_modules=plan['modules'],world_instruction_count=world_count,frame_instruction_count=len(frame_edits),
        frame_disk_only_metadata_edits=1,frame_changed_file_bytes=sum(a!=b for a,b in zip(frame_input,frame_output)),
        runtime_plan_sha256=file_sha(header_path),engine_instruction_count=engine_count,grid_instruction_count=104,navigation_regions=len(nav['edits']),navigation_transaction_chunks=navigation_chunks,copied_active_exception_metadata_edits=2,
        visibility_repair_regions=visibility_regions,repaired_view_producer_stack_frame=0xe0ce8 if visibility else None,
        changed_file_bytes=changed_bytes,declared_instruction_or_unwind_bytes=len(covered),length_preserved=True,
        all_changes_explained_by_reviewed_operands=True,food_and_world_hooks_preserved=True,
        original_native_member_offsets_retained=True,compiled_header_equals_complete_json_transaction=True,
        independent_composition_equals_packaged_transform=True,exact_complete_output_idempotent=True,rejected_mutations=mutations,
        patched_shared_accessor_unwind_records=unwind,patch_counts_by_PE_section=sections,
        runtime_transaction_requires_quiescent_threads_and_no_existing_world=True,
        original_or_dev7_or_game_copy_or_backups_modified=False,
        inputs_sha256={str(path.relative_to(GAME)):file_sha(path)for path in [Path(__file__),ENGINE/'runtime_engine_edits.json',header_path,ENGINE/'grid/runtime_grid_edits.json',ENGINE/'navigation/navigation_patch_manifest.json',ENGINE/'engine_patch.py',ENGINE/'bias/frame_bias_manifest.json',ENGINE/'bias/frame_bias_patch.py']+([ENGINE/'visibility/visibility_repair_plan.json',ENGINE/'visibility/world_visibility_patch.py']if visibility else [])})
    target=HERE/'engine_candidate_independent_audit.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key]for key in ['passed','patched_welt_sha256','engine_instruction_count','changed_file_bytes','patched_shared_accessor_unwind_records']},indent=2))


if __name__=='__main__':main()
