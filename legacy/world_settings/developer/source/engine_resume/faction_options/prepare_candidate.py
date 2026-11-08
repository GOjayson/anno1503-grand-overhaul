"""Build a private, copy-only faction planner candidate from the frozen backend.

No installed, canonical runtime, package or game-copy files are modified.
"""
from pathlib import Path
import hashlib,json,re,shutil,struct,sys
HERE=Path(__file__).resolve().parent; WORK=HERE.parents[1]; ROOT=WORK.parent
sys.path.insert(0,str(WORK/'world_data'))
from scene_catalogue import chunks,read_container,island_chunks
OUT=HERE/'runtime'; OUT.mkdir(exist_ok=True)
def replace(text,old,new):
 assert text.count(old)==1,(old[:100],text.count(old))
 return text.replace(old,new)
cat=json.loads((WORK/'world_data/catalogue.json').read_text())
factions=[]; choices=[]; pirates=[]
for i,t in enumerate(cat['templates']):
 b=(ROOT/t['path']).read_bytes(); assert hashlib.sha256(b).hexdigest()==t['sha256']
 names=[]
 for m in re.finditer(b'VOLK\0\0',b):
  n=struct.unpack_from('<H',b,m.start()+6)[0]; v=b[m.start()+8:m.start()+8+n]
  assert len(v)==n and v.endswith(b'\0') and b'\0' not in v[:-1];names.append(v[:-1].decode())
 special=set(names)-set(cat['cultures'])-{'SPIELER'}
 assert not special or special=={'PIRATEN'}
 factions.append(int(bool(special))); choices.append(0)
 if special:
  assert names.count('PIRATEN')==1 and t['climate_index']==2
  root,trailer=read_container(b);assert len(trailer)==t['trailer_length']
  ps=[c for c in chunks(b,16,root.end) if c.tag=='SPIELER' and b'PIRATEN\0' in c.payload]
  assert len(ps)==1 and b'STADT2' in ps[0].payload
  pirates.append(dict(index=i,path=t['path'],width=t['width'],height=t['height'],sha256=t['sha256']))
assert len(pirates)==15
widths={p['width'] for p in pirates};assert widths=={64,128,256}
for p in pirates:choices[p['index']]=int(p['width']==min(widths))|(int(p['width']==128)<<1)|(int(p['width']==max(widths))<<2)
(OUT/'world_factions.h').write_text('/* Fingerprint-bound metadata; see faction_options/audit_results.json. */\nstatic const unsigned char wsTemplateFactions[]={'+','.join(map(str,factions))+'};\nstatic const unsigned char wsTemplateFactionSizes[]={'+','.join(map(str,choices))+'};\n','ascii')
for name in ['world_catalogue.h','world_ship_reserves.h']:
 shutil.copyfile(WORK/'engine_resume/runtime'/name,OUT/name)
h=(WORK/'engine_resume/runtime/world_backend.h').read_text()
h=replace(h,'uint32_t cultures;','uint32_t cultures,factions;')
(OUT/'world_backend.h').write_text(h)
c=(WORK/'engine_resume/runtime/world_backend.c').read_text()
c=replace(c,'#include "world_ship_reserves.h"','#include "world_ship_reserves.h"\n#include "world_factions.h"')
c=replace(c,'static uint32_t planCount,planSpacing,rngState,sceneSequence;','static uint32_t planCount,planSpacing,rngState,sceneSequence,planFactions;')
c=replace(c,'static int wsEligible(const WSTemplate*t,const WSWorldSettings*s){return !t->excludedNative&&wsSize(t,s->islandSize)&&!(t->cultures&~s->cultures)&&(t->fertileLand>0||t->climate==0);}', '''static uint32_t wsTemplateFaction(const WSTemplate*t){return wsTemplateFactions[t-wsTemplates];}
static int wsEligible(const WSTemplate*t,const WSWorldSettings*s){uint32_t f=wsTemplateFaction(t);int size=f?(s->islandSize==3||(wsTemplateFactionSizes[t-wsTemplates]&(1u<<s->islandSize))):wsSize(t,s->islandSize);return (!t->excludedNative||f)&&!(f&~s->factions)&&size&&!(t->cultures&~s->cultures)&&(t->fertileLand>0||t->climate==0);}''')
c=replace(c,'int ore,int whale,int empty){','int ore,int whale,int empty,int faction){')
c=replace(c,'if(!wsEligible(t,s))continue;','if(!wsEligible(t,s)||wsTemplateFaction(t)!=(uint32_t)faction)continue;')
c=c.replace('wsChoose(s,1u<<c,-1,0,0,0)','wsChoose(s,1u<<c,-1,0,0,0,0)').replace('wsChoose(s,0,c,0,0,1)','wsChoose(s,0,c,0,0,1,0)').replace('wsChoose(s,0,-1,(int)need[r],0,1)','wsChoose(s,0,-1,(int)need[r],0,1,0)').replace('wsChoose(s,0,-1,0,1,1)','wsChoose(s,0,-1,0,1,1,0)').replace('wsChoose(s,0,-1,0,0,1)','wsChoose(s,0,-1,0,0,1,0)')
c=replace(c,'s->aiCount||s->cultures&~255u','s->aiCount||s->cultures&~255u||s->factions&~3u')
c=replace(c,'planSpacing=(uint32_t)s->spacing;','planSpacing=(uint32_t)s->spacing;planFactions=s->factions;')
c=replace(c,'for(uint32_t i=0;i<n;i++)climates|=1u<<planned[i].climate;','''if(s->factions&1u){int pick=wsChoose(s,0,-1,0,0,0,1);if(pick<0||!wsAdd((uint32_t)pick,&n)){wsMessage(error,cap,"No pirate island matches this size.");return 0;}}
  for(uint32_t i=0;i<n;i++)climates|=1u<<planned[i].climate;''')
