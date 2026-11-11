"""Staged starting-position, cargo and inspected native-disaster options.

Only newly staged runtime sources change. The immutable imported source and
its tested Food implementation remain available byte-for-byte.
"""
from .world_options import PRIVATE, authored, replace


def apply_start(files: dict[str, bytes]) -> None:
    header = PRIVATE + 'world_backend.h'
    files[header] = replace(files[header], b'#include "advanced_settings.h"',
        b'__declspec(dllexport) int WorldSettingsStartingIslandEligible(uint32_t);\n'
        b'__declspec(dllexport) int WorldSettingsStartingIslandChosen(void);\n'
        b'int WorldSettingsValidateChosenDisasters(void*,char*,uint32_t);\n'
        b'#include "advanced_settings.h"', 'starting island query declarations')

    ships = PRIVATE + 'world_ship_reserves.h'
    files[ships] = replace(files[ships], b'static uint32_t wsWorld=1024u;',
        b'static uint32_t wsWorld=1024u;\n'
        b'static uint32_t wsBaseShipReserveCount,wsPreferredStartActive;\n'
        b'static float wsPreferredStartX,wsPreferredStartY;\n'
        b'static uint32_t wsStartOverrideMask;\n'
        b'static float wsStartOverrideXY[4][2];', 'preferred start state')
    files[ships] = replace(files[ships],
        b'static void wsWorldShipPosition(uint32_t owner,float*x,float*y){',
        b'static void wsWorldShipPosition(uint32_t owner,float*x,float*y){\n'
        b' if(owner<4u&&(wsStartOverrideMask&(1u<<owner))){*x=wsStartOverrideXY[owner][0];*y=wsStartOverrideXY[owner][1];return;}\n'
        b' if(!owner&&wsPreferredStartActive){*x=wsPreferredStartX;*y=wsPreferredStartY;return;}',
        'human spawn override')
    files[ships] = replace(files[ships], b' wsExpectedSceneShipCount=wsActiveShipReserveCount=0;',
        b' wsExpectedSceneShipCount=wsActiveShipReserveCount=wsBaseShipReserveCount=0;wsPreferredStartActive=wsStartOverrideMask=0;',
        'new spawn reservation scope')
    files[ships] = replace(files[ships], b'}wsActiveShipReserveCount=5;}\n return 1;',
        b'}wsActiveShipReserveCount=5;}\n wsBaseShipReserveCount=wsActiveShipReserveCount;\n return 1;',
        'base reservation count')

    backend = PRIVATE + 'world_backend.c'
    if b'#include "resource_distribution.inc"' in files[backend]:
        files[backend] = replace(files[backend], b'#include "resource_distribution.inc"',
            b'#include "resource_distribution.inc"\n#include "start_position.inc"', 'preferred start after resource helpers')
    else:
        # The isolated starting-policy fixture has no resource planner. Full
        # production apply_options always stages resource helpers first.
        files[backend] = replace(files[backend], b'#include "mineral_fertility.inc"',
            b'#include "mineral_fertility.inc"\n#include "start_position.inc"', 'preferred start helpers')
    files[backend] = replace(files[backend], b'  if(failed||!wsPack',
        b'  if(!wsConfigureWorldSize(s)){wsMessage(error,cap,"The starting ship reservation could not reset.");return 0;}\n'
        b'  if(failed||!wsPack', 'reset preferred spawn before every packing attempt')
    files[backend] = replace(files[backend],
        b'  if(wsValidatePlan(s,error,cap)){wsPreviewRemember(s,seed);wsMessage(error,cap,"");return 1;}planCount=0;',
        b'  if(!wsApplyPreferredStart(s,error,cap)||!wsGuaranteeStartResources(s,seed,error,cap)||!wsValidateFairStarts(s,error,cap)){planCount=0;return 0;}\n'
        b'  if(wsValidatePlan(s,error,cap)){wsPreviewRemember(s,seed);wsMessage(error,cap,"");return 1;}planCount=0;',
        'starting assignments after resource distribution and before preview')
    files[backend] = replace(files[backend],
        b' if(!wsConfigureWorldSize(s)){wsMessage(error,cap,"The selected world size or starting fleet is unsupported.");return 0;}',
        b' if(!wsConfigureWorldSize(s)){wsMessage(error,cap,"The selected world size or starting fleet is unsupported.");return 0;}\n'
        b' if(!wsApplyPreferredStart(s,error,cap)||!wsValidateFairStarts(s,error,cap)||!wsValidatePlan(s,error,cap))return 0;',
        'stage preferred fleet and recertify unchanged islands')
    files[backend] = replace(files[backend], b'#include "mineral_persistence.inc"',
        b'#include "mineral_persistence.inc"\n'
        b'int WorldSettingsValidateChosenDisasters(void*world,char*error,uint32_t cap){\n'
        b' uint32_t flags=0,expected=wsExpectedDisasters?0u:0x86u;\n'
        b' if(!world||!wsCertRead((unsigned char*)world+0x6eec,&flags,4)||(flags&0x86u)!=expected){\n'
        b'  wsMessage(error,cap,"Loaded disasters differ from the option chosen in World Settings.");return 0;\n'
        b' }return 1;\n}\n', 'post-profile read-only disaster certificate')
    files[PRIVATE + 'start_position.inc'] = authored('start_position.inc')
    files[PRIVATE + 'fair_starts.inc'] = authored('fair_starts.inc')

    cargo = PRIVATE + 'start_options.inc'
    files[cargo] = replace(files[cargo],
        b'static int wsStartingMoneyAllowed(int32_t n)',
        b'#include "start_cargo.inc"\nstatic int wsStartingMoneyAllowed(int32_t n)', 'custom cargo helper')
    files[cargo] = replace(files[cargo],
        b' wsExpectedStartShips[2]=(WSStartShip){s->startingFleet==1?1504:1502,x+6,y+6};\n return 1;',
        b' wsExpectedStartShips[2]=(WSStartShip){s->startingFleet==1?1504:1502,x+6,y+6};\n'
        b' if(!wsStartingCargoSelection(s)){wsMessage(error,cap,"Custom cargo exceeds the verified trade ship holds.");return 0;}\n return 1;',
        'validated expected cargo')
    files[cargo] = replace(files[cargo],
        b'  if(wsStartTag(stock+f.at,"WAREN")&&!index&&wsExpectedStartingFleet==1)memcpy(cargo,f.data,32);\n',
        b'', 'replace inherited cargo with expected slots')
    files[cargo] = replace(files[cargo],
        b' if(wsExpectedStartingFleet==2){wsPut16(cargo,41);wsPut16(cargo+2,40);wsPut16(cargo+8,42);wsPut16(cargo+10,40);}',
        b' wsStartingCargoBytes(cargo,index,holds);', 'serialize exact custom cargo slots')
    files[cargo] = replace(files[cargo],
        b'   if(s->startingFleet){if(!wsStartingNewShip(&b,f.data,f.size,0))goto failure;}',
        b'   if(s->startingFleet||s->cargoMode){if(!wsStartingNewShip(&b,f.data,f.size,0))goto failure;}',
        'single custom ship serialization')
    files[PRIVATE + 'start_cargo.inc'] = authored('start_cargo.inc')
    certificate = PRIVATE + 'starting_fleet_certificate.inc'
    files[certificate] = replace(files[certificate],
        b'  if(wsExpectedStartingFleet==2){if(i==0){expectedGood=41;want=40;}else if(i==1){expectedGood=42;want=40;}}\n'
        b'  else if(!index&&i<4){static const uint32_t goods[4]={42,26,41,41};expectedGood=goods[i];want=(uint16_t)(i==1?10:(i==3&&wsExpectedStartingDifficulty?30:50));}',
        b'  expectedGood=wsExpectedCargoGoods[index][i];want=wsExpectedCargoTons[index][i];',
        'loaded custom cargo certificate')

    files[PRIVATE + 'native_faction_options.h'] = authored('start_disasters.h')
    menu = PRIVATE + 'WorldSettings.c'
    files[menu] = replace(files[menu], b'wsBindNativeFactionOptions(d->frame,d->settings.factions)',
        b'wsBindNativeFactionOptions(d->frame,d->settings.factions,d->settings.disasters)',
        'native disasters selection')
    ai = PRIVATE + 'world_ai.c'
    files[ai] = replace(files[ai], b'extern int WorldSettingsIsActive(void);',
        b'extern int WorldSettingsIsActive(void);\n#ifndef WS_AI_FIXTURE\nextern int WorldSettingsFinishNativeSetup(int);\n#endif',
        'native-start completion owns the bounded setup rollback')
    files[ai] = replace(files[ai], b' if(!complete)InterlockedExchange(&wsProfileStatus,0);',
        b' #ifndef WS_AI_FIXTURE\n'
        b' if(!WorldSettingsFinishNativeSetup(complete)){complete=0;snprintf(wsProfileError,sizeof wsProfileError,"%s","The original game setup could not be restored safely. Close Anno and start it again before creating another world.");}\n'
        b' #endif\n if(!complete)InterlockedExchange(&wsProfileStatus,0);',
        'restore failed custom native starts and discard only on complete commit')
    files[ai] = replace(files[ai], b'extern int WorldSettingsIsActive(void);',
        b'extern int WorldSettingsIsActive(void);\n'
        b'extern int WorldSettingsValidateChosenDisasters(void*,char*,uint32_t);\n'
        b'extern uint32_t WorldSettingsExpectedFairOwners(void);',
        'post-profile disaster declaration')
    files[ai] = replace(files[ai],
        b'  if(!suspend&&!disabled&&thinking)active++;',
        b'  if(!suspend&&!disabled&&thinking)active++;\n'
        b'  uint32_t fair=WorldSettingsExpectedFairOwners();\n'
        b'  if(fair&&((!suspend&&!disabled&&thinking)!=(id<32u&&!!(fair&(1u<<id)))))return wsAIError(error,cap,"Active opponent owners differ from the validated fair starting positions.");',
        'read-only active opponent owner identity certificate')
    files[ai] = replace(files[ai],
        b' if(valid==1)valid=WorldSettingsBindAIDiplomacy(world,expected,wsDiplomacyExpected,approved,wsProfileError,sizeof wsProfileError);',
        b' if(valid==1)valid=WorldSettingsBindAIDiplomacy(world,expected,wsDiplomacyExpected,approved,wsProfileError,sizeof wsProfileError);\n'
        b' if(valid==1)valid=WorldSettingsValidateChosenDisasters(world,wsProfileError,sizeof wsProfileError);',
        'validate disaster flags after original native profile commit')
