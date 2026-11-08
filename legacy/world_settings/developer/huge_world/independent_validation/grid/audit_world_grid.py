"""Recheck allocation/lifecycle/reference inventory against the exact PE text."""
from pathlib import Path
import hashlib
import json
import sys
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'WorldSettings_Work/_tools'))
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
import world_grid_patch as patch


def instructions(image, pe):
    cs = Cs(CS_ARCH_X86, CS_MODE_64)
    cs.detail = True
    cs.skipdata = True
    for section in pe.sections:
        if section.Characteristics & 0x20000000:
            for inst in cs.disasm(image[section.VirtualAddress:section.VirtualAddress + section.Misc_VirtualSize], section.VirtualAddress):
                if inst.id:
                    yield inst


def main():
    blob = (ROOT / 'AnnoWelt.dll').read_bytes()
    assert patch.sha256(blob) == patch.ORIGINAL_SHA256
    pe = pefile.PE(data=blob)
    image = pe.get_memory_mapped_image()
    plan = patch.instruction_edits()
    by_plan = {row['rva']: row for row in plan}
    ctor_calls, ctor_rip, native_sizes, old_byte_refs = [], [], [], []
    base_ctor = 0xd1de0
    count = 0
    vtable_loads = []
    previous_vtable_load = None
    vtable_stores = []
    for inst in instructions(image, pe):
        count += 1
        if previous_vtable_load:
            old_inst, old_target = previous_vtable_load
            if inst.address == old_inst.address + old_inst.size and inst.mnemonic == 'mov' and len(inst.operands) == 2 and inst.operands[0].type == X86_OP_MEM and inst.operands[1].type != X86_OP_MEM and inst.operands[1].reg == old_inst.operands[0].reg:
                vtable_stores.append(dict(load_rva=hex(old_inst.address), store_rva=hex(inst.address), vtable_rva=hex(old_target)))
        previous_vtable_load = None
        for operand in inst.operands:
            if operand.type == X86_OP_IMM:
                if inst.mnemonic == 'call' and operand.imm == base_ctor:
                    ctor_calls.append(hex(inst.address))
                if operand.imm in (0x6f00, 0x7068):
                    native_sizes.append(dict(rva=hex(inst.address), instruction=inst.mnemonic + ' ' + inst.op_str, covered=inst.address in by_plan))
            if operand.type == X86_OP_MEM:
                if operand.mem.disp == 0x240 and operand.size == 1:
                    old_byte_refs.append(inst.address)
                if operand.mem.base == X86_REG_RIP:
                    target = inst.address + inst.size + operand.mem.disp
                    if target == base_ctor:
                        ctor_rip.append(hex(inst.address))
                    if target in (0xff1d8, 0xff650):
                        vtable_loads.append(dict(rva=hex(inst.address), vtable_rva=hex(target), instruction=inst.mnemonic + ' ' + inst.op_str))
                        if inst.mnemonic == 'lea':
                            previous_vtable_load = (inst, target)
    assert ctor_calls == ['0x255f'] and not ctor_rip
    assert all(item['covered'] for item in native_sizes), native_sizes
    absolute_ctor_refs = []
    target = (pe.OPTIONAL_HEADER.ImageBase + base_ctor).to_bytes(8, 'little')
    start = 0
    while True:
        start = image.find(target, start)
        if start < 0:
            break
        absolute_ctor_refs.append(hex(start))
        start += 1
    assert not absolute_ctor_refs
    assert {row['load_rva'] for row in vtable_stores} == {'0x2565', '0xd1c85', '0xd1e23', '0xe2ba5'}, vtable_stores
    assert not any(row.address == base_ctor for row in pe.DIRECTORY_ENTRY_EXPORT.symbols)
    transformed, manifest = patch.transform_welt_grid(blob)
    outpe = pefile.PE(data=transformed)
    outimage = outpe.get_memory_mapped_image()
    remaining_old_byte = []
    new_byte = []
    for inst in instructions(outimage, outpe):
        for operand in inst.operands:
            if operand.type == X86_OP_MEM and operand.size == 1:
                if operand.mem.disp == 0x240:
                    remaining_old_byte.append(inst.address)
                if operand.mem.disp == patch.GRID_OFFSET:
                    new_byte.append(inst.address)
    assert len(new_byte) == 88
    assert set(remaining_old_byte) == {0x64653, 0x6bfa3, 0xa7c8e, 0xa84fa}
    assert len(old_byte_refs) == 92
    # Existing hook source sites themselves remain identical in each transformed payload.
    hook_results = []
    for name, src in [('original', blob), ('dev7', (ROOT / 'WorldSettings_Work/anno1503_food_world_dev7/native/AnnoWelt.world.dll').read_bytes())]:
        output, _ = patch.transform_welt_grid(src)
        srcpe, dstpe = pefile.PE(data=src), pefile.PE(data=output)
        for rva in (0xc714d, 0xdf460):
            a, b = srcpe.get_offset_from_rva(rva), dstpe.get_offset_from_rva(rva)
            assert src[a:a + 6] == output[b:b + 6]
        hook_results.append(dict(source=name, welt_hooks_preserved=2))
    result = dict(passed=True, source_sha256=patch.sha256(blob),
        executable_instructions=count, source_plan_sha256=patch.PLAN_SHA256,
        factory_export='CreateAnnoWeltInstance', factory_rva='0x21c0',
        base_constructor='0xd1de0', direct_base_constructor_calls=ctor_calls,
        base_constructor_rip_address_refs=ctor_rip,
        base_constructor_absolute_pointer_refs=absolute_ctor_refs,
        base_constructor_exported=False,
        immediate_native_world_size_refs=native_sizes,
        observed_world_allocation_paths=1, world_derived_type='server World',
        last_native_member_offset='0x7060', native_world_bytes='0x7068',
        enlarged_world_bytes=hex(patch.ALLOCATION_BYTES), appended_grid_offset=hex(patch.GRID_OFFSET),
        native_world_vtable_references=vtable_loads,
        native_world_vtable_object_stores=vtable_stores,
        vtable_object_store_coverage='factory, base constructor, base destructor, server destructor only',
        old_byte_240_refs=len(old_byte_refs), new_byte_10000_refs=len(new_byte),
        residual_old_byte_refs=[dict(rva=hex(x), reason=('stack array' if x in (0x64653, 0x6bfa3) else 'small object flag, not World')) for x in remaining_old_byte],
        native_pointer_table_offset_preserved='0x6640', existing_hooks=hook_results,
        construction_and_destructor_emulation='native_test_results.json',
        other_modules_audit='Independent huge_engine_validation lane',
        copy_reset_lifetime=dict(
            appended_allocation_owned_by_existing_factory=True,
            appended_grid_cleared_by_native_constructor_rebuild_and_both_removals=True,
            no_additional_sidecar_allocation_or_lifetime=True,
            native_server_reset_removes_and_reinserts_islands=True,
            native_free_chain_ignores_size_but_all3_metadata_updated=True,
            no_whole_world_copy_in_reviewed_constructor_factory_reset_destructor_paths=True),
        limits=['Computed references are not a formal whole-program proof.',
                'Other subsystem/navigation/rendering/save compatibility is reported by separate lanes.',
                'Actual game loading, save/reload, ship movement and play require a real game run.'],
        game_executed=False)
    (HERE / 'allocation_reference_audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=True, executable_instructions=count, source_size_refs=len(native_sizes), new_lookup_byte_refs=len(new_byte), residual_old_refs=len(remaining_old_byte))))


if __name__ == '__main__':
    main()
