"""Bounded direct AMD64 PE export parsing; no third-party Python dependency."""
import struct


def exports(data, required):
    def unpack(fmt, at):
        if at < 0 or at + struct.calcsize(fmt) > len(data):
            raise ValueError("PE structure leaves the file")
        return struct.unpack_from(fmt, data, at)
    if data[:2] != b"MZ": raise ValueError("Missing DOS signature")
    pe, = unpack("<I",60)
    if data[pe:pe+4] != b"PE\0\0": raise ValueError("Missing PE signature")
    machine,count = unpack("<HH",pe+4)
    optional_size, = unpack("<H",pe+20)
    optional = pe+24
    magic, = unpack("<H",optional)
    if machine != 0x8664 or magic != 0x20b or not 1 <= count <= 96 or optional_size < 120:
        raise ValueError("Expected bounded AMD64 PE32+ image")
    image_size, = unpack("<I",optional+56)
    if not image_size: raise ValueError("Empty PE image")
    directory_count, = unpack("<I",optional+108)
    if not directory_count: raise ValueError("Missing PE export directory")
    export_rva,export_size = unpack("<II",optional+112)
    if not export_rva or export_size < 40 or export_rva+export_size > image_size:
        raise ValueError("Invalid PE export range")
    sections=[]
    for i in range(count):
        at=optional+optional_size+i*40
        virtual_size,rva,raw_size,raw = unpack("<IIII",at+8)
        flags, = unpack("<I",at+36)
        if raw+raw_size > len(data): raise ValueError("PE section leaves the file")
        extent=max(virtual_size,raw_size)
        if rva >= image_size or extent > image_size-rva:
            raise ValueError("PE section leaves SizeOfImage")
        sections.append((rva,virtual_size,raw_size,raw,flags))
    def offset(rva,size):
        if rva < 0 or size < 0 or rva > image_size or size > image_size-rva:
            raise ValueError("PE mapped span leaves SizeOfImage")
        for base,virtual,raw_size,raw,flags in sections:
            delta=rva-base
            if 0 <= delta and size >= 0 and delta+size <= raw_size:
                return raw+delta
        raise ValueError("Unmapped PE export data")
    fields=unpack("<IIHHIIIIIII",offset(export_rva,40))
    function_count,name_count,functions,names,ordinals=fields[6:]
    if not 1 <= function_count <= 4096 or name_count > function_count:
        raise ValueError("Unbounded PE export table")
    function_at=offset(functions,function_count*4)
    name_at=offset(names,name_count*4)
    ordinal_at=offset(ordinals,name_count*2)
    values={}
    for i in range(name_count):
        string_rva, = unpack("<I",name_at+i*4)
        chars=[]
        for j in range(256):
            value=data[offset(string_rva+j,1)]
            if not value: break
            chars.append(value)
        else: raise ValueError("Unterminated PE export name")
        name=bytes(chars).decode("ascii")
        ordinal,=unpack("<H",ordinal_at+i*2)
        if ordinal >= function_count or name in values: raise ValueError("Invalid PE export ordinal/name")
        address,=unpack("<I",function_at+ordinal*4)
        if export_rva <= address < export_rva+export_size: continue
        if not 0 < address < image_size or not any(base <= address < base+min(virtual,raw_size) and flags&0x20000000
                   for base,virtual,raw_size,raw,flags in sections):
            raise ValueError("PE export is not in executable image data")
        values[name]=address
    if not set(required) <= values.keys(): raise ValueError("Runtime lacks required activation exports")
    return values
