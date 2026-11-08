"""Whole native Frame construction/state4 fixtures for conditional2048 depth.

Runs native camera construction/trig and the actual1c300 state4 setup prefix in
a bounded emulator. Display virtual setters alone are observed/returned. This
is not a game/GPU run; independent World→Display tests cover downstream use.
"""
from pathlib import Path
import hashlib,importlib.util,json,struct,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[3]
sys.path.insert(0,str(GAME/'WorldSettings_Work/_tools'))
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
s=importlib.util.spec_from_file_location('conditional_depth_subject',HERE/'frame_depth_patch.py')
P=importlib.util.module_from_spec(s);sys.modules[s.name]=P;s.loader.exec_module(P)


def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,m):
 if not ok:raise ValueError(m)
def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]
def z(m,x,h,y):return f32(f32(f32(f32(h*m[6])+f32(x*m[2]))+f32(y*m[10]))+m[14])


class Native:
 def __init__(self,blob,base):
  self.base=base;self.u=u=Uc(UC_ARCH_X86,UC_MODE_64);p=pefile.PE(data=blob);p.relocate_image(base);image=p.get_memory_mapped_image()
  u.mem_map(base,(len(image)+4095)&~4095);u.mem_write(base,bytes(image))
  self.stack=0x4000000;self.camera=0x5000000;self.world=0x6000000;self.display=0x7000000;self.stop=0x8000000
  for a,n in[(self.stack,0x200000),(self.camera,0xd0000),(self.world,0x2000),(self.display,0x2000),(self.stop,0x1000)]:u.mem_map(a,n)
  self.setters=[];u.hook_add(UC_HOOK_CODE,self.setter,begin=self.stop+0x100,end=self.stop+0x200)
 def setter(self,u,pc,size,unused):
  if pc==self.stop+0x100:self.origin=bytes(u.mem_read(u.reg_read(UC_X86_REG_RDX),12))
  elif pc==self.stop+0x200:
   require(u.reg_read(UC_X86_REG_RDX)==4,'Unexpected observed Display state');self.setters.append(bytes(u.mem_read(u.reg_read(UC_X86_REG_R8),64)))
  else:raise ValueError('Unexpected fixture callback')
  sp=u.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',u.mem_read(sp,8))[0];u.reg_write(UC_X86_REG_RAX,0);u.reg_write(UC_X86_REG_RSP,sp+8);u.reg_write(UC_X86_REG_RIP,ret)
 def run(self,dimensions,viewport,orientation,zoom_code,target):
  u=self.u;c=self.camera;u.mem_write(c,bytes(0xd0000));u.mem_write(self.world,bytes(0x2000))
  if dimensions is not None:u.mem_write(c+0x18,struct.pack('<Q',self.world));u.mem_write(self.world+0x1d8,struct.pack('<II',*dimensions))
  u.mem_write(c+8,struct.pack('<Q',self.display));u.mem_write(self.display,struct.pack('<Q',self.display+0x1000))
  u.mem_write(self.display+0x1000+0xe8,struct.pack('<Q',self.stop+0x100));u.mem_write(self.display+0x1000+0xf0,struct.pack('<Q',self.stop+0x200))
  u.mem_write(c+0xc0188,struct.pack('<6f',0.,0.,0.,viewport[0],viewport[1],0.));u.mem_write(c+0xc0320,struct.pack('<3f',*target));u.mem_write(c+0xc0310,struct.pack('<3f',*target))
  scale=[1.,.5,.25][zoom_code];u.mem_write(c+0xc0308,bytes([orientation]));u.mem_write(c+0xc030c,struct.pack('<f',scale))
  sp=self.stack+0x1ff008;u.mem_write(sp,struct.pack('<Q',self.stop));u.reg_write(UC_X86_REG_RSP,sp);u.reg_write(UC_X86_REG_RCX,c);u.reg_write(UC_X86_REG_RDX,zoom_code)
  u.emu_start(self.base+0x1cc20,self.base+0x1ce48,count=2000000);require(u.reg_read(UC_X86_REG_RIP)==self.base+0x1ce48,'Native camera prefix did not finish')
  state=bytes(u.mem_read(c+0xc0188,0x1a0));main=bytes(u.mem_read(c+0xc01a0,64));secondary=bytes(u.mem_read(c+0xc02c8,64))
  # The real render function requires nonnull World to enter; null-world
  # normalization is separately checked through the constructor and leaf tests.
  if dimensions is None:return dict(main=main,secondary=secondary,camera_state=state,state4=None,origin=None)
  self.setters=[];self.origin=None;u.mem_write(sp,struct.pack('<Q',self.stop));u.reg_write(UC_X86_REG_RSP,sp);u.reg_write(UC_X86_REG_RCX,c);u.reg_write(UC_X86_REG_RDX,1<<18)
  u.emu_start(self.base+0x1c300,self.base+0x1c429,count=2000000);require(len(self.setters)==1,'Actual native state4 setter was not reached exactly once')
  return dict(main=main,secondary=secondary,camera_state=state,state4=self.setters[0],origin=self.origin)


