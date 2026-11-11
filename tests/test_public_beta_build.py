"""Public builder routing/pin decisions; no compiler or game invocation."""
from pathlib import Path
from contextlib import ExitStack
from types import SimpleNamespace
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from anno1503_overhaul import world_options_build as build


class PublicBetaBuildTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name).resolve();inputs=root/'inputs';inputs.mkdir()
        verified=dict(root=inputs,source_game=root/'source',source_data_root=root/'source',
                      native_host_root=inputs/'native-host',assets_root=inputs/'assets',compiler_path=root/'zig.exe',
                      manifest=dict(kind='fixture'))
        return inputs,dict(verified=verified,activity_inputs=({},{})),root/'build'

    def test_public_build_routes_only_validated_explicit_inputs_to_separate_host(self):
        path,inputs,output=self.fixture()
        report=dict(matches_reviewed_runtime=True,generator_id='reviewed')
        with (patch.object(build,'generator_id',return_value='reviewed'),
              patch.object(build,'PINNED_GENERATOR','reviewed'),
              patch.object(build,'_public_runtime_inputs',return_value=inputs)as validate,
              patch.object(build,'_build_options_runtime',return_value=report)as compile):
            self.assertIs(build.build_public_options_runtime(path,output=output),report)
        validate.assert_called_once_with(path)
        compile.assert_called_once_with('world-only',inputs['verified']['native_host_root'],
                                        output=output,_public_inputs=inputs)

    def test_unreviewed_source_refused_before_reading_inputs_or_compiling(self):
        path,inputs,output=self.fixture()
        with (patch.object(build,'generator_id',return_value='changed'),
              patch.object(build,'PINNED_GENERATOR','reviewed'),
              patch.object(build,'_public_runtime_inputs')as validate,
              patch.object(build,'_build_options_runtime')as compile,
              self.assertRaises(build.old.RuntimeBuildError)):
            build.build_public_options_runtime(path,output=output)
        validate.assert_not_called();compile.assert_not_called()

    def test_changed_runtime_or_generation_never_passes_public_review(self):
        path,inputs,output=self.fixture()
        for report in (dict(matches_reviewed_runtime=False,generator_id='reviewed'),
                       dict(matches_reviewed_runtime=True,generator_id='changed')):
            with (self.subTest(report=report),patch.object(build,'generator_id',return_value='reviewed'),
                  patch.object(build,'PINNED_GENERATOR','reviewed'),
                  patch.object(build,'_public_runtime_inputs',return_value=inputs),
                  patch.object(build,'_build_options_runtime',return_value=report),
                  self.assertRaises(build.old.RuntimeBuildError)):
                build.build_public_options_runtime(path,output=output)

    def test_maintainer_candidate_is_explicit_and_does_not_publish_or_install(self):
        path,inputs,output=self.fixture();report=dict(matches_reviewed_runtime=False,generator_id='candidate')
        with (patch.object(build,'_public_runtime_inputs',return_value=inputs),
              patch.object(build,'_build_options_runtime',return_value=report)as compile):
            self.assertIs(build.build_public_options_runtime(path,output=output,require_reviewed=False),report)
        self.assertNotIn('publish',compile.call_args.kwargs)
        with self.assertRaises(build.old.RuntimeBuildError):
            build.build_public_options_runtime(path,output=output,require_reviewed=1)

    def test_public_compiler_calls_suppress_console_and_historical_calls_keep_defaults(self):
        # Execute the real staging/compiler-call workflow against one explicitly
        # synthetic unit and a mocked compiler/PE boundary, for both routes.
        for public in (False,True):
            with self.subTest(public=public),tempfile.TemporaryDirectory()as folder,ExitStack()as stack:
                root=Path(folder).resolve();game=root/'game';game.mkdir()
                compiler=root/'toolchain/ziglang/zig.exe';compiler.parent.mkdir(parents=True);compiler.write_bytes(b'compiler fixture')
                unit='developer/source/runtime_dev3/fixture.c';source={unit:b'fixture source',build.old.ENGINE_PLAN:b'{}'}
                records=[]
                for name,data in source.items():
                    path=root/build.old.SOURCE_PREFIX/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                    records.append(dict(path=build.old.SOURCE_PREFIX+name,imported_sha256=hashlib.sha256(data).hexdigest()))
                (root/'provenance').mkdir();(root/'provenance/legacy_import.json').write_text(json.dumps(dict(source_files=records)))
                parser=root/'legacy/world_settings/activation/pe_exports.py';parser.parent.mkdir(parents=True,exist_ok=True)
                parser.write_text('def exports(data,required):return {name:1 for name in required}\n')
                compiled={build.old.SOURCE_PREFIX+unit:hashlib.sha256(source[unit]).hexdigest()}
                inputs_root=root/'inputs';inputs_root.mkdir()
                verified=dict(root=inputs_root,source_game=game,source_data_root=game,assets_root=inputs_root/'assets',
                              compiler_path=compiler,manifest={})
                inputs=dict(verified=verified,activity_inputs=({},{}))if public else None
                output=root/('.local/builds/public'if public else'.local/builds/historical')
                stack.enter_context(patch.object(build.old,'ROOT',root))
                stack.enter_context(patch.object(build.old,'_verified_sources',return_value=compiled))
                stack.enter_context(patch.object(build.old,'normalize_pe_metadata',return_value=(b'normalized fixture',{})))
                stack.enter_context(patch.object(build,'UNITS',[unit]))
                stack.enter_context(patch.object(build,'REQUIRED_EXPORTS',{'FixtureExport'}))
                stack.enter_context(patch.object(build,'generator_id',return_value='fixture'))
                stack.enter_context(patch.object(build,'os',SimpleNamespace(name='nt',environ=os.environ)))
                stack.enter_context(patch.object(build,'derive_sources',return_value=(source,{})))
                stack.enter_context(patch.object(build,'_derive_sources_exact',return_value=(source,{})))
                version=stack.enter_context(patch.object(build.subprocess,'check_output',return_value='0.16.0\n'))
                def compiled_output(command,**kwargs):
                    Path(command[command.index('-o')+1]).write_bytes(b'raw fixture')
                    return SimpleNamespace(returncode=0,stdout='')
                compile=stack.enter_context(patch.object(build.subprocess,'run',side_effect=compiled_output))
                stack.enter_context(patch.object(build.subprocess,'CREATE_NO_WINDOW',0x08000000,create=True))
                report=build._build_options_runtime('world-only',game,root/'toolchain',output=output,_public_inputs=inputs)
                self.assertTrue(report['built'])
                for call in (version.call_args,compile.call_args):
                    if public:self.assertEqual(call.kwargs['creationflags'],0x08000000)
                    else:self.assertNotIn('creationflags',call.kwargs)


if __name__=='__main__':unittest.main()
