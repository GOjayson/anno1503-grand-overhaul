"""Native two-renderer Frame fixtures for world-centered Huge depth bias.

Both native renderer prefixes execute through their actual state4 submission.
Only Display virtual setters are fixture callbacks. No actual game/GPU run.
"""
from pathlib import Path
import importlib.util,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]


def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m


N=load('bias_native_frame_fixture',HERE.parent/'frame_depth/test_frame_depth_candidate.py')
P=load('bias_native_subject',HERE/'frame_bias_patch.py')


def alternate(engine,dimensions):
 if dimensions is None:return None
 u=engine.u;engine.setters=[];engine.origin=None;sp=engine.stack+0x1ff008
 u.mem_write(sp,struct.pack('<Q',engine.stop));u.reg_write(N.UC_X86_REG_RSP,sp);u.reg_write(N.UC_X86_REG_RCX,engine.camera);u.reg_write(N.UC_X86_REG_RDX,1<<18);u.reg_write(N.UC_X86_REG_R8,0)
 u.emu_start(engine.base+0x1c6e0,engine.base+0x1c802,count=2000000);N.require(len(engine.setters)==1,'Alternate native renderer did not submit exactly one state4')
 return dict(state4=engine.setters[0],origin=engine.origin)


def main():
 source=(N.GAME/'AnnoFrame.dll').read_bytes();candidate,manifest=P.transform_frame_bias(source)
 N.require(candidate==(HERE/'AnnoFrame.food_original.bias2.dll').read_bytes(),'Exact candidate changed')
 hp=WORK/'grid/border/h12diag_display_depth.json';hdoc=json.loads(hp.read_bytes());heights=hdoc['world_height_table']['values'];N.require(len(heights)==256,'All native heights needed')
 rows=[];legacy=0;huge=0;minimum=1.;maximum=0.;biases={i:set()for i in range(4)}
 for base in[0x180000000,0x280000000]:
  old=N.Native(source,base);new=N.Native(candidate,base)
  for dims in[(256,256),(512,512),(1024,1024),(2048,2048),None,(2048,1024)]:
   for view in[(1920.,1408.),(2880.,1848.)]:
    for rotation in range(4):
     for zoom in range(3):
      for center in[(16.,16.),(1024.,1024.),(2032.,2032.)]:
       target=(-center[0],0.,-center[1]);a=old.run(dims,view,rotation,zoom,target);b=new.run(dims,view,rotation,zoom,target);aa=alternate(old,dims);bb=alternate(new,dims)
       if dims!=(2048,2048):N.require(a==b and aa==bb,'Legacy/null/nonsquare output differs');legacy+=1
       else:
        huge+=1
        for field in['main','secondary','camera_state','origin']:N.require(a[field]==b[field],'Camera/sprite/local-bias/viewport source changed')
        for label,left,right in[('primary',a,b),('alternate',aa,bb)]:
         N.require(all(left['state4'][i*4:i*4+4]==right['state4'][i*4:i*4+4]for i in range(16)if i!=14),'Original state4 slope/XY/height precision changed')
         m=struct.unpack('<16f',right['state4']);N.require(left['origin']==right['origin'],'Viewport origin changed')
         values=[N.z(m,x,h,y)for x in[0.,2048.]for y in[0.,2048.]for h in heights]
         lo,hi=min(values),max(values);N.require(0.<lo<=hi<1.,'Full Huge native height/coordinate depth leaves domain')
         minimum=min(minimum,lo);maximum=max(maximum,hi);biases[rotation].add(m[14])
        N.require(b['state4']==bb['state4'],'Two native renderer paths have different Huge bias')
       rows.append(dict(base=hex(base),dimensions=dims,viewport=view,rotation=rotation,zoom=zoom,center=center,legacy_exact=dims!=(2048,2048),both_renderer_prefixes_tested=dims is not None))
 N.require(all(len(v)==1 for v in biases.values()),'Huge bias depends on camera/zoom/viewport, which would invalidate cached depths')
 leaf=[]
 for base in[0x180000000,0x280000000]:
  f=N.Native(candidate,base);u=f.u
  for dims in[None,(256,256),(512,512),(1024,1024),(2048,2048),(2048,1024),(1024,2048)]:
   for rotation,(dx,dy)in enumerate([(-.00023663246247451752,-.00023663246247451752),(-.00023663246247451752,.00023663246247451752),(.00023663246247451752,.00023663246247451752),(.00023663246247451752,-.00023663246247451752)]):
    u.mem_write(f.camera,bytes(0xd0000));u.mem_write(f.world,bytes(0x2000))
    if dims is not None:u.mem_write(f.camera+0x18,struct.pack('<Q',f.world));u.mem_write(f.world+0x1d8,struct.pack('<II',*dims))
    u.mem_write(f.camera+0xc01a8,struct.pack('<f',dx));u.mem_write(f.camera+0xc01c8,struct.pack('<f',dy))
    regs=[N.UC_X86_REG_RAX,N.UC_X86_REG_RBX,N.UC_X86_REG_RCX,N.UC_X86_REG_RDX,N.UC_X86_REG_RSI,N.UC_X86_REG_RDI,N.UC_X86_REG_RBP,N.UC_X86_REG_R8,N.UC_X86_REG_R9,N.UC_X86_REG_R10,N.UC_X86_REG_R11,N.UC_X86_REG_R12,N.UC_X86_REG_R13,N.UC_X86_REG_R14,N.UC_X86_REG_R15]
    expected={r:0x7171000000000000+i for i,r in enumerate(regs)};expected[N.UC_X86_REG_RDI]=f.camera
    for r,v in expected.items():u.reg_write(r,v)
    xmms={N.UC_X86_REG_XMM0+i:(1<<127)+0x51230+i for i in range(16)}
    for r,v in xmms.items():u.reg_write(r,v)
    sp=f.stack+0x1ff008;u.mem_write(sp,struct.pack('<Q',f.stop));u.reg_write(N.UC_X86_REG_RSP,sp);u.emu_start(base+P.CAVE,f.stop,count=1000)
    N.require(all(u.reg_read(r)==v for r,v in expected.items()),'Leaf changedGPR');N.require(all(u.reg_read(r)==v for r,v in xmms.items()if r!=N.UC_X86_REG_XMM0),'Leaf changed anotherXMM');N.require(u.reg_read(N.UC_X86_REG_RSP)==sp+8,'Leaf return stack differs')
    wanted=N.f32(.5-N.f32(N.f32(dx+dy)*1024.))if dims==(2048,2048)else .5
    N.require(u.reg_read(N.UC_X86_REG_XMM0)==int.from_bytes(struct.pack('<f',wanted),'little'),'Leaf scalar/fullXMM0 result differs')
    leaf.append(dict(base=hex(base),dimensions=dims,rotation=rotation,GPRs_otherXMMs_and_return_stack_preserved=True))
 report=dict(passed=True,scope=__doc__,source_frame_sha256=P.sha(source),candidate_frame_sha256=P.sha(candidate),patch_source_sha256=P.sha((HERE/'frame_bias_patch.py').read_bytes()),test_source_sha256=P.sha(Path(__file__).read_bytes()),
  native_camera_cases=len(rows),primary_and_alternate_renderer_cases=sum(2 for r in rows if r['both_renderer_prefixes_tested']),legacy_null_nonsquare_exact_cases=legacy,Huge_native_cases=huge,
  native_leaf_register_cases=len(leaf),all_256_actual_native_heights_tested=True,native_height_source_sha256=P.sha(hp.read_bytes()),Huge_complete_coordinate_depth_bounds=[minimum,maximum],
  orientation_biases={str(k):list(v)for k,v in biases.items()},all_original_XY_and_height_depth_slopes_bit_identical=True,both_native_renderer_paths_consistent=True,
  original_secondary_state6_matrix_and_viewport_origin_bit_identical=True,bias_is_camera_zoom_viewport_independent=True,
  native_pixel_branch_equivalence_verified_by_this_fixture=False,actual_game_runs=0,game_or_input_files_modified=False,cases=rows,leaf_cases=leaf)
 out=HERE/'frame_bias_native_results.json';N.require(not out.exists(),'Preserve prior native proof');out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(passed=True,camera_cases=len(rows),renderer_cases=report['primary_and_alternate_renderer_cases'],legacy_exact=legacy,huge=huge,leaf=len(leaf),depth_bounds=report['Huge_complete_coordinate_depth_bounds'])))


if __name__=='__main__':main()
