"""Exact History Edition ShipRM capacity patch. Parent must verify module chain."""
import struct,hashlib
PATCH_MANIFEST = {'schema': 3, 'module': 'AnnoWelt.dll', 'original_sha256': 'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9', 'original_size': 1358336, 'allowed_input_sha256_sizes': {'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9': 1358336, '059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319': 1451520, '8c3fef5ffc23303ccbb90eface8977899a03e4bbffd314e8ef9f4b92b238a48d': 1358336, '3d05583144039da2b477509b60fbfc3e70f75cad23a2a666cb8a3ecf07c94c6f': 1451520}, 'input_profiles': {'ae772ab0d06b9f4d0759197fea10affe379eb927c0609f805427e4de532f7bd9': 'original', '059ecd1dcb2139b350f50a2805d811eff89e61cead2733ca9aedb6da83058319': 'dev7', '8c3fef5ffc23303ccbb90eface8977899a03e4bbffd314e8ef9f4b92b238a48d': 'original', '3d05583144039da2b477509b60fbfc3e70f75cad23a2a666cb8a3ecf07c94c6f': 'dev7'}, 'disk_profile_edits': {'original': [], 'dev7': [{'rva': 1454492, 'rva_hex': '0x16319c', 'before': '4d800600', 'after': '59800600', 'length': 4, 'category': 'active_copied_unwind', 'reason': 'Dev7 active merged exception directory copies original records into .wsaildr. Disk profile must update this active copy too; original-loaded runtime has only the common records.'}, {'rva': 1454500, 'rva_hex': '0x1631a4', 'before': '4d80060053800600', 'after': '598006005f800600', 'length': 8, 'category': 'active_copied_unwind', 'reason': 'Dev7 active merged exception directory copies original records into .wsaildr. Disk profile must update this active copy too; original-loaded runtime has only the common records.'}]}, 'active_exception_directory_rvas': {'original': 1340596, 'dev7': 1435588}, 'output_sha256_from_original': '9b5a1c2486af7033155c470ff181df29b7c2de402191adc06556f50e8d85235b', 'machine': 34404, 'image_base': 6442450944, 'object_old_size': 15944, 'object_new_size': 24576, 'fine_helper_offset': 13800, 'original_pointer_offset': 13832, 'new_pointer_offset': 16384, 'pointer_capacity': 1024, 'pointer_bytes': 8192, 'helper_vtable_rva': 1003296, 'shared_accessor_span': [425952, 426080], 'fine_clear_span': [437269, 437351], 'backtrack_span': [437067, 437157], 'backtrack_capacity': 1024, 'backtrack_failure_rva': 437291, 'backtrack_failure_return': -1, 'labels': {'ordinary': 426018, 'rbx_saved': 426020, 'restore': 426068, 'epilog': 426073, 'end': 426079}, 'edits': [{'rva': 425952, 'rva_hex': '0x67fe0', 'before': '40574883ec20418bc0448bca9983e207448d0402418bc19941c1f80383e20741c1e00403c2c1f8034103c04898488d3cc1488b44c1204885c07532488b4918ba0002000048895c2430e8327cffff33d24889472041b800020000488bc8488bd8e8a5d80700488bc3488b5c24304883c4205fc3cccccccccccccccccccccccccc', 'after': '40574883ec208bc29983e20703c2c1f803418bd0c1fa1f83e2074103d0c1fa03c1e20403c24898488d3cc14c8d150ecf08004c3911750b4863d2488dbcd7f8090000909048895c2430488b47204885c07522488b4918ba00020000e8207cffff48894720488bc833d241b800020000e896d80700488b5c24304883c4205fc3cc', 'length': 128, 'category': 'shared_accessor', 'reason': 'Exact ShipRM vtable selects appended 32-column grid; other helper types preserve 16-column grid. Existing stack/unwind boundaries preserved.'}, {'rva': 437269, 'rva_hex': '0x6ac15', 'before': '83e20703c2c1f8034c63c88d41079983e20703c2c1f8034585c07e3685c07e32498be98bf848c1e503498d9d083600006666660f1f8400000000004c8bc533d2488bcbe88dac07004883eb804883ef0175e9', 'after': '498d8d0040000033d241b800200000e8c1ac0700eb3c0f28b424401000000f28bc2430100000b8ffffffff4881c450100000415f415d415c5f5e5d5bc3909090909090909090909090909090909090909090', 'length': 82, 'category': 'fine_clear_and_backtrack_failure', 'reason': 'One8192-byte clear at object+0x4000; complete in-frame guarded-failure epilog restoresXMM6/XMM7 and pushedGPRs, returns-1 and leavesR14 untouched. No cross-unwind-fragment tailjump.'}, {'rva': 437067, 'rva_hex': '0x6ab4b', 'before': '0f1f440000410fb641022c803c07774a488d542420498d4d10e847450000488b4c2420440fb744242a0fb7542428428d04c24c8d0c810fb781000100006603c2664189070fb78102010000664103c066418947024983c704ebab', 'after': 'bdff030000410fb641022c803c07774a85ed0f84c8000000488d542420498d4d10e83f450000488b4c2420440fb744242a0fb7542428428d04c24c8d0c818b810001000041c1e0104103c06603c24189074983c704ffcdebac90', 'length': 90, 'category': 'backtrack_bound', 'reason': '1023 append slots after firstpair: terminalcheck first, rejectbeforeanotherwrite when full, preserve original independent16-bit coordinate arithmetic. Cyclic/overlong predecessor chain returns native-1.'}, {'rva': 900510, 'rva_hex': '0xdbd9e', 'before': 'b9483e0000', 'after': 'b900600000', 'length': 5, 'category': 'object_lifetime', 'reason': 'Matching 0x6000 allocation, deleting destructor and constructor-error sized-delete.'}, {'rva': 443227, 'rva_hex': '0x6c35b', 'before': 'ba483e0000', 'after': 'ba00600000', 'length': 5, 'category': 'object_lifetime', 'reason': 'Matching 0x6000 allocation, deleting destructor and constructor-error sized-delete.'}, {'rva': 953577, 'rva_hex': '0xe8ce9', 'before': 'ba483e0000', 'after': 'ba00600000', 'length': 5, 'category': 'object_lifetime', 'reason': 'Matching 0x6000 allocation, deleting destructor and constructor-error sized-delete.'}, {'rva': 1359500, 'rva_hex': '0x14be8c', 'before': '4d800600', 'after': '59800600', 'length': 4, 'category': 'unwind', 'reason': 'Second chained range ends immediately after RBX restoration.'}, {'rva': 1359508, 'rva_hex': '0x14be94', 'before': '4d80060053800600', 'after': '598006005f800600', 'length': 8, 'category': 'unwind', 'reason': 'Final chained range follows restored RBX and covers extended epilog, before next function.'}], 'activation': 'Apply all preimages transactionally before World construction, including .pdata edits; reject partial/unknown input. Parent verifies entire input hash/chain.', 'claims': 'Native bounded emulation only until live integration tests pass.'}

