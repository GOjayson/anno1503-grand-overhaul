"""Copied-DLL ABI/configuration/staging checks in Python, not a game run.

Does not invoke UI, native factories or memory hooks. Generated files are confined
to the independent copy and removed in finally. World choices stay in the game's
dialog during actual play; these explicit calls are automated test fixtures.
"""
from pathlib import Path
import ctypes as C
import hashlib,json
HERE=Path(__file__).resolve().parent;WORK=HERE.parent;ROOT=WORK.parent
built=json.loads((HERE/'build_result.json').read_text())
assert hashlib.sha256((HERE/'AnnoWorldSettings.dll').read_bytes()).hexdigest()==built['sha256']
for name,digest in built['source_sha256'].items():assert hashlib.sha256((WORK/name).read_bytes()).hexdigest()==digest,name
class Settings(C.Structure):
 _fields_=[('size',C.c_uint32),('difficulty',C.c_int32),('islandSize',C.c_int32),('islandCount',C.c_int32),('spacing',C.c_int32),('aiCount',C.c_int32),('cultures',C.c_uint32)]
lib=C.CDLL(str(HERE/'AnnoWorldSettings.dll'))
lib.WorldSettingsSettingsSize.restype=C.c_uint32
lib.WorldSettingsValidateSettings.argtypes=[C.POINTER(Settings),C.c_void_p,C.c_uint32]
lib.WorldSettingsConfigureDevelopmentRoot.argtypes=[C.c_wchar_p];lib.WorldSettingsConfigureDevelopmentRoot.restype=C.c_uint32
lib.WorldSettingsCopyConfigurationError.argtypes=[C.c_void_p];lib.WorldSettingsCopyConfigurationError.restype=C.c_uint32
lib.WorldSettingsSetBackend.argtypes=[C.c_void_p,C.c_void_p]
lib.WorldSettingsStageScene.argtypes=[C.POINTER(Settings),C.c_char_p,C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32]
lib.WorldSettingsPendingPath.restype=C.c_char_p
lib.WorldSettingsValidateScene.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32]
err=C.create_string_buffer(512);out=C.create_string_buffer(260);cases=[]
assert lib.WorldSettingsSettingsSize()==C.sizeof(Settings)==28
s=Settings(28,1,3,24,16,0,255)
assert lib.WorldSettingsValidateSettings(C.byref(s),err,len(err))==1
cases.append('combined settings ABI and valid input')
for field,value in [('size',0),('difficulty',-1),('difficulty',3),('islandSize',4),('islandCount',0),('islandCount',129),('spacing',257),('aiCount',1),('cultures',256)]:
 bad=Settings.from_buffer_copy(s);setattr(bad,field,value)
 assert lib.WorldSettingsValidateSettings(C.byref(bad),err,len(err))==0 and err.value,(field,value)
 cases.append(f'reject {field}={value}')
for path in [None,'relative',str(ROOT),str(WORK/'no_such_copy')]:
 assert lib.WorldSettingsConfigureDevelopmentRoot(path)==0
 assert lib.WorldSettingsCopyConfigurationError(err)>1 and err.value
 cases.append('reject unmarked/relative/missing configuration '+str(path))
copy=WORK/'game_copy'
assert lib.WorldSettingsConfigureDevelopmentRoot(str(copy))==1
assert lib.WorldSettingsCopyConfigurationError(err)==1 and not err.value
cases.append('marked independent copy accepted')
try:
 assert lib.WorldSettingsStageScene(C.byref(s),str(copy).encode('mbcs'),913,out,len(out),err,len(err))==1,err.value
 generated=Path(out.value.decode('mbcs'));assert generated.is_relative_to(copy/'Scenes') and generated.is_file()
 assert lib.WorldSettingsIsActive()==1 and lib.WorldSettingsPendingPath()==out.value
 assert lib.WorldSettingsConfigureDevelopmentRoot(None)==0
 assert lib.WorldSettingsPendingPath()==out.value and generated.is_file()
 cases.append('pending world prevents configuration change without losing its file')
 assert lib.WorldSettingsValidateScene(None,err,len(err))==0 and err.value
 cases.append('staging alone cannot authorize a native scene')
finally:
 lib.WorldSettingsFinishAttempt(0)
 assert not lib.WorldSettingsIsActive() and not lib.WorldSettingsPendingPath()
 if out.value:assert not Path(out.value.decode('mbcs')).exists()
 lib.WorldSettingsSetBackend(None,None)
cases.append('pending file and registration cleanup')
report={'scope':__doc__,'runtime_sha256':built['sha256'],'passed':len(cases),'cases':cases}
(HERE/'integrated_results.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
