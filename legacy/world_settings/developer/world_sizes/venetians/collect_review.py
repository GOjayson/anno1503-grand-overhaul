"""Bind current Venetian asset/source/fixture evidence without running a game."""
from pathlib import Path
import hashlib,json

HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[2]
PRIVATE=PACKAGE/'developer/source/engine_resume/ai_food/experiment_runtime'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise ValueError(message)


def collect(package=PACKAGE):
    package=Path(package).resolve();here=package/'developer/world_sizes/venetians';private=package/'developer/source/engine_resume/ai_food/experiment_runtime'
    evidence={}
    def bind(name,expected=None):
        path=(package/name).resolve(strict=True);require(path.is_relative_to(package),'Unsafe Venetian evidence path')
        actual=sha(path);require(expected is None or actual==expected,'Stale Venetian evidence: '+name);evidence[name]=actual
        return json.loads(path.read_bytes())if path.suffix=='.json'else None
    asset=bind('developer/world_sizes/venetians/venetian_assets.json')
    require(asset['catalogue_count']==444 and asset['template_index']==443 and asset['actual_game_executed'] is False and asset['original_game_files_modified'] is False,'Venetian asset scope differs')
    bind('developer/world_sizes/venetians/generate_venetian_assets.py',asset['generator_sha256'])
    bind('developer/source/engine_resume/ai_food/experiment_runtime/world_catalogue.h',asset['catalogue_sha256'])
    bind('developer/source/engine_resume/ai_food/experiment_runtime/world_factions.h',asset['factions_sha256'])
    require(len(asset['files'])==1 and asset.get('required_copy_inputs')=={'Scenes/Islands/Nord/N_080x080_dummy.scp':'e64de5cd9008a3675f26a29e8f0855a3a7eabdc237334a2f2aa4c9e9ee058f35'},'Venetian asset or required stock loading dummy policy differs')
    for row in asset['files']:bind(row['payloadpath'],row['sha256'])
    auto=bind('developer/world_sizes/venetians/automated_results.json')
    require(auto['passed']is True and auto['game_executed']is False and len(auto['scene_controller_cases'])==12 and len(auto['rejected_cases'])==23 and auto['native_city_building_count']==73,'Compiled Venetian fixtures incomplete')
    require(auto.get('required_existing_stock_dummy')==dict(path='Scenes/Islands/Nord/N_080x080_dummy.scp',sha256='e64de5cd9008a3675f26a29e8f0855a3a7eabdc237334a2f2aa4c9e9ee058f35',bytes=27289,bounded_format_verified=True,not_introduced_or_modified=True),'Stock80dummy preservation/format fixture is missing')
    for name,expected in auto['source_sha256'].items():bind(name,expected)
    source=(private/'validated_world.inc').read_text();gate=source[source.index('/* Venetian owner gate:'):source.index('/* Welt a28e0 property1c')]
    require(hashlib.sha256(gate.encode()).hexdigest()==auto['owner_gate_sha256'],'Venetian owner gate differs from tested production helper')
    native=bind('developer/world_sizes/venetians/native_results.json')
    require(native['passed']is True and native['actual_game_executed']is False and len(native['native_owner_selection_cases'])==4 and len(native['native_relocation_cases'])==10 and native['native_building_coordinate_cases']==730,'Native Venetian alias/relocation fixtures incomplete')
    bind('developer/world_sizes/venetians/native_venetian.py',native['script_sha256']);bind('developer/world_sizes/venetians/native_relocation.asm')
    require(native['asset_sha256']==asset['files'][0]['sha256'],'Native Venetian proof used a different asset')
    saved=bind('developer/world_sizes/venetians/save_inspector_tests.json')
    require(saved['passed']is True and saved['game_executed']is False and saved['synthetic_positive_cases']==2 and len(saved['rejected_cases'])==13,'Venetian saved-town inspector checks incomplete')
    bind('developer/world_sizes/venetians/inspect_venetian_save.py',saved['inspector_sha256']);bind('developer/world_sizes/venetians/test_save_inspector.py',saved['test_sha256'])
    bind('developer/world_sizes/venetians/README.txt');bind('developer/world_sizes/venetians/collect_review.py')
    return dict(scope=__doc__,passed=True,game_executed=False,ui_or_gameplay_verified=False,catalogue_templates=444,venetian_template_index=443,venetian_asset_sha256=asset['files'][0]['sha256'],venetian_scene_controller_cases=12,venetian_rejected_cases=23,venetian_native_owner_selection_cases=4,venetian_native_relocation_cases=10,venetian_native_building_coordinate_cases=730,venetian_save_inspector_synthetic_cases=2,venetian_save_inspector_rejected_cases=13,owner_gate_sha256=auto['owner_gate_sha256'],evidence_sha256=evidence,limits=['City/building construction and complete native save/reload require separate actual-game evidence.','Serialized SUSPEND is not proof of current or future controller activity or trading.'])


if __name__=='__main__':
    result=collect();(HERE/'VENETIAN_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,evidence_files=len(result['evidence_sha256']),game_executed=False),indent=2))