c=replace(c,'uint32_t climates=0,cultures=0,crops=0,minerals=0,whales=0;','uint32_t climates=0,cultures=0,crops=0,minerals=0,whales=0,pirates=0;')
c=replace(c,'climates|=1u<<p->climate;cultures|=p->cultures;','pirates+=wsTemplateFaction(t)==1;climates|=1u<<p->climate;cultures|=p->cultures;')
c=replace(c,'if(climates!=63||cultures!=s->cultures','if(pirates!=((s->factions&1u)!=0)||climates!=63||cultures!=s->cultures')
c=replace(c,'node[0x15c]=(unsigned char)(p->cultures!=0);','node[0x15c]=(unsigned char)(p->cultures!=0||wsTemplateFaction(&wsTemplates[p->templateIndex])!=0);')
# The strict helper validates stock basic/state identities before any output.
c=replace(c,'static int wsBuildSZE(const WSWorldSettings*s,WSBuffer*b,char*error,uint32_t cap){','#include "special_scene.inc"\nstatic int wsBuildSZE(const WSWorldSettings*s,WSBuffer*b,char*error,uint32_t cap){')
c=replace(c,'if(!wsAppend(b,src,32))return 0;int links=0,head=0,ores=0,crops=0,treasure=0;','unsigned char special[32]={0};if(!wsSpecialPlayers(src,size,special,error,cap))return 0;\n if(!wsAppend(b,src,32))return 0;int links=0,head=0,ores=0,crops=0,treasure=0;')
c=replace(c,'if(wsTag(src+at,"INSELLNK")||wsTag(src+at,"INSEL5")){','if(wsTag(src+at,"SPIELER")&&n>=8&&wsU32(src+at+20)<32&&special[wsU32(src+at+20)]&&!(s->factions&special[wsU32(src+at+20)])){}\n  else if(wsTag(src+at,"BIGBROTHER")){if(!wsSpecialScript(b,src+at+16,n,s->factions,special,error,cap))return 0;}\n  else if(wsTag(src+at,"INSELLNK")||wsTag(src+at,"INSEL5")){')
(OUT/'world_backend.c').write_text(c)
v=(WORK/'engine_resume/runtime/validated_world.inc').read_text()
v=replace(v,'uint32_t islandCultures=0;','uint32_t islandCultures=0,islandFactions=0;')
v=replace(v,'if(type!=14)WS_CERT_FAIL("A template settlement was not transferred to a native player.");','if(type==15&&nativeCulture==11){islandFactions|=1;continue;}\n   if(type!=14)WS_CERT_FAIL("A template settlement was not transferred to an enabled native player.");')
v=replace(v,'if(islandCultures!=p->cultures)','if(islandFactions!=wsTemplateFaction(&wsTemplates[p->templateIndex]))WS_CERT_FAIL("Loaded pirate settlement ownership differs from the selected island.");\n  if(islandCultures!=p->cultures)')
v=replace(v,'if(!wsCertShips(world,error,cap))return 0;','if(!wsCertSpecialPlayers(world,error,cap))return 0;\n if(!wsCertShips(world,error,cap))return 0;')
v=replace(v,'static int wsLoadedCertificate(void*scene,char*error,uint32_t cap){','#include "special_certificate.inc"\nstatic int wsLoadedCertificate(void*scene,char*error,uint32_t cap){')
(OUT/'validated_world.inc').write_text(v)
for name in ['special_scene.inc','special_certificate.inc']:
 shutil.copyfile(HERE/name,OUT/name)
result=dict(scope=__doc__,abi_bytes=32,factions={'pirates':1,'venetians':2},pirate_templates=pirates,pirate_size_widths={'small':64,'medium':128,'large':256},source_sha256={n:hashlib.sha256((WORK/'engine_resume/runtime'/n).read_bytes()).hexdigest() for n in ['world_backend.c','world_backend.h','validated_world.inc','world_catalogue.h','world_ship_reserves.h']})
(HERE/'candidate_sources.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'private_candidate':str(OUT),'pirate_templates':len(pirates),'settings_abi':32}))