def main():
 source=(GAME/'AnnoFrame.dll').read_bytes();candidate,manifest=P.transform_frame_depth(source)
 preserved_candidate=(HERE/'AnnoFrame.food_original.depth.dll').read_bytes();require(candidate==preserved_candidate,'Candidate output differs from pure transform')
 live_path=GAME/'WorldSettings_Work/huge_engine_work/grid/border/h12diag_display_depth.json';live=json.loads(live_path.read_bytes());heights=live['world_height_table']['values']
 require(len(heights)==256 and min(heights)==0 and max(heights)<10.21,'Bound actual native height lookup missing')
 rows=[];global_min=1.;global_max=0.;legacy=0;huge=0
 for base in[0x180000000,0x280000000]:
  old=Native(source,base);new=Native(candidate,base)
  for dimensions in[(256,256),(512,512),(1024,1024),(2048,2048),None,(2048,1024)]:
   for viewport in[(1920.,1408.),(2880.,1848.)]:
    for orientation in range(4):
     for zoom_code in range(3):
      for center in[(16.,16.),(1024.,1024.),(2032.,2032.)]:
       target=(-center[0],0.,-center[1]);a=old.run(dimensions,viewport,orientation,zoom_code,target);b=new.run(dimensions,viewport,orientation,zoom_code,target)
       ishuge=dimensions==(2048,2048)
       if not ishuge:require(a==b,'Legacy/null/rectangular Frame output changed');legacy+=1
       else:
        huge+=1
        for field in['main','secondary','state4']:
         x=struct.unpack('<16f',a[field]);y=struct.unpack('<16f',b[field])
         require(all(a[field][k*4:k*4+4]==b[field][k*4:k*4+4]for k in range(16)if k not in[2,6,10,14]),'ScreenXY/homogeneous coefficient changed')
         require(all(y[k]==x[k]*.5 for k in[2,6,10]),'Depth coefficients did not scale exactly byonehalf')
         if field!='main':require(y[14]==x[14]==.5,'Fixed cached draw depth bias changed')
        require(a['origin'][:8]==b['origin'][:8],'Screen pan/origin XY changed')
        matrix=struct.unpack('<16f',b['state4']);depths=[z(matrix,x,h,y)for x in[0.,2048.]for y in[0.,2048.]for h in heights]
        lo,hi=min(depths),max(depths);require(0.<lo<=hi<1.,'Huge full-coordinate/native-height range leaves depth domain')
        global_min=min(global_min,lo);global_max=max(global_max,hi)
       rows.append(dict(image_base=hex(base),dimensions=dimensions,viewport=viewport,orientation=orientation,zoom_code=zoom_code,center=center,legacy_exact_output_equal=not ishuge,huge_depth_half_only=ishuge))
 # Each leaf restores allGPRs/RSP, preserves allotherXMMs and clears high96bits
 # ofXMM0 exactly as the replaced memory MOVSS. Flags are deliberately dead.
 leaf_cases=[]
 for base in[0x180000000,0x280000000]:
  n=Native(candidate,base);u=n.u
  for entry in[P.MAIN_ENTRY,P.SECONDARY_ENTRY]:
   for dimensions in[None,(256,256),(512,512),(1024,1024),(2048,2048),(2048,1024),(1024,2048)]:
    u.mem_write(n.camera,bytes(0xd0000));u.mem_write(n.world,bytes(0x2000))
    if dimensions is not None:u.mem_write(n.camera+0x18,struct.pack('<Q',n.world));u.mem_write(n.world+0x1d8,struct.pack('<II',*dimensions))
    regs=[UC_X86_REG_RAX,UC_X86_REG_RBX,UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_RSI,UC_X86_REG_RDI,UC_X86_REG_RBP,UC_X86_REG_R8,UC_X86_REG_R9,UC_X86_REG_R10,UC_X86_REG_R11,UC_X86_REG_R12,UC_X86_REG_R13,UC_X86_REG_R14,UC_X86_REG_R15]
    expected={r:0x5555000000000000+i for i,r in enumerate(regs)};expected[UC_X86_REG_RBX]=n.camera+0xc0188;expected[UC_X86_REG_RDI]=n.camera
    for r,v in expected.items():u.reg_write(r,v)
    other={UC_X86_REG_XMM0+i:(1<<127)+0x123400+i for i in range(16)}
    for r,v in other.items():u.reg_write(r,v)
    sp=n.stack+0x1ff008;u.mem_write(sp,struct.pack('<Q',n.stop));u.reg_write(UC_X86_REG_RSP,sp)
    u.emu_start(base+entry,n.stop,count=1000);require(all(u.reg_read(r)==v for r,v in expected.items()),'Leaf clobbered aGPR')
    require(u.reg_read(UC_X86_REG_RSP)==sp+8,'Leaf changed caller stack');require(all(u.reg_read(r)==v for r,v in other.items()if r!=UC_X86_REG_XMM0),'Leaf clobbered anotherXMM')
    scalar=1./5200. if dimensions==(2048,2048)else 1./2600.;require(u.reg_read(UC_X86_REG_XMM0)==int.from_bytes(struct.pack('<f',scalar),'little'),'Leaf scalar/upperXMM0 differs from original MOVSS semantics')
    leaf_cases.append(dict(base=hex(base),entry=hex(entry),dimensions=dimensions,all_GPRs_and_other_XMMs_preserved=True,stack_return_exact=True))
 report=dict(passed=True,scope=__doc__,source_sha256=sha(source),candidate_sha256=sha(candidate),patch_source_sha256=sha((HERE/'frame_depth_patch.py').read_bytes()),test_source_sha256=sha(Path(__file__).read_bytes()),
  native_whole_camera_and_actual_state4_prefix_cases=len(rows),legacy_null_and_rectangular_exact_output_cases=legacy,huge_exact_half_depth_only_cases=huge,native_leaf_register_cases=len(leaf_cases),
  all_256_actual_native_height_values_tested=True,height_observation_sha256=sha(live_path.read_bytes()),huge_full_world_depth_bounds=[global_min,global_max],
  fixed_cached_draw_bias_preserved=True,screenXY_camera_pan_orientation_zoom_viewport_unchanged=True,all_supported_legacy_outputs_exact_bytes_equal=True,
  cases=rows,leaf_cases=leaf_cases,actual_game_runs=0,game_or_input_files_modified=False)
 out=HERE/'frame_depth_native_results.json';require(not out.exists(),'Preserve prior proof');out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(passed=True,camera_cases=len(rows),legacy_exact=legacy,huge=huge,leaf=len(leaf_cases),huge_depth_bounds=report['huge_full_world_depth_bounds'])))


if __name__=='__main__':main()
