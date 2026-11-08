from pathlib import Path
import sys,re,struct,json
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1];ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'))
from scene_catalogue import chunks,read_container,island_chunks

def fields(buf):
    out=[];at=0
    while at<len(buf):
        assert len(buf)-at>=8
        name=buf[at:at+6].rstrip(b'\0').decode('ascii');n=struct.unpack_from('<H',buf,at+6)[0];h=8
        if n>=0xff00:h=10;n=(n&255)<<16|struct.unpack_from('<H',buf,at+8)[0]
        assert n<=len(buf)-at-h,(at,name,n,len(buf))
        value=buf[at+h:at+h+n];out.append((name,value));at+=h+n
    return out
p=ROOT/'Languages/Nl/Scenes/0010SingleEndlos/03_1024_med_256.sze'
b=p.read_bytes()
for c in chunks(b,32,len(b)):
 if c.tag=='SPIELER':
  print('PLAYER',struct.unpack_from('<II',c.payload),c.length)
  for key,val in fields(c.payload[8:]):print(key,len(val),repr(val[:240]))
for c in chunks(b,32,len(b)):
 if c.tag!='SPIELER': print(c.tag,c.length,repr(c.payload[:100]))
print('template pirates:')
p=ROOT/'Scenes/Islands/Nord/N_064x064_0009_0B_Pirat.scp'
d=p.read_bytes();r,t=read_container(d)
for c in chunks(d,16,r.end):
 print(c.tag,c.length)
 if c.tag=='SPIELER':
  print('ID',struct.unpack_from('<II',c.payload));print([(k,repr(v[:130])) for k,v in fields(c.payload[8:])])
 if c.tag=='INSEL5':
  g,parts=island_chunks(c);print('geom',g)
  for q in parts:
   if q.tag not in ['HEIGHT','FRUCHTBAR','FELD','BODEN','OBJECTS','ANBAU']:print(q.tag,q.length,repr(q.payload[:70]))
print(next(c.payload.decode('cp1252') for c in chunks(b,32,len(b)) if c.tag=='BIGBROTHER'))
