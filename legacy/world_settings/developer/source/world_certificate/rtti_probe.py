from pathlib import Path
import sys,struct
sys.path.insert(0,str(Path('WorldSettings_Work/engine_audit').resolve()))
from audit import Module
for name in ['AnnoWelt.dll','AnnoGame.dll']:
 m=Module(name)
 for sec in m.pe.sections:
  if sec.Characteristics &0x20000000: continue
  for off in range(sec.VirtualAddress+8,sec.VirtualAddress+sec.Misc_VirtualSize-8,8):
   col=struct.unpack_from('<Q',m.image,off-8)[0]-m.base
   if not 0<=col<len(m.image)-24: continue
   sig,offset,cd,ty,cl,self=struct.unpack_from('<6I',m.image,col)
   if sig!=1 or self!=col or not 0<=ty<len(m.image)-32: continue
   n=m.image[ty+16:ty+200].split(b'\0')[0].decode('ascii',errors='replace')
   if any(x.lower() in n.lower() for x in ['vork','schiff','spieler','kultur','insel','figur','erz','rohstoff','orkomm','native','liste','stadt','occur','welt','bewohner' ]):
    print(name,hex(off),offset,n)
