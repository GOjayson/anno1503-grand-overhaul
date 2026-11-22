"""Reuse the reviewed disaster callbacks for generated multiplayer scenes."""

from pathlib import Path

from .world_options import PRIVATE, replace
from .world_options_disasters import verify_disaster_preimages
from .world_runtime_build import AI_LOADER


PREPARE_DISASTERS = "WorldSettingsPrepareMultiplayerDisasters"
CLEAR_DISASTERS = "WorldSettingsClearMultiplayerDisasters"
_NATIVE = Path(__file__).with_name("native") / "world_settings_multiplayer"


def apply_multiplayer_disasters(files, world_image: bytes, world_sha256: str):
    proof = verify_disaster_preimages({"AnnoWelt.dll": world_image}, {"AnnoWelt.dll": world_sha256})
    loader = AI_LOADER.rsplit("/", 1)[0] + "/install_test_hooks.c"
    source = files[loader]
    source = replace(
        source,
        b"static int wsPrepareBlob(uint32_t index,HMODULE self,WSPatch *patches,uint32_t *patchCount){\n"
        b" const WSBlob *blob=&wsBlobs[index];WSInstalledBlob *installed=&wsInstalled[index];",
        b"static int wsPrepareBlobFromPlan(const WSBlob *blob,WSInstalledBlob *installed,HMODULE self,WSPatch *patches,uint32_t *patchCount){",
        "reuse the guarded native bridge allocator for the multiplayer disaster subset",
    )
    source = replace(
        source, b"static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){",
        b"static int wsPrepareBlob(uint32_t index,HMODULE self,WSPatch *patches,uint32_t *patchCount){\n"
        b" return wsPrepareBlobFromPlan(&wsBlobs[index],&wsInstalled[index],self,patches,patchCount);\n"
        b"}\n"
        b"static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){",
        "preserve the original single-player hook plan",
    )
    hashes = ",".join(f"0x{value:02x}" for value in bytes.fromhex(world_sha256))
    pin = f"static const unsigned char wsMpDisasterWorldSha[32] = {{{hashes}}};\n".encode("ascii")
    files[loader.rsplit("/", 1)[0] + "/disaster_multiplayer_install.inc"] = (
        pin + (_NATIVE / "disaster_multiplayer_install.inc").read_bytes()
    )
    files[loader] = source + b'\n#include "disaster_multiplayer_install.inc"\n'

    name = PRIVATE + "disaster_policy.inc"
    data = replace(
        files[name], b"static uint32_t wsDisasterPending[5];",
        b"static uint32_t wsDisasterPending[5];\n"
        b"static WSDisasterContext wsMpDisasterPolicy;\n"
        b"int WorldSettingsConfigureMultiplayerDisasters(const unsigned char *policy){\n"
        b" WSDisasterContext c={0};\n"
        b" if(policy){\n"
        b"  uint32_t settings[4];memcpy(settings,policy,sizeof settings);\n"
        b"  c.master=settings[0];c.mask=settings[1];c.frequency=settings[2];c.severity=settings[3];\n"
        b"  if(!wsDisasterOptionsValid(c.master,c.mask,c.frequency,c.severity))return 0;\n"
        b"  memcpy(c.guid,policy+sizeof settings,sizeof c.guid);c.active=1;\n"
        b" }\n"
        b" AcquireSRWLockExclusive(&wsDisasterLock);wsMpDisasterPolicy=c;ReleaseSRWLockExclusive(&wsDisasterLock);\n"
        b" return 1;\n"
        b"}",
        "scope the agreed multiplayer policy to one generated scene GUID",
    )
    files[name] = replace(
        data,
        b" ReleaseSRWLockShared(&wsDisasterLock);return found;",
        b" if(!found&&type<WS_DISASTER_COUNT&&world&&wsMpDisasterPolicy.active&&\n"
        b"    !memcmp((unsigned char*)world+0x6e4c,wsMpDisasterPolicy.guid,16)){\n"
        b"  found=wsMpDisasterPolicy.master&&!!(wsMpDisasterPolicy.mask&(1u<<type))?1:-1;\n"
        b"  if(frequency)*frequency=(wsMpDisasterPolicy.frequency>>(type*2u))&3u;\n"
        b"  if(severity)*severity=(wsMpDisasterPolicy.severity>>(type*2u))&3u;\n"
        b" }\n"
        b" ReleaseSRWLockShared(&wsDisasterLock);return found;",
        "apply one agreed disaster policy to the host and client copies of that World",
    )
    return proof
