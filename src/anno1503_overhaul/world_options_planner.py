"""Staged climate, variety and layout policies for the in-game World screen."""
import hashlib
from .world_options import PRIVATE, authored, replace


def stage_selection_prelude(value: bytes, *, fixture: bool = False) -> bytes:
    """Use one selection implementation in production and its native fixture."""
    marker = (b'  wsSelectionBeginAttempt(s,attempt);uint32_t n=0,seen=0,climates=0;int failed=0;\n'
              if fixture else b'  uint32_t n=0,seen=0,climates=0;int failed=0;\n')
    end = b'  if(failed||!wsPack('
    if value.count(marker) != 1 or value.count(end) != 1:
        raise ValueError('Reviewed mandatory island-selection extent changed.')
    prefix, body = value.split(marker, 1)
    prelude, suffix = body.split(end, 1)
    # Native fixture and production differ only in diagnostics and their
    # original special-faction loop. Pin both complete reviewed preludes.
    expected = ('72e2860b94014582462d5109a452e47628e9177e41e633d357bf0602c74d9bdf' if fixture else
                'fc25a1543a17ecf500a17e594964638c3369635f788f1487a7d7f43584579612')
    if hashlib.sha256(prelude).hexdigest() != expected:
        raise ValueError('Reviewed mandatory island-selection preimage changed.')
    if fixture:
        replacement = (b'  wsSelectionBeginAttempt(s,attempt);uint32_t n=0;int failed=0;char selectionError[512]={0};\n'
            b'  int selected=wsSelectIslands(s,&n,NULL,NULL,selectionError,sizeof selectionError);\n'
            b'  if(selected<0&&!wsClimateQuotasActive(s))return 0;\n'
            b'  if(selected<=0)continue;\n')
    else:
        replacement = (b'  uint32_t n=0;int failed=0;\n'
            b'  int selected=wsSelectIslands(s,&n,cultureNames,climateNames,message,sizeof message);\n'
            b'  if(selected<0){wsMessage(error,cap,message);if(wsClimateQuotasActive(s))continue;return 0;}\n'
            b'  if(!selected){wsMessage(error,cap,message);continue;}\n')
    return prefix + replacement + end + suffix


def stage_selection_add(value: bytes) -> bytes:
    return replace(value, b'p->cropMask=cropMasks[t->climate];return 1;}',
        b'p->cropMask=cropMasks[t->climate];wsIslandSelectionAdded(index);return 1;}',
        'selection counters reflect every successfully added island')


def stage_selection_fixture(value: bytes) -> bytes:
    """Bind the historical native geometry fixture to the production prelude."""
    value = stage_selection_add(value)
    value = stage_selection_prelude(value, fixture=True)
    value = stage_selection_attempts(value)
    value = replace(value, b'#include "balanced_layout.inc"\n',
        b'#include "balanced_layout.inc"\n#include "island_selection.inc"\n',
        'shared native selection fixture')
    value = replace(value,
        b'if(!s||!out||!usedAttempt||s->islandCount<1||s->islandCount>WS_LIMIT||s->spacing<0||!wsConfigureWorldSize(s))return 0;',
        b'if(!s||!out||!usedAttempt||!wsClimateQuotaSettings(s)||s->spacing<0||!wsConfigureWorldSize(s))return 0;',
        'native fixture rejects malformed quota settings')
    return replace(value,
        b'  memcpy(out,planned,n*sizeof(*out));*usedAttempt=(uint32_t)attempt;return (int)n;',
        b'  if(!wsClimateQuotaCertificate(s,planned,n))continue;\n'
        b'  memcpy(out,planned,n*sizeof(*out));*usedAttempt=(uint32_t)attempt;return (int)n;',
        'independent native fixture quota certificate')


def stage_selection_attempts(value: bytes) -> bytes:
    return replace(value, b' for(int attempt=0;attempt<32;attempt++){\n',
        b' for(int attempt=0;attempt<(s->islandVariety?64:32);attempt++){\n'
        b'  if(attempt==32)rngState=seed?seed:0x15032026;\n',
        'retry soft variety preferences with the original bounded search before refusing world fit')


