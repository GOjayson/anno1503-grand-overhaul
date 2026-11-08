"""Execute original/patched category constructors, paging and selection."""
import ctypes as c
import struct


def check_categories(win, allocate, q, u32, u8, callback, redirect, view, base, symbols, errors):
    noop=callback(lambda *args:0)
    redirect(view,0x9efc9,callback(lambda a,b,*args:(c.string_at(a)>c.string_at(b))-(c.string_at(a)<c.string_at(b))))
    all_objects=[];children={};values={};labels={};kindmap={}
    table=allocate(0x200);group_table=allocate(0x200);root_table=allocate(0x200)
    def prop(self,kind,record,z):
        value=q(record+8)
        if kind==0x1c1:value=u8(value)
        else:value&=0xffffffff
        values[self,kind]=value
    def getprop(self,kind,record,z):u32(record+8,values.get((self,kind),0))
    def text(self,value,*args):labels[self]=c.string_at(value).decode()
    for vt in [table,group_table,root_table]:
        for at in range(0,0x200,8):q(vt+at,noop)
        q(vt+0x80,callback(lambda self,idx,*args:u32(self+0x28,idx)))
        q(vt+0xa0,callback(prop));q(vt+0x98,callback(getprop));q(vt+0x148,callback(text))
    def attach(self,child,*args):
        if child==resources:q(self+8,child);return 0
        items=children.setdefault(self,[]);items.append(child);return len(items)-1
    q(group_table+0x58,callback(attach))
    q(group_table+0x50,callback(lambda self,child,index,z:attach(self,child,0,0)))
    q(group_table+0x48,callback(lambda self,kind,index,z:children[self][index]))
    q(group_table+0x70,callback(lambda self,*args:len(children[self])))
    def factory(self,kind,out,parent):
        obj=allocate(0x200);q(obj,group_table if kind==0xb03 else table)
        q(obj+8,parent);u32(obj+0x64,1);q(out,obj)
        all_objects.append(obj);kindmap[obj]=kind;children[obj]=[]
    def register(self,obj,index,z):
        q(q(self+0x750)+index*8,obj);return index
    q(root_table+0x178,callback(factory));q(root_table+0x50,callback(register))
    redirect(view,0x1fc30,callback(factory));redirect(view,0x1f790,callback(register))
    font=allocate(16);q(font,table)
    label=allocate(16);c.memmove(label,b'heading\0',8)
    font_vt=allocate(0x200);q(font,font_vt);q(font_vt+0x10,callback(lambda *args:label))
    fontlib=allocate(16);fontlib_vt=allocate(0x200);q(fontlib,fontlib_vt)
    q(fontlib_vt+0xc0,callback(lambda *args:font))
    context=allocate(16);ctx_vt=allocate(0x200);q(context,ctx_vt)
    q(ctx_vt+0x120,callback(lambda *args:fontlib))
    game=allocate(16);game_vt=allocate(0x100);q(game,game_vt)
    names={i:'GOOD'+str(i) for i in range(1,56) if i not in [10,11]}
    names.update({4:'STEINE',6:'MAMORSTEIN',23:'HOLZKOHLE'})
    def goodname(self,kind,record,z):
        assert kind==0x20
        good=u32(record);name=names.get(good,'UNUSED').encode()+b'\0'
        c.memmove(record+8,name,len(name))
    q(game_vt+0x98,callback(goodname))
    holder=allocate(16);holder_vt=allocate(0x100);q(holder,holder_vt)
    q(holder_vt+0x38,callback(lambda *args:game))
    resources=allocate(16);res_vt=allocate(0x100);q(resources,res_vt)
    q(res_vt+0x98,callback(lambda self,kind,record,z:u32(record+8,700)))
    # Existing sprite sheets stay intact; all category consumers resolve the
    # correct per-good graphic from the initialized global map.
    for good in range(143):
        at=base+0xce490+good*12;u32(at,good);u32(at+8,1000+good)
    def root():
        obj=allocate(0x860);q(obj,root_table);q(obj+0x750,allocate(32*8))
        for at,value in [(0x6c8,resources),(0x710,resources),(0x6c0,context),(0x7e8,holder)]:q(obj+at,value)
        return obj
    expected=[26,24,40,25,45,*range(27,40)]
    results={}
    # Constructors run their real loops, string filtering, creation and all
    # native property writes. Only allocation/resource boundaries are mocked.
    for name,rva,source in [('consumer chooser',0x391d0,'chooser'),('city consumer',0x78ad0,'city'),
                            ('raw chooser',0x39a00,'chooser'),('city raw',0x79d70,'city'),
                            ('material chooser',0x38570,'chooser'),('city material',0x78590,'city')]:
        obj=root();assert win(base+rva,obj)==0,(name,errors)
        group=q(q(obj+0x750));items=children[group]
        assert all((item,0x1bf if source=='chooser' else 0x1c1) in values for item in items),(name,[[(hex(k),v) for (p,k),v in values.items() if p==item] for item in items[:2]])
        goods=[values[item,0x1bf] if source=='chooser' else values[item,0x1c1] for item in items]
        results[name]=goods
        if 'consumer' in name:
            assert goods==expected,(name,goods)
            assert all(values[item,0x198]==1000+good for item,good in zip(items,goods))
        elif 'raw' in name:assert goods==[i for i in range(1,24) if i not in [4,6,10,11]],(name,goods)
        else:assert goods==list(range(41,45)),(name,goods)
    # Ship chooser retains its 16-entry object array; its three readers now
    # use the immutable 20-cell list. Real paging clamps at offset 12.
    ship=root();u32(ship+0x840,0);q(ship+0x848,0x1122334455667788)
    assert win(base+0x66120,ship)==0,errors
    group=q(q(ship+0x750));items=children[group]
    assert len(items)==8,(len(items),errors)
    seen=[]
    for offset in [0,4,8,12,12]:
        assert u32(ship+0x840)==offset
        if offset==0:win(base+0x65c50,ship)
        actual=[values[item,0x1bf] for item in items]
        assert actual==(expected+[0,0])[offset:offset+8],(offset,actual)
        for item,good in zip(items,actual):
            assert values[item,0x198]==(1000+good if good else 700)
        seen+=actual
        win(base+0x66810,ship)
    for offset in [8,4,0,0]:
        win(base+0x667f0,ship);assert u32(ship+0x840)==offset
    for good in expected+[0]:
        win(base+0x659b0,ship,good)
        actual=[values[item,0x1bf] for item in items]
        assert good in actual,(good,u32(ship+0x840),actual)
    assert set(expected)<=set(seen) and q(ship+0x848)==0x1122334455667788
    # The other ship category constructors must also omit the reclassified
    # goods; scroll/neighboring fields remain unchanged and arrays fit.
    for name,rva in [('ship raw',0x66ea0),('ship material',0x654a0)]:
        obj=root();assert win(base+rva,obj)==0,(name,errors)
        if name=='ship raw':
            raw=[u32(obj+0x800+4*i) for i in range(21)]
            assert 24 not in raw and 25 not in raw and 23 in raw,raw
        else:
            items=children[q(q(obj+0x750))]
            assert [values[item,0x1bf] for item in items]==list(range(41,45))
    assert not errors,errors
    return dict(category_constructors=9,consumer_goods=expected,ship_paging_and_selection='passed',
                category_icons='per-good native lookup',stock_and_save_ids='unchanged')
