"""Stage presentation-only visibility for the optional native companion."""

from pathlib import Path

from .world_options import PRIVATE, replace
from .world_runtime_build import AI_LOADER


VISIBILITY_EXPORT = "WorldSettingsEnableMultiplayerVisibility"
DISABLE_VISIBILITY_EXPORT = "WorldSettingsDisableMultiplayerVisibility"
VISIBILITY_VIEW_EXPORT = "WorldSettingsMultiplayerVisibilityView"
VISIBILITY_RELOAD_EXPORT = "WorldSettingsMultiplayerFinishReload"
VISIBILITY_ACTIVITY_EXPORTS = {"WorldSettingsVisibilityProjectActivityTiles", "WorldSettingsVisibilityActivityMinimapProperty"}
PEACEFUL_AI_EXPORT = "WorldSettingsMultiplayerPeacefulDiplomacy"
_NATIVE = Path(__file__).with_name("native") / "world_settings_multiplayer"


def apply_multiplayer_visibility(files, *, frame_sha256, display_sha256, scene_sha256=None, world_sha256=None,
                                 peaceful_ai=False):
    """Embed the exact staged module identities and add the multiplayer draw hooks."""
    pins = {"Frame": frame_sha256, "Display": display_sha256}
    if scene_sha256 is not None:
        pins["Scene"] = scene_sha256
    if world_sha256 is not None:
        pins["World"] = world_sha256
    hashes = []
    for module, value in pins.items():
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"The multiplayer {module} pin must be a lowercase SHA-256 digest.")
        encoded = ",".join(f"0x{byte:02x}" for byte in bytes.fromhex(value))
        hashes.append(f"static const unsigned char wsMp{module}Sha[32]={{{encoded}}};\n")
    if scene_sha256 is not None:
        hashes.append("#define WS_MP_HAS_SCENE_PIN 1\n")
    if world_sha256 is not None:
        hashes.append("#define WS_MP_HAS_WORLD_PIN 1\n")
    if peaceful_ai:
        hashes.append("#define WS_MP_PEACEFUL_AI 1\n")

    menu = PRIVATE + "WorldSettings.c"
    files[menu] = b"#define WS_MULTIPLAYER_VISIBILITY 1\n" + files[menu]
    runtime = PRIVATE + "start_visibility_runtime.inc"
    files[runtime] = replace(files[runtime], b" int32_t map,enemy;int marked;",
        b" int32_t map,enemy;int marked;\n"
        b" void*multiplayerPlayer;uint32_t multiplayerGeneration;int multiplayerWithheld;",
        "companion display view fields")
    files[runtime] = replace(files[runtime], b"static int wsVisibilityWorldRead(void*world,WSVisibilityWorld*out){",
        b'#include "visibility_view.inc"\nstatic int wsVisibilityWorldRead(void*world,WSVisibilityWorld*out){',
        "companion local view binding")
    files[runtime] = replace(files[runtime], b" v.marked=wsVisibilityDecode(v.flags,&v.map,&v.enemy);",
        b" v.marked=wsVisibilityDecode(v.flags,&v.map,&v.enemy);\n"
        b" wsMultiplayerBindVisibility(&v);", "companion display-only policy")
    files[runtime] = replace(files[runtime], b"static int wsVisibilityHasPolicy(void*world){",
        b'#include "visibility_reveal_activity.inc"\nstatic int wsVisibilityHasPolicy(void*world){',
        "project current activity only in the native display paths")
    files[runtime] = replace(files[runtime],
        b"  wsCertRead((unsigned char*)world+0x6eec,&flags,4)&&(flags&WS_VISIBILITY_POLICY_MASK)!=0;",
        b"  (wsMultiplayerWorldWithheld(world)||\n"
        b"   (wsCertRead((unsigned char*)world+0x6eec,&flags,4)&&(flags&WS_VISIBILITY_POLICY_MASK)!=0));",
        "withhold typed multiplayer World draws when native fields cannot be read")
    files[runtime] = replace(files[runtime],
        b" if(!wsVisibilityWorldRead(world,&v))return wsVisibilityHasPolicy(world)?-1:0;\n if(!v.marked)return 0;",
        b" if(!wsVisibilityWorldRead(world,&v))return (wsVisibilityHasPolicy(world)||wsMultiplayerUsesRenderer(renderer))?-1:0;\n"
        b" wsMultiplayerRememberRenderer(&v,renderer);\n"
        b" if(wsMultiplayerWithholdsRenderTarget(&v,renderer))return -1;\n if(!v.marked)return 0;",
        "withhold native draw while the scoped multiplayer renderer or World is unresolved")
    files[runtime] = replace(files[runtime], b" if(!picking&&!WorldSettingsVisibilityWorldLoaded(world,0,0))return -1;",
        b" if(!v.multiplayerPlayer&&!picking&&!WorldSettingsVisibilityWorldLoaded(world,0,0))return -1;",
        "skip single-player World writes in multiplayer draw")
    files[runtime] = replace(files[runtime], b" if(!WorldSettingsVisibilityWorldLoaded(world,0,0))return 0;",
        b" if(!v.multiplayerPlayer&&!WorldSettingsVisibilityWorldLoaded(world,0,0))return 0;",
        "skip single-player World writes in multiplayer minimap")
    files[runtime] = replace(files[runtime],
        b" if(!wsVisibilityWorldRead(world,&v))return wsVisibilityHasPolicy(world)?0:WS_VISIBILITY_NATIVE_MAP(w)(map,flags,rect);",
        b" int worldReady=wsVisibilityWorldRead(world,&v);\n"
        b" if((worldReady&&v.multiplayerWithheld)||(!worldReady&&wsMultiplayerWorldWithheld(world))){\n"
        b"  WSVisibilityWorld pending={.world=world,.module=w};WSVisibilityMapView bitmap;\n"
        b"  if(wsVisibilityMapRead(map,&pending,&bitmap))wsVisibilityClearMap(&bitmap);\n"
        b"  InterlockedIncrement(&wsVisibilityMapGeneration);return 0;\n"
        b" }\n"
        b" if(!worldReady)return wsVisibilityHasPolicy(world)?0:WS_VISIBILITY_NATIVE_MAP(w)(map,flags,rect);",
        "clear the selected world's minimap while its view is withheld")
    files[runtime] = replace(files[runtime],
        b" if(v.map!=0&&v.enemy!=0)return WS_VISIBILITY_NATIVE_MAP(w)(map,flags,rect);",
        b" if(v.map!=0&&v.enemy!=0&&!v.multiplayerPlayer)return WS_VISIBILITY_NATIVE_MAP(w)(map,flags,rect);",
        "recover the multiplayer minimap after a withheld revealed view")
    files[runtime] = replace(files[runtime], b" if(v.map==0||!v.enemy){",
        b" if(v.map==0||!v.enemy||v.multiplayerPlayer){",
        "commit the verified revealed multiplayer bitmap to the refresh memo")
    files[runtime] = replace(files[runtime], b" if(!wsVisibilityMaskMapView(&after,context)){",
        b" if((v.map==0||!v.enemy)&&!wsVisibilityMaskMapView(&after,context)){",
        "keep a fully visible bitmap on the native colour path")
    files[runtime] = replace(files[runtime], b" if(context->view.map!=0&&context->view.enemy!=0)return 1;",
        b" if(context->view.map!=0&&context->view.enemy!=0&&!context->view.multiplayerPlayer)return 1;",
        "recover a revealed multiplayer bitmap on the next protected draw")
    files[runtime] = replace(files[runtime],
        b"  if(view.marked<0||!WorldSettingsVisibilityWorldLoaded(world,0,0)||!wsVisibilityContextRead(&view,&local))return 0;",
        b"  if(view.marked<0||(!view.multiplayerPlayer&&!WorldSettingsVisibilityWorldLoaded(world,0,0))||"
        b"!wsVisibilityContextRead(&view,&local))return 0;",
        "skip single-player World writes in detached multiplayer draw")
    files[runtime] = replace(files[runtime], b" if(v.marked<0)goto invalid;\n if(!wsMineralPersistenceWritable(v.world+0x6ee9,1))",
        b" if(v.marked<0)goto invalid;\n if(v.multiplayerPlayer)return 1;\n if(!wsMineralPersistenceWritable(v.world+0x6ee9,1))",
        "exclude multiplayer from native discovery mutation")
    files[runtime] = replace(files[runtime],
        b"   if(!wsVisibilityChartPoint(v,(float)qx+4.0f,(float)qy+4.0f))result|=(unsigned char)(1u<<q);",
        b"   if(v->multiplayerPlayer?!(island->discovered&(1u<<v->viewer)):\n"
        b"      !wsVisibilityChartPoint(v,(float)qx+4.0f,(float)qy+4.0f))result|=(unsigned char)(1u<<q);",
        "project multiplayer native discovery in borrowed terrain rows")
    files[runtime] = replace(files[runtime], b"if(!wsVisibilityRestore()||!chart)wsVisibilityRenderMemo.valid=0;",
        b"int restored=wsVisibilityRestore();if(!restored||!chart)wsVisibilityRenderMemo.valid=0;"
        b"else wsMultiplayerVisibilityDrawn(wsVisibilityDrawContext);", "publish only completed native draw views")
    files[runtime] = replace(files[runtime],
        b"static void*wsVisibilityUnknownActorTarget(void*actor,unsigned char*module,uint32_t slot){",
        b"static void*wsVisibilityUnknownActorTarget(void*actor,unsigned char*module,uint32_t slot,void*renderer){\n"
        b" if(wsMultiplayerUnknownActorWithheld(renderer))return 0;",
        "suppress unidentified native World actors while binding is pending")
    for signature, count in ((b"0x100", 2), (b"0x108", 1)):
        anchor = b"wsVisibilityUnknownActorTarget(actor,module," + signature + b")"
        files[runtime] = replace(files[runtime], anchor, anchor[:-1] + b",renderer)",
                                 "pass renderer identity to unknown World actors", count=count)
    files[runtime] = replace(files[runtime],
        b" int marked=wsVisibilityDrawContext&&wsVisibilityDrawContext->view.marked;\n int known=",
        b" int marked=wsVisibilityDrawContext&&wsVisibilityDrawContext->view.marked;\n"
        b" if(marked&&wsVisibilityDrawContext->view.multiplayerPlayer&&!wsVisibilityFastRenderer(wsVisibilityDrawContext,renderer))return 0;\n"
        b" int known=", "refuse a sprite targeting another renderer during a protected draw")
    vision = PRIVATE + "start_visibility_vision.inc"
    files[vision] = replace(files[vision], b" c->human=(unsigned char*)wsCertPointer(table,8);",
        b" c->human=c->view.multiplayerPlayer?(unsigned char*)c->view.multiplayerPlayer:\n"
        b"          (unsigned char*)wsCertPointer(table,8);", "read local seat's observer lists")
    files[vision] = replace(files[vision], b"    !wsCertRead(c->human+8,&id,4)||id)return 0;",
        b"    !wsCertRead(c->human+8,&id,4)||id!=(c->view.multiplayerPlayer?c->view.viewer:0u))return 0;",
        "verify observer owner identity per mode")
    files[vision] = replace(files[vision],
        b"static int wsVisibilityOwnedBuilding(const WSVisibilityDrawContext*,const WSVisibilityIsland*,float,float,void**);",
        b"static int wsVisibilityMultiplayerIslandKnown(const WSVisibilityDrawContext*c,float x,float z){\n"
        b" if(!c->view.multiplayerPlayer)return 1;\n"
        b" const WSVisibilityIsland*island=wsVisibilityIslandAt(c,x,z);\n"
        b" return !island||(island->discovered&(1u<<c->view.viewer));\n"
        b"}\nstatic int wsVisibilityOwnedBuilding(const WSVisibilityDrawContext*,const WSVisibilityIsland*,float,float,void**);",
        "share the local native discovery projection across draw surfaces")
    files[vision] = replace(files[vision], b" if(c->view.map==0&&!wsVisibilityChartPoint(&c->view,x,z))return 0;",
        b" if(c->view.map==0&&(!wsVisibilityMultiplayerIslandKnown(c,x,z)||!wsVisibilityChartPoint(&c->view,x,z)))return 0;",
        "honor the local island bit in actor submissions")
    files[vision] = replace(files[vision], b" if(c->view.map==0&&!wsVisibilityChartPoint(&c->view,xyz[0],xyz[2]))return 0;",
        b" if(c->view.map==0&&(!wsVisibilityMultiplayerIslandKnown(c,xyz[0],xyz[2])||"
        b"!wsVisibilityChartPoint(&c->view,xyz[0],xyz[2])))return 0;", "honor the local island bit in sprite submissions")

    chart = PRIVATE + "start_visibility_chart.inc"
    files[chart] = replace(files[chart], b"static uintptr_t wsChartWorldBinding,wsChartFreshBinding;",
        b"static uintptr_t wsChartWorldBinding,wsChartFreshBinding;\nstatic uint32_t wsChartMultiplayerGeneration;",
        "chart identity includes activation generation")
    files[chart] = replace(files[chart],
        b" if(wsChartActive.bits)return wsChartWorldBinding==(uintptr_t)v->world&&wsChartCoreIdentity",
        b" if(wsChartMultiplayerGeneration!=v->multiplayerGeneration){\n"
        b"  wsChartCoreFree(&wsChartActive);wsChartWorldBinding=0;\n"
        b"  wsChartMultiplayerGeneration=v->multiplayerGeneration;wsVisibilityChartTransientReset();\n"
        b" }\n"
        b" if(wsChartActive.bits)return wsChartWorldBinding==(uintptr_t)v->world&&wsChartCoreIdentity",
        "never reuse exploration across different activations")
    files[chart] = replace(files[chart],
        b" if(picking||mode==4u||mode==5u)return 1;\n perf=wsVisibilityPerformanceBegin();int observed=wsChartObserve(c,time);",
        b" if(picking||mode==4u||mode==5u)return 1;\n"
        b" if(c->view.multiplayerPlayer){\n"
        b"  if(wsVisibilityChartMarkContext(c))return 1;\n"
        b"  wsVisibilityChartReadEnd(&c->chart);return 0;\n"
        b" }\n perf=wsVisibilityPerformanceBegin();int observed=wsChartObserve(c,time);",
        "avoid borrowing memory-bearing terrain and ghost copies in multiplayer")
    files[chart] = replace(files[chart],
        b" int result=wsChartWorldBinding?wsChartCoreEncode",
        b" if(wsChartMultiplayerGeneration){wsChartGive();return wsChError(error,cap,\"Multiplayer exploration is local to the renderer.\");}\n"
        b" int result=wsChartWorldBinding?wsChartCoreEncode", "refuse to serialize the multiplayer chart")
    files[chart] = replace(files[chart],
        b"  if(c->view.map==0&&!wsVisibilityChartPoint(&c->view,wx,wz)){*pixel=0x90u;continue;}",
        b"  if(c->view.map==0&&(!wsVisibilityMultiplayerIslandKnown(c,wx,wz)||"
        b"!wsVisibilityChartPoint(&c->view,wx,wz))){*pixel=0x90u;continue;}",
        "honor the local island bit in the minimap")

    refresh = PRIVATE + "start_visibility_map_refresh.inc"
    files[refresh] = replace(files[refresh],
        b"out[3]=(int32_t)v->height;*flags|=2u;}",
        b"out[3]=(int32_t)v->height;*flags|=v->multiplayerPlayer&&v->enemy?3u:2u;}",
        "restore both native colour nibbles after withholding the revealed bitmap")
    files[refresh] = replace(files[refresh],
        b"  const WSChartCore*chart=wsVisibilityChartReadSnapshot(v);if(!chart||chart->bitBytes>sizeof wsVisibilityMapMemo.chartBits)return 0;",
        b"  if(v->multiplayerPlayer)for(uint32_t id=0;id<WS_VISIBILITY_ISLAND_LIMIT;id++)if(c->present[id]){\n"
        b"   const WSVisibilityIsland*island=&c->islands[id];\n"
        b"   int known=!!(island->discovered&(1u<<v->viewer));\n"
        b"   if((!matching&&known)||(matching&&known!=wsVisibilityMapMemo.islands[id].known)){\n"
        b"    wsVisibilityUnionRect(out,island->x,island->y,island->x+island->width,island->y+island->height);*flags|=3u;\n"
        b"   }\n"
        b"  }\n"
        b"  const WSChartCore*chart=wsVisibilityChartReadSnapshot(v);if(!chart||chart->bitBytes>sizeof wsVisibilityMapMemo.chartBits)return 0;",
        "refresh minimap bounds when the local player's native discovery changes")

    exploration = PRIVATE + "start_visibility_exploration.inc"
    files[exploration] = replace(files[exploration], b"/* 0 invalid; 1 positive native surface; 2 legacy/non-Terra delegation.",
        b"/* 0 invalid; 1 positive native surface; 2 native delegation; 3 withheld surface.",
        "document the withheld final viewport status")
    files[exploration] = replace(files[exploration],
        b" if(!wsVisibilityWorldRead(world,&s.view))return 0;\n if(s.view.marked<0)return 0;\n"
        b" if(!s.view.marked||s.view.map!=0){*out=s;return 2;}",
        b" int worldReady=wsVisibilityWorldRead(world,&s.view);\n"
        b" if(!worldReady){\n"
        b"  s.view.world=world;s.view.multiplayerWithheld=wsVisibilityHasPolicy(world)&&wsMultiplayerWorldWithheld(world);\n"
        b" }\n"
        b" int withheld=wsMultiplayerWithholdsRenderTarget(&s.view,renderer);\n"
        b" if(!withheld&&(!worldReady||s.view.marked<0))return 0;\n"
        b" if(!withheld&&(!s.view.marked||s.view.map!=0)){*out=s;return 2;}\n"
        b" s.view.multiplayerWithheld=withheld;",
        "certify native mode-2 surface even while the view is withheld")
    files[exploration] = replace(files[exploration],
        b" *out=s;return 1;\n}", b" *out=s;return withheld?3:1;\n}",
        "distinguish a withheld surface from a charted surface")
    files[exploration] = replace(files[exploration],
        b" return wsVisibilityExplorationSurfaceRead(s->renderer,s->context,&n)==1&&!n.empty&&",
        b" return wsVisibilityExplorationSurfaceRead(s->renderer,s->context,&n)==(s->view.multiplayerWithheld?3:1)&&!n.empty&&",
        "recheck current surface ownership before blacking withheld frames")
    files[exploration] = replace(files[exploration], b" if(!status)return 0;if(status==2||surface.empty)return 1;",
        b" if(!status)return 0;if(status==2||surface.empty)return 1;\n"
        b" if(status==3){\n"
        b"  if(!wsVisibilityExplorationSurfaceSame(&surface))return 0;\n"
        b"  wsVisibilityExplorationBlack(&surface);return 1;\n"
        b" }", "black the selected viewport after the native worker flush")

    files[PRIVATE + "visibility_view.inc"] = (_NATIVE / "visibility_view.inc").read_bytes()
    files[PRIVATE + "visibility_reveal_activity.inc"] = (_NATIVE / "visibility_reveal_activity.inc").read_bytes()
    if peaceful_ai:
        files[runtime] += b'\n#include "peaceful_ai.inc"\n'
        files[PRIVATE + "peaceful_ai.inc"] = (_NATIVE / "peaceful_ai.inc").read_bytes()
    loader_source = AI_LOADER.rsplit("/", 1)[0] + "/install_test_hooks.c"
    loader_folder = loader_source.rsplit("/", 1)[0] + "/"
    files[loader_folder + "visibility_multiplayer_install.inc"] = (
        "".join(hashes).encode("ascii") + (_NATIVE / "visibility_multiplayer_install.inc").read_bytes()
    )
    files[loader_source] = files[loader_source] + b'\n#include "visibility_multiplayer_install.inc"\n'