def _offset(blob,rva):
    if blob[:2]!=b'MZ':raise ValueError('Not PE')
    nt=struct.unpack_from('<I',blob,0x3c)[0]
    if blob[nt:nt+4]!=b'PE\0\0':raise ValueError('Not PE')
    machine,n=struct.unpack_from('<HH',blob,nt+4)
    opt=struct.unpack_from('<H',blob,nt+20)[0]
    if machine!=0x8664 or struct.unpack_from('<H',blob,nt+24)[0]!=0x20b:raise ValueError('Exact AMD64 PE32+ required')
    for i in range(n):
        p=nt+24+opt+i*40
        vs,va,raw,off=struct.unpack_from('<IIII',blob,p+8)
        if va<=rva<va+raw:return off+rva-va
    raise ValueError('RVA outside raw sections')

def transform_welt_navigation(blob):
    """Compose onto verified original/Food/world-grid bytes using exact preimages.

    Full module identity is checked here and by the caller. All common/profile regions are
    validated before any copy is modified. Already patched and mixed state fail.
    """
    digest=hashlib.sha256(blob).hexdigest()
    if PATCH_MANIFEST['allowed_input_sha256_sizes'].get(digest)!=len(blob):raise ValueError('Unexpected navigation input fingerprint/size')
    edits=[]
    profile=PATCH_MANIFEST['input_profiles'][digest]
    for e in PATCH_MANIFEST['edits']+PATCH_MANIFEST['disk_profile_edits'][profile]:
        p=_offset(blob,e['rva']);before=bytes.fromhex(e['before'])
        if blob[p:p+len(before)]!=before:raise ValueError('Navigation preimage mismatch at '+hex(e['rva']))
        edits.append((p,bytes.fromhex(e['after'])))
    out=bytearray(blob)
    for p,after in edits:out[p:p+len(after)]=after
    return bytes(out)

def runtime_navigation_edits(max_length=32):
    """Runtime chunks. Validate every chunk before mutation; exclude whole span.

    The parent must pause other threads and reject instruction pointers anywhere
    in shared_accessor_span, backtrack_span or fine_clear_span throughout the transaction.
    """
    if not 1<=max_length<=32:raise ValueError('Invalid runtime chunk size')
    out=[]
    for e in PATCH_MANIFEST['edits']:
        before,after=bytes.fromhex(e['before']),bytes.fromhex(e['after'])
        for k in range(0,len(before),max_length):
            out.append(dict(rva=e['rva']+k,before=before[k:k+max_length].hex(),after=after[k:k+max_length].hex(),category=e['category']))
    return out
