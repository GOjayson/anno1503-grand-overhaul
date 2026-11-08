"""Bind the copied-size-aware Frame candidate to bounded native/lab evidence.

This publication is outside the release. It does not certify an actual repaired
game run, and does not turn failed119/166 visual runs into successful tests.
"""
from pathlib import Path
import hashlib,json,shutil,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_bytes())
def require(ok,m):
 if not ok:raise ValueError(m)


def main():
 native=read(HERE/'frame_depth_native_results.json');closure=read(HERE/'frame_depth_closure_audit.json');guards=read(HERE/'frame_depth_source_guard_results.json')
 grid=WORK/'grid/border';nav=WORK/'navigation/world_consumer';unwind=read(grid/'frame_depth_unwind_results.json');projection=read(nav/'repaired_frame_projection_results.json')
 for r in[native,closure,guards,unwind]:require(r.get('passed')is True,'A Frame native proof failed')
 require(projection.get('status')=='PASS','Independent Frame→Display proof failed')
 own_sha=sha(HERE/'frame_depth_patch.py');require(native['patch_source_sha256']==closure['patch_source_sha256']==guards['patch_source_sha256']==own_sha,'Candidate source/proof closure differs')
 profiles=[read(HERE/(name+'.json'))for name in['AnnoFrame.food_original.depth','AnnoFrame.world_overlay166.depth']]
 expected={'046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf':'8c0024aabd610bbb7ecfaaa43a09247448f5fc39e576eecafe906b38f2f31925','dfe71e26feb210bb1c400c338d338a71b1b3026c1e9b2e1ddf06a6378a1d5f86':'6b9972ec85f05e2b417096b5f0343daebd07daf53d4554758353a7c9cd4c6c80'}
 require({p['source_sha256']:p['output_sha256']for p in profiles}==expected,'Exact source/output profile fingerprints differ')
 require(all(p['runtime_edit_count']==7 and len(p['disk_only_metadata_edits'])==1 for p in profiles),'Expected7common runtime chunks and1disk-only metadata declaration')
 require(profiles[0]['runtime_edits']==profiles[1]['runtime_edits'],'Runtime source/copy patches differ')
 require(native['native_whole_camera_and_actual_state4_prefix_cases']==864 and native['native_leaf_register_cases']==28 and native['all_256_actual_native_height_values_tested']is True,'Native fixture matrix incomplete')
 require(native['legacy_null_and_rectangular_exact_output_cases']==720 and projection['legacy_or_null_matrix_snapshots_byte_exact']==360,'Legacy equivalence proof incomplete')
 require(projection['huge_Frame_to_native_Display_cases']==72 and projection['projected_vertices']==5832,'Independent complete mesh projection proof incomplete')
 require(guards['negative_cases']==7 and closure['original_Windows_image_mapping']['all_new_RVAs_originally_committed_RX']is True,'Exact source or original image mapping guards incomplete')
 require(unwind['loader_case_count']==4 and len(unwind['native_parent_unwind_cases'])==168,'Independent Windows unwind/loader cases incomplete')
 sources=[HERE/'frame_depth_patch.py',HERE/'test_frame_depth_candidate.py',HERE/'audit_frame_depth.py',HERE/'publish_frame_depth_review.py',
          HERE/'frame_depth_native_results.json',HERE/'frame_depth_closure_audit.json',HERE/'frame_depth_source_guard_results.json',
          HERE/'AnnoFrame.food_original.depth.json',HERE/'AnnoFrame.world_overlay166.depth.json',
          grid/'test_frame_depth_unwind.py',grid/'frame_depth_unwind_results.json',grid/'frame_depth_independent_refs.json',
          grid/'display_depth_results.json',grid/'h12diag_display_depth.json',grid/'h12diag_midpoint_display_depth.json',
          nav/'test_repaired_frame_projection.py',nav/'repaired_frame_projection_results.json',WORK/'live/H12_MIDPOINT_FAILURE.json']
 evidence={}
 for path in sources:
  require(path.is_file(),'Evidence missing: '+str(path));relative=path.relative_to(WORK).as_posix();evidence[relative]=sha(path)
 # Copy delegated evidence under a review-owned folder so root can carry only
 # scripts/reports, without shipping private candidateDLLs or native saves.
 target=HERE/'review_evidence';target.mkdir(exist_ok=True)
 copied={}
 for path in sources:
  if path.parent==HERE:continue
  relative=path.relative_to(WORK);dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():require(dest.read_bytes()==path.read_bytes(),'Preserve previous evidence copy')
  else:shutil.copyfile(path,dest)
  copied[dest.relative_to(HERE).as_posix()]=sha(dest)
 result=dict(passed=True,scope=__doc__,profile='history-amd64-size-aware-world-depth-v1',module='AnnoFrame.dll',architecture='AMD64 PE32+',source_sha256=own_sha,
  source_to_output_sha256=expected,runtime_edit_count=7,disk_only_metadata_edit_count=1,runtime_edits=profiles[0]['runtime_edits'],disk_only_metadata_edits=profiles[0]['disk_only_metadata_edits'],
  api=['transform_frame_depth(blob)->(bytes,manifest)','runtime_depth_edits()->[{rva,before,after,category}]'],
  behavior=dict(exact2048_square_World_scalar='1/5200',other_or_null_World_scalar='unchanged1/2600',fixed_cached_draw_bias=0.5,screenXY_and_camera_controls_unchanged=True,both_terrain_state4_and_sprite_state6_depth_scaled_consistently=True),
  native_frame_cases=864,legacy_null_nonsquare_byte_exact_cases=720,leaf_register_and_return_cases=28,actual_native_height_values_tested=256,huge_full_coordinate_depth_bounds=native['huge_full_world_depth_bounds'],
  independent_World_Frame_Display_projection_cases=72,independent_projected_vertices=5832,independent_legacy_snapshots_byte_exact=360,independent_Windows_unwind_cases=168,independent_Windows_image_loader_cases=4,
  rejected_unknown_partial_repeated_or_changed_sources=7,original_image_final_page_already_committed_RX=True,helper_private_call_graph_verified=True,helper_no_stack_adjustment_or_nonvolatile_changes=True,
  original_Food_hooks_and_all_unplanned_bytes_preserved=True,exception_directories_and_unwind_metadata_unchanged=True,
  causal_observed166_failure=dict(save_name='h12',actual_midpoint_terrain_stripe_confirmed=True,current_runtime_failed_visual_acceptance=True,actual_state4_fixed_point_depth_crosses_zero_at_stripe_view=True,counted_as_accepted_repaired_game_run=False),
  actual_repaired_game_run_verified=False,complete_feature_verified=False,game_or_copy_or_package_modified_by_review=False,
  evidence_sha256=evidence,copied_delegated_evidence_sha256=copied,
  remaining_actual_checks=['Fresh patched173 process: load preservedh12 and inspect the previous stripe location, all rotations/zooms and far islands.','New2048 generation with3AI, selected cultures/Pirate/Venetian owners; save and fresh-process reload/resave.','Actual256/512/1024 load/render regressions and restoration/combined-installer checks.'],
  limits=['Private native execution/emulation and Windows unwinding are automated component evidence, not a rendered Anno game.','The reduced Huge depth range halves fixed-point depth precision; actual drawing must be checked in the game.'])
 output=HERE/'FRAME_DEPTH_REVIEW.json';require(not output.exists(),'Preserve final Frame review');output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(passed=True,review=str(output),runtime_edits=7,evidence_files=len(evidence),repaired_game_run_verified=False)))


if __name__=='__main__':main()
