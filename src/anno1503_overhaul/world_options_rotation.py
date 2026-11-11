"""Stage real island rotation without modifying original game or legacy inputs."""
import hashlib

from .world_options import PRIVATE, authored, replace
from .world_runtime_build import PE, RuntimeBuildError


ROTATION_NATIVE_FUNCTIONS = (
    (0xc5d30, 0xc66df, 'c098cfa45e5a01b049fa577282adeb0161e869370dde5f3b3f89c1bfe07dee36'),
    (0x453b0, 0x455c6, '5c673b9e9b74c3cd7383b8c13f175d541b3e38e828ab375fd229f9f7de63575d'),
    (0x368e0, 0x36b3a, 'eb176031a169be9c4acfcc1db9307b1d866fd94d5bdbf3b3f356f818f329a0c4'),
)


def verify_rotation_native_image(raw: bytes, expected: str):
    """Authenticate the HE mesh, height and mine readers used by the codec.

    This is provenance for existing native formats, not an engine edit or a
    claim that instruction fixtures replace checking a rendered game world.
    """
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeBuildError('Unknown native island rotation input.')
    pe = PE(raw)
    functions = {(a, b) for a, b, _ in pe.function_table()}
    for start, end, pin in ROTATION_NATIVE_FUNCTIONS:
        if ((start, end) not in functions or not pe.executable(start, end-start)
                or hashlib.sha256(pe.read(start, end-start)).hexdigest() != pin):
            raise RuntimeBuildError('The reviewed native island readers differ.')
    return dict(module_sha256=expected, functions=[dict(begin=a, end=b, sha256=h)
        for a, b, h in ROTATION_NATIVE_FUNCTIONS])


def apply_rotation(files: dict[str, bytes]) -> None:
    backend = PRIVATE+'world_backend.c'
    value = files[backend]
    value = replace(value, b'#include "selection_policy.inc"',
        b'#include "selection_policy.inc"\n#include "island_rotation_plan.h"', 'verified ordinary rotation policy')
    value = replace(value,
        b'  if(!wsApplyPreferredStart(s,error,cap)||!wsGuaranteeStartResources(s,seed,error,cap)||!wsValidateFairStarts(s,error,cap))',
        b'  if(!wsAssignIslandRotations(s,seed,planned,planCount,error,cap)){planCount=0;return 0;}\n'
        b'  if(!wsApplyPreferredStart(s,error,cap)||!wsGuaranteeStartResources(s,seed,error,cap)||!wsValidateFairStarts(s,error,cap))',
        'deterministic orientation after packing and resources')
    value = replace(value, b'static int wsValidatePlan(const WSWorldSettings*s,char*error,uint32_t cap){',
        b'static int wsValidatePlan(const WSWorldSettings*s,char*error,uint32_t cap){\n'
        b' if(!wsIslandRotationsValid(s,planned,planCount)){wsMessage(error,cap,"The island orientation differs from its verified ordinary template.");return 0;}',
        'independent orientation certificate')
    value = replace(value, b'static int wsStagePlan(const WSWorldSettings*s,',
        b'#include "island_rotation_io.inc"\nstatic int wsStagePlanBase(const WSWorldSettings*s,',
        'exclusive per-attempt rotated assets')
    value = replace(value, b'__declspec(dllexport) int WorldSettingsStageScene(',
        b'static int wsStagePlan(const WSWorldSettings*s,const char*root,char*out,uint32_t outCap,char*error,uint32_t cap){\n'
        b' wsRotationCleanup();\n'
        b' if(!wsRotationStage(s,root,error,cap)){wsRotationCleanup();return 0;}\n'
        b' if(!wsStagePlanBase(s,root,out,outCap,error,cap)){wsRotationCleanup();return 0;}return 1;\n}\n'
        b'__declspec(dllexport) int WorldSettingsStageScene(', 'clean temporary islands on every stage failure')
    value = replace(value, b'unsigned char*nodes[WS_LIMIT];',
        b'unsigned char*nodes[WS_LIMIT];char rotatedPaths[WS_LIMIT][MAX_PATH];', 'validate all paths before native commit')
    value = replace(value,
        b'char full[MAX_PATH];if(!wsFullPath(gameDirectory,wsTemplates[p->templateIndex].path,full))',
        b'char full[MAX_PATH];if(!wsRotationSelectedPath(gameDirectory,p,full))', 'certify selected physical island path')
    value = replace(value, b'  nodes[count++]=node;seen[id]=1;',
        b'  memcpy(rotatedPaths[count],full,strlen(full)+1u);nodes[count++]=node;seen[id]=1;', 'cache certified rotated paths')
    value = replace(value,
        b'char full[MAX_PATH];wsFullPath(gameDirectory,wsTemplates[p->templateIndex].path,full);memset(node+0x1e,0,260);',
        b'const char*full=rotatedPaths[i];memset(node+0x1e,0,260);', 'atomic native path substitution')
    value = replace(value, b'void WorldSettingsFinishAttempt(int success){',
        b'void WorldSettingsFinishAttempt(int success){wsRotationCleanup();', 'owned rotated asset cleanup')
    files[backend] = value
    for name in ('island_rotation_plan.h','island_rotation_definitions.h','island_rotation_codec.inc','island_rotation_io.inc','island_rotation_preview.h'):
        files[PRIVATE+name] = authored(name)

    preview = PRIVATE+'world_menu_preview.inc'
    value = files[preview]
    value = replace(value, b'#include "world_factions.h"',
        b'#include "world_factions.h"\n#include "island_rotation_preview.h"', 'shared rotated coastline projection')
    value = replace(value,
        b'    uint32_t row=(uint32_t)y*WS_PREVIEW_COAST_SIZE/(uint32_t)ih;int first=-1;',
        b'    int first=-1;', 'rotated paint scanline')
    value = replace(value,
        b'     uint32_t bit=x<iw?row*WS_PREVIEW_COAST_SIZE+(uint32_t)x*WS_PREVIEW_COAST_SIZE/(uint32_t)iw:0;\n'
        b'     int solid=x<iw&&(coast[bit>>3]&(1u<<(bit&7u)));',
        b'     int solid=x<iw&&wsRotationPreviewSolid(p,coast,(uint32_t)x,(uint32_t)y,(uint32_t)iw,(uint32_t)ih);',
        'paint the physical island orientation')
    files[preview] = value
    click = PRIVATE+'menu_preview.inc'
    files[click] = replace(files[click],
        b'  uint32_t row=(uint32_t)(y-top)*WS_PREVIEW_COAST_SIZE/(uint32_t)(bottom-top);\n'
        b'  uint32_t column=(uint32_t)(x-left)*WS_PREVIEW_COAST_SIZE/(uint32_t)(right-left),bit=row*WS_PREVIEW_COAST_SIZE+column;\n'
        b'  if(!(wsPreviewCoasts[p->templateIndex][bit>>3]&(1u<<(bit&7u))))continue;',
        b'  if(!wsRotationPreviewSolid(p,wsPreviewCoasts[p->templateIndex],(uint32_t)(x-left),(uint32_t)(y-top),(uint32_t)(right-left),(uint32_t)(bottom-top)))continue;',
        'rotated coastline hit testing matches its paint pixels')
