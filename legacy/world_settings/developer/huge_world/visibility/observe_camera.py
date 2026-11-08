"""Read-only camera/World backlink observation. No remote calls, writes or UI."""
from pathlib import Path
import argparse,ctypes as C,hashlib,importlib.util,json,math,struct,sys,time
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;GAME=HERE.parents[3]
path=GAME/'WorldSettings_Work/huge_engine_work/navigation/observe_live_grids.py'
spec=importlib.util.spec_from_file_location('border_readonly_process_api',path);N=importlib.util.module_from_spec(spec);sys.modules[spec.name]=N;spec.loader.exec_module(N)


def sha(data):return hashlib.sha256(data).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--pid',type=int,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    output=a.output.resolve();N.require(output.is_relative_to(HERE)and not output.exists(),'Expected new report under border folder')
    o=N.Observer(a.pid)
    try:
        identity=o.identity();mods=o.modules(a.pid);frame=mods['annoframe.dll'];welt=mods['annowelt.dll']
        worlds,world_scan=o.find_worlds(welt['base'],8*1024**3);N.require(len(worlds)==1,'Expected one World')
        world=worlds[0];dimensions=struct.unpack('<II',o.read(world+0x1d8,8))
        camera_vt=frame['base']+0xa0c98;pattern=struct.pack('<Q',camera_vt)
        info=N.SystemInfo();o.system(C.byref(info));at=int(info.minimum);last=int(info.maximum);candidates=set();read_bytes=0
        while at<last:
            r=o.region(at);start=int(r.BaseAddress or 0);end=start+r.RegionSize;N.require(end>at,'Virtual query did not progress')
            if r.State==0x1000 and r.Type==0x20000 and not(r.Protect&0x100)and(r.Protect&255)in[4,8,0x40,0x80]:
                for part in range(start,end,65536):
                    amount=min(65536,end-part);read_bytes+=amount;N.require(read_bytes<=8*1024**3,'Private memory scan budget exceeded')
                    try:buf=o.read(part,amount)
                    except OSError:continue
                    p=buf.find(pattern)
                    while p>=0:
                        obj=part+p
                        if obj%8==0 and o.readable(obj,0xc0340,True):candidates.add(obj)
                        p=buf.find(pattern,p+1)
            at=end
        cameras=[]
        for obj in sorted(candidates):
            prefix=o.read(obj,0x30);linked=struct.unpack_from('<Q',prefix,0x18)[0]
            values=o.read(obj+0xc0300,0x40);target=struct.unpack_from('<3f',values,0x20);previous=struct.unpack_from('<3f',values,0x10)
            cameras.append(dict(object_fingerprint=sha(struct.pack('<Q',obj)),native_vtable_rva='0xa0c98',world_backlink_matches_exact_live_World=linked==world,
                linked_world_dimensions=list(struct.unpack('<II',o.read(linked+0x1d8,8)))if linked and o.readable(linked+0x1d8,8)else None,
                camera_target_xyz=list(target),previous_camera_xyz=list(previous),orientation=values[8],scale=struct.unpack_from('<f',values,12)[0],
                projection_axis_floats=list(struct.unpack_from('<4f',values,0x2c)),
                beyond_old1024_x=target[0]<-1024,beyond_old1024_y=target[2]<-1024,
                requested_world_bounds_hold=all(math.isfinite(v)for v in target)and -dimensions[0]<=target[0]<=0 and -dimensions[1]<=target[2]<=0,
                stable_camera_target_during_read=o.read(obj+0xc0320,12)==values[0x20:0x2c],
                native_record_count_fields=list(struct.unpack('<II',o.read(obj+0xc0030,8)))))
        N.require(o.identity()==identity,'Process changed during observation')
    finally:o.close(o.handle)
    report=dict(scope=__doc__,pid=a.pid,process_creation_time=identity[1],world_dimensions=list(dimensions),world_scan=world_scan,
        camera_scan_private_bytes=read_bytes,camera_candidates=len(cameras),cameras=cameras,
        game_or_memory_modified=False,UI_or_native_method_called=False,source_sha256=sha(Path(__file__).read_bytes()))
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