def apply_planner(files: dict[str, bytes]) -> None:
    """Extend fresh staged source; never edit the historical source closure."""
    selection = PRIVATE + 'selection_policy.inc'
    marker = b'static int wsChooseBalancedFill(const WSWorldSettings*s,uint32_t count){'
    value = files[selection]
    if value.count(marker) != 1:
        raise ValueError('Reviewed climate filler function changed.')
    prefix, body = value.split(marker, 1)
    # This is deliberately the final frozen function in the reviewed include.
    if body.count(b'\n}') != 1 or not body.rstrip().endswith(b'}'):
        raise ValueError('Reviewed climate filler extent changed.')
    newline = b'\r\n' if b'\r\n' in value else b'\n'
    prefix = replace(prefix, b' wsSelectionInit();wsSelectionStage=0;wsSelectionSmallest=0;',
        b' wsIslandSelectionReset((uint32_t)attempt);wsSelectionInit();wsSelectionStage=0;wsSelectionSmallest=0;',
        'reset quota and variety state on every bounded selection attempt')
    prefix = replace(prefix, b'uint32_t n=attempt<0?0u:(uint32_t)attempt;',
        b'uint32_t n=attempt<0?0u:(uint32_t)attempt%32u;',
        'retain the original lenient-size schedule in the soft-preference fallback')
    prefix = replace(prefix, b' if(!wsEligible(t,s)||wsTemplateFaction(t)!=(uint32_t)faction)return 0;',
        b' if(!wsEligible(t,s)||wsTemplateFaction(t)!=(uint32_t)faction||!wsClimateQuotaCandidate(s,t->climate))return 0;',
        'climate maxima and remaining mandatory slots apply to all candidates')
    prefix = replace(prefix,
        b'static int wsChoose(const WSWorldSettings*s,uint32_t requiredCulture,int climate,int ore,int whale,int empty,int faction){',
        b'static int wsChooseOriginal(const WSWorldSettings*s,uint32_t requiredCulture,int climate,int ore,int whale,int empty,int faction){',
        'retain original catalogue selection as the exact default path')
    files[selection] = (b'#include "island_variety.inc"' + newline + prefix +
        b'#include "island_choice.inc"' + newline + b'#include "advanced_climate.inc"' + newline)
    files[PRIVATE + 'advanced_climate.inc'] = authored('advanced_climate.inc')
    for name in ('island_variety.inc', 'island_choice.inc', 'island_selection.inc', 'island_shapes.h'):
        files[PRIVATE + name] = authored(name)

    layout = PRIVATE + 'balanced_layout.inc'
    files[layout] = replace(files[layout],
        b'static int wsPack(uint32_t count,uint32_t spacing){',
        b'#include "advanced_layout.inc"\n'
        b'static int wsPack(const WSWorldSettings*s,uint32_t count,uint32_t spacing){',
        'advanced layout settings')
    files[layout] = replace(files[layout],
        b' if(!wsCompactPack(count,spacing))return 0;\n wsSpreadPack(count,spacing);return 1;',
        b' if(!s||s->layoutStyle<0||s->layoutStyle>2)return 0;\n'
        b' if(s->layoutStyle==0){if(!wsCompactPack(count,spacing))return 0;wsSpreadPack(count,spacing);return 1;}\n'
        b' return wsAdvancedPack(s,count,spacing);', 'advanced layout dispatch')
    files[PRIVATE + 'advanced_layout.inc'] = authored('advanced_layout.inc')

    backend = PRIVATE + 'world_backend.c'
    files[backend] = stage_selection_add(files[backend])
    files[backend] = stage_selection_prelude(files[backend])
    files[backend] = stage_selection_attempts(files[backend])
    files[backend] = replace(files[backend],
        b' if(!wsConfigureWorldSize(s)){wsMessage(error,cap,"World size must be Small (256), Medium (512), Big (1024) or Huge (2048).");return 0;}',
        b' if(!wsClimateQuotaSettings(s)){wsMessage(error,cap,"Climate minima/maxima must fit the island count and permit all six climates.");return 0;}\n'
        b' if(!wsConfigureWorldSize(s)){wsMessage(error,cap,"World size must be Small (256), Medium (512), Big (1024) or Huge (2048).");return 0;}',
        'independent climate-quota input guard')
    files[backend] = replace(files[backend], b'wsPack(n,(uint32_t)s->spacing)',
                             b'wsPack(s,n,(uint32_t)s->spacing)', 'advanced layout call')
    files[backend] = replace(files[backend],
        b' if(pirates!=((s->factions&1u)!=0)',
        b' if(!wsAdvancedLayoutMatches(s,planCount)){wsMessage(error,cap,"The selected layout cannot preserve its central ocean.");return 0;}\n'
        b' if(pirates!=((s->factions&1u)!=0)', 'independent layout certificate')
    files[backend] = replace(files[backend],
        b'"Island size, count and spacing do not fit in the selected %u by %u world. Reduce count, island size or spacing."',
        b'"Island size, count, spacing and layout do not fit in the selected %u by %u world. Reduce them or choose another layout."',
        'layout fit diagnostic')
    files[backend] = replace(files[backend], b'#include "mineral_fertility.inc"',
        b'#include "mineral_fertility.inc"\n#include "resource_distribution.inc"\n#include "island_selection.inc"',
        'resource geography and nearby basic-resource policy')
    files[backend] = replace(files[backend],
        b'if(!wsApplyPlantFertility(s,seed,error,cap)||!wsApplyMineralFertility(s,seed,error,cap))',
        b'if(!wsApplyPlantFertility(s,seed,error,cap)||!wsApplyMineralFertility(s,seed,error,cap)||!wsApplyResourceDistribution(s,seed,error,cap))',
        'preserve fertility census while distributing resources')
    files[backend] = replace(files[backend],
        b' if(pirates!=((s->factions&1u)!=0)',
        b' if(!wsValidateStartResources(s,error,cap))return 0;\n'
        b' if(!wsClimateQuotaCertificate(s,planned,planCount)){wsMessage(error,cap,"The generated world does not satisfy its climate minima and maxima.");return 0;}\n'
        b' if(pirates!=((s->factions&1u)!=0)', 'independent resource and nearby basics certificate')
    files[PRIVATE + 'resource_distribution.inc'] = authored('resource_distribution.inc')
