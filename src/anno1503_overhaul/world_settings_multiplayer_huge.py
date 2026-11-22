"""Build the optional, reversible Huge multiplayer engine transaction."""

from hashlib import sha256
from json import loads
from pathlib import Path

from .world_options import replace
from .world_runtime_build import AI_LOADER, PE, WORLD_ONLY_ENGINE_PLAN_SHA256


PREPARE_EXPORT = "WorldSettingsPrepareMultiplayerHugeWorld"
CLEAR_EXPORT = "WorldSettingsClearMultiplayerHugeWorld"
_INSTALL = "huge_multiplayer_install.inc"
_SOURCE = Path(__file__).with_name("native") / "world_settings_multiplayer" / _INSTALL
INSTALL_PATH = AI_LOADER.rsplit("/", 1)[0] + "/" + _INSTALL


def prove_huge_frame(frame: bytes, frame_sha256: str, engine_plan: bytes) -> dict:
    """Match the generated Frame against the reviewed World-only engine edits."""
    if sha256(engine_plan).hexdigest() != WORLD_ONLY_ENGINE_PLAN_SHA256:
        raise ValueError("Huge multiplayer requires the reviewed World-only engine plan.")
    if sha256(frame).hexdigest() != frame_sha256:
        raise ValueError("The Huge multiplayer Frame differs from its visibility pin.")
    image = PE(frame)
    plan = loads(engine_plan)
    edits = [row for row in plan["edits"] if row["module"] == "AnnoFrame.dll"]
    for row in edits:
        before = bytes.fromhex(row["before"])
        if image.read(row["rva"], len(before)) != before:
            raise ValueError(f"The Huge multiplayer Frame preimage differs at 0x{row['rva']:X}.")
    # The reviewed in-memory depth helper occupies slack in the last mapped
    # executable page. Its on-disk VirtualSize stays at the original value.
    for row in plan["disk_only_frame_edits"]:
        before = bytes.fromhex(row["before"])
        if image.bytes(row["file_offset"], len(before)) != before:
            raise ValueError("The Huge multiplayer Frame section layout differs.")
    return {"frame_sha256": frame_sha256, "engine_plan_sha256": WORLD_ONLY_ENGINE_PLAN_SHA256,
            "engine_edits": len(plan["edits"]), "frame_edits": len(edits)}


def apply_huge_engine(files: dict[str, bytes]) -> None:
    """Stage the existing engine transaction with a reversible byte direction."""
    loader = AI_LOADER.rsplit("/", 1)[0] + "/install_test_hooks.c"
    data = files[loader]
    data = replace(data, b"static int wsInstallState;",
                   b"static int wsInstallState;\nstatic int wsMpHugeState;",
                   "private multiplayer Huge engine state")
    data = replace(data, b"static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){",
                   b"static int wsPrepareEngineTransition(WSPatch *patches,uint32_t *patchCount,int restore){",
                   "allow the same engine plan to prepare either direction")
    data = replace(
        data,
        b'  if(!wsReadable(patch->address,patch->length)||memcmp(patch->address,edit->before,patch->length))return wsError("An expanded engine instruction differs from its inspected preimage; no changes were committed.");\n'
        b"  memcpy(patch->before,edit->before,patch->length);memcpy(patch->after,edit->after,patch->length);",
        b"  const unsigned char *before=restore?edit->after:edit->before;\n"
        b"  const unsigned char *after=restore?edit->before:edit->after;\n"
        b'  if(!wsReadable(patch->address,patch->length)||memcmp(patch->address,before,patch->length))return wsError("An expanded engine instruction differs from its inspected preimage; no changes were committed.");\n'
        b"  memcpy(patch->before,before,patch->length);memcpy(patch->after,after,patch->length);",
        "verify all expanded engine preimages in either direction",
    )
    data = replace(data, b"/* A thread inside CRT/another module can still be constructing a World.",
                   b"static int wsPrepareEngine(WSPatch *patches,uint32_t *patchCount){\n"
                   b" return wsPrepareEngineTransition(patches,patchCount,0);\n}\n"
                   b"/* A thread inside CRT/another module can still be constructing a World.",
                   "preserve the existing single-player engine preparation")
    data = replace(data, b" if(wsInstallState==1){WorldSettingsSetAILoaderHookReady(1);",
                   b' if(wsMpHugeState){wsError("Clear the multiplayer Huge engine before starting single-player.");ReleaseSRWLockExclusive(&wsInstallLock);return 0;}\n'
                   b" if(wsInstallState==1){WorldSettingsSetAILoaderHookReady(1);",
                   "prevent a competing single-player transaction")
    files[loader] = data + b'\n#include "huge_multiplayer_install.inc"\n'
    files[INSTALL_PATH] = _SOURCE.read_bytes()
