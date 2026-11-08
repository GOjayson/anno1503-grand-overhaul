"""Publish outside-only bias2 component approval; actual game remains unverified."""
from pathlib import Path
import hashlib,json,shutil,sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;WORK=HERE.parents[1]


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def require(ok,m):
 if not ok:raise ValueError(m)


def main():
 native=read(HERE/'frame_bias_native_results.json');closure=read(HERE/'frame_bias_closure_audit.json');grid=WORK/'grid/border';nav=WORK/'navigation/world_consumer'
 unwind=read(grid/'frame_bias_unwind_results.json');projection=read(nav/'repaired_frame_bias2_results.json');domains=read(grid/'display_depth_domains_results.json')
 for r in[native,closure,unwind,domains]:require(r.get('passed')is True,'A native component proof failed')
 require(projection.get('status')=='PASS','Independent mesh/sprite base proof failed')
 source=sha(HERE/'frame_bias_patch.py');require(native['patch_source_sha256']==closure['patch_source_sha256']==source,'Candidate source/proof closure differs')
 profiles=[read(HERE/(x+'.json'))for x in['AnnoFrame.food_original.bias2','AnnoFrame.world_overlay166.bias2']]
 expected={'046b5ad6f351dfe867ed38ce29fb50a594485b43a32ee90adadc48e850466baf':'79eb380f16ab9c1d3b7c9370c2a337a66bae4f04a118fc14bf5647e45ad896cf','dfe71e26feb210bb1c400c338d338a71b1b3026c1e9b2e1ddf06a6378a1d5f86':'59a4856b2551d12990501680511ab0684348c4214476ed398d17e1a99e46c4fb'}
 require({p['source_sha256']:p['output_sha256']for p in profiles}==expected,'Canonical source/output fingerprints differ')
 require(all(p['runtime_edit_count']==7 and len(p['disk_only_metadata_edits'])==1 for p in profiles)and profiles[0]['runtime_edits']==profiles[1]['runtime_edits'],'Source/copy runtime+disk plans differ')
 require(native['native_camera_cases']==864 and native['primary_and_alternate_renderer_cases']==1440 and native['legacy_null_nonsquare_exact_cases']==720 and native['native_leaf_register_cases']==56,'Whole native fixture coverage incomplete')
 require(native['all_original_XY_and_height_depth_slopes_bit_identical']and native['original_secondary_state6_matrix_and_viewport_origin_bit_identical']and native['bias_is_camera_zoom_viewport_independent'],'Camera/depth cache/local bias contract failed')
 require(projection['native_mesh_vertices']==5832 and projection['native_sprite_base_projection_cases']==2808 and projection['native_render_submission_prefixes']==1440,'Independent geometry/sprite proof incomplete')
 require(unwind['native_unwind_case_count']==240 and unwind['loader_case_count']==4,'Independent Windows closure incomplete')
 require(domains['native_state6_global_case_count']==10 and domains['state6_translation_exactly_invariant']is False and domains['state6_original_half_bias_and_original_coefficients_recommended']is True,'Native state6 precision preservation evidence differs')
 require(len(domains['native_water_over_nearer_land_counterexamples'])==10,'Controlled shoreline native pixel counterexamples incomplete')
 failure=read(WORK/'live/H12_DEPTH173_FAILURE.json');require(failure.get('release_accepted')is False or'FAIL'in str(failure.get('status','')),'Failed previous173 candidate not explicit')
 sources=[HERE/'frame_bias_patch.py',HERE/'test_frame_bias_candidate.py',HERE/'audit_frame_bias.py',HERE/'publish_frame_bias_review.py',HERE/'frame_bias_native_results.json',HERE/'frame_bias_closure_audit.json',HERE/'AnnoFrame.food_original.bias2.json',HERE/'AnnoFrame.world_overlay166.bias2.json',
          HERE.parent/'frame_depth/test_frame_depth_candidate.py',HERE.parent/'frame_depth/frame_depth_patch.py',
          grid/'test_frame_bias_unwind.py',grid/'frame_bias_unwind_results.json',grid/'probe_display_depth_domains.py',grid/'display_depth_domains_results.json',grid/'h12depth_display_depth.json',grid/'h12diag_midpoint_display_depth.json',
          nav/'test_repaired_frame_bias.py',nav/'repaired_frame_bias2_results.json',nav/'RECENTER_BIAS2_EVIDENCE_INDEX.json',nav/'RECENTER_BIAS2_REVIEW.md',WORK/'live/H12_DEPTH173_FAILURE.json']
 evidence={};copies={};destroot=HERE/'review_evidence';destroot.mkdir(exist_ok=True)
 for path in sources:
  require(path.is_file(),'Review evidence missing: '+str(path));relative=path.relative_to(WORK);evidence[relative.as_posix()]=sha(path)
  if path.parent!=HERE:
   target=destroot/relative;target.parent.mkdir(parents=True,exist_ok=True)
   if target.exists():require(target.read_bytes()==path.read_bytes(),'Preserve delegated evidence copy')
   else:shutil.copyfile(path,target)
   copies[target.relative_to(HERE).as_posix()]=sha(target)
 result=dict(passed=True,automated_component_approved=True,scope=__doc__,profile='history-amd64-world-centered-depth-bias-v1',intended_combined_profile='history-amd64-world-ship-render-and-recenter-v4',module='AnnoFrame.dll',architecture='AMD64 PE32+',
  source_sha256=source,source_to_output_sha256=expected,api=['transform_frame_bias(blob)->(bytes,manifest)','runtime_bias_edits()->[{rva,before,after,category}]'],runtime_edit_count=7,disk_only_metadata_edit_count=1,runtime_edits=profiles[0]['runtime_edits'],disk_only_metadata_edits=profiles[0]['disk_only_metadata_edits'],
  state4_bias_sites=['0x1c3f6','0x1c7d0'],original_normalization_and_height_precision_preserved=True,original_state6_matrix_and_all_local_sprite_globals_preserved=True,
  Huge_bias='.5f - 1024.0f*(native camera depthX+depthY)',legacy_or_null_world_bias='exact native.5f',bias_independent_of_camera_pan_zoom_viewport=True,
  whole_camera_cases=864,both_renderer_prefix_cases=1440,legacy_null_nonsquare_byte_exact_cases=720,leaf_GPR_XMM_return_cases=56,native_height_values_tested=256,Huge_full_coordinate_depth_bounds=native['Huge_complete_coordinate_depth_bounds'],
  independent_native_mesh_vertices=5832,independent_native_sprite_base_projection_cases=2808,independent_native_Windows_unwind_cases=240,independent_Windows_loader_RX_leaf_cases=4,
  exact_source_guard_rejection_cases=13,exception_unwind_tables_and_all_Food_hooks_unchanged=True,all_unplanned_file_bytes_preserved=True,
  controlled_native_shore_pixel_counterexamples_show_half_precision_regression=10,controlled_numerical_proof_is_not_actual_game_causality=True,
  prior_half_depth173_actual_visual_acceptance_failed=True,prior_midpoint166_actual_visual_acceptance_failed=True,actual_repaired_game_run_verified=False,complete_feature_verified=False,game_or_copy_or_package_modified_by_review=False,
  evidence_sha256=evidence,copied_delegated_evidence_sha256=copies,
  remaining_actual_checks=['Fresh v4 load of the preservedh12: inspect previous midpoint and shoreline views at matching zoom and all rotations.','New2048 generation/preview/save with3AI and selected native/Pirate/Venetian owners, followed by same-runtime fresh-process reload/resave.','Actual256/512/1024 render/load regressions and final combined installer/restoration checks.'],
  limits=['Native/emulated pixel and unwind checks are bounded automated evidence, not an actual rendered-game pass.','Original16-bit depth quantization still exists; comparison-phase ties can occur and actual coast rendering must be checked.','Old experimental single-site/half-depth candidates are preserved outside and are not this approved component.'])
 out=HERE/'FRAME_BIAS_REVIEW.json';require(not out.exists(),'Preserve final review');out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(passed=True,review=str(out),runtime_edits=7,evidence_files=len(evidence),actual_game_verified=False)))


if __name__=='__main__':main()
