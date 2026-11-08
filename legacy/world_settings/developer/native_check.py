"""Execute native selectors, worker purchases, click dispatch and overlay drawing.

Spatial/object lookup, graphics submission and OS services are test doubles;
the decisions, transfer plumbing, command validation and house updates execute
the game's original/patched x64 instructions. This is not a Windows game run.
"""
import ctypes as c
import base64
import json
import mmap
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import food_mod as mod
from pe_builder import pe_info


def execute(modules):
    keep=[];errors=[]
    def allocate(size):
        value=c.create_string_buffer(size);keep.append(value);return c.addressof(value)
    def q(at,value=None):
        if value is None:return c.c_uint64.from_address(at).value
        c.c_uint64.from_address(at).value=value
    def u32(at,value=None):
        if value is None:return c.c_uint32.from_address(at).value
        c.c_uint32.from_address(at).value=value
    def u16(at,value=None):
        if value is None:return c.c_uint16.from_address(at).value
        c.c_uint16.from_address(at).value=value
    def u8(at,value=None):
        if value is None:return c.c_uint8.from_address(at).value
        c.c_uint8.from_address(at).value=value
    def machine(code):
        memory=mmap.mmap(-1,4096,prot=7);memory[:len(code)]=code;keep.append(memory)
        return c.addressof(c.c_char.from_buffer(memory))
    # SysV -> Windows x64, including the 32-byte shadow area and alignment.
    wrapper=machine(bytes.fromhex('4889f84d89c14989c84889f14883ec28ffd04883c428c3'))
    call=c.CFUNCTYPE(c.c_uint64,c.c_void_p,c.c_uint64,c.c_uint64,c.c_uint64,c.c_uint64)(wrapper)
    def win(fn,*args):return call(fn,*(list(args)+[0]*(4-len(args))))
    callbacks=[]
    def callback(function):
        def safe(a,b,d,e):
            try:return function(a,b,d,e) or 0
            except Exception as exc:errors.append(repr(exc));return 0
        native=c.CFUNCTYPE(c.c_uint64,c.c_uint64,c.c_uint64,c.c_uint64,c.c_uint64)(safe)
        callbacks.append(native)
        # Windows -> SysV. Preserve Windows' nonvolatile RSI/RDI.
        code=bytes.fromhex('57564883ec084889cf4889d64c89c24c89c948b8')
        code+=struct.pack('<Q',c.cast(native,c.c_void_p).value)+bytes.fromhex('ffd04883c4085e5fc3')
        return machine(code)
    mapped={}
    for name,(data,symbols) in modules.items():
        pe,opt,table,sections,offset=pe_info(data)
        size=struct.unpack_from('<I',data,opt+56)[0]
        memory=mmap.mmap(-1,size,prot=7)
        for section,vs,rva,rs,raw,*rest in sections:memory[rva:rva+rs]=data[raw:raw+rs]
        keep.append(memory);base=c.addressof(c.c_char.from_buffer(memory))
        mapped[name]=(memory,base,{key:base+value for key,value in symbols.items()})
    game,game_base,g=mapped['AnnoGame.dll'];world,world_base,w=mapped['AnnoWelt.dll'];view,view_base,v=mapped['View.dll']
    frame,frame_base,f=mapped['AnnoFrame.dll']
    noop=callback(lambda *args:0)
    # Replace only the original game functions called by our helpers.
    def redirect(memory,rva,address):memory[rva:rva+12]=b'\x48\xb8'+struct.pack('<Q',address)+b'\xff\xe0'
    notices=[]
    redirect(world,0x842e0,callback(lambda self,old,new,z:notices.append((old,new)) or 0))
    definition=allocate(0x300);def_vtable=allocate(0x200)
    q(definition,def_vtable);q(def_vtable+0x160,g['food_get_ware'])
    q(def_vtable+0x1c0,game_base+0x4290);u8(definition+0x202,2)
    q(def_vtable+0xc0,callback(lambda *args:0x21))
    u8(definition+0x20e,26);u8(definition+0x20f,28)
    product=allocate(0x80);prod_vtable=allocate(0x280)
    q(product,prod_vtable);q(product+0x20,definition)
    q(product+0x30,0x1122334455667788)
    q(prod_vtable+0xf0,world_base+0xae30)
    q(prod_vtable+0x148,world_base+0x76ae0)
    owner=allocate(0x800);owner_vt=allocate(0x300);q(owner,owner_vt);q(product+0x18,owner)
    class Stock:
        def __getitem__(self,good):return u32(owner+0x478+good*12)
        def __setitem__(self,good,value):u32(owner+0x478+good*12,value)
    stock=Stock()
    for good in [26,28,24,40,25,45]:stock[good]=(good+10)*256
    q(prod_vtable+0x150,world_base+0x76af0)
    q(owner_vt+0x100,world_base+0xb4f20)
    q(owner_vt+0x118,world_base+0xb4fb0);q(prod_vtable+0x160,world_base+0x81000)
    q(prod_vtable+0x190,w['market_enabled'])
    q(prod_vtable+0x198,w['market_set_enabled'])
    q(prod_vtable+0xb0,callback(lambda *args:12));q(prod_vtable+0xb8,callback(lambda *args:34))
    goods=[26,28,24,40,25,45]
    assert [win(g['food_get_ware'],definition,i) for i in range(8)]==goods+[0,0]
    checks=0
    for mask in range(64):
        win(w['market_load_flags'],product,mask)
        assert win(w['market_pack_flags'],product)==mask
        for i,good in enumerate(goods):
            assert win(w['market_enabled'],product,good)==((mask>>i)&1)
        assert win(w['market_enabled'],product,142)==bool(mask)
        assert win(w['market_enabled'],product,255)==0
        assert q(product+0x30)==0x1122334455667788
        checks+=10
    # Other two-slot markets expose no extra goods and never alias slot 2
    # onto the raw-material bytes following the original two-byte array.
    u8(definition+0x20e,37);u8(definition+0x20f,39);u8(definition+0x210,99)
    assert [win(g['food_get_ware'],definition,i) for i in range(8)]==[37,39,0,0,0,0,0,0]
    u8(definition+0x20e,26);u8(definition+0x20f,28)
    win(w['market_load_flags'],product,63)

    # Native house scoring, original two-good regression, and all six needs.
    house=allocate(0xb0);house_vt=allocate(0x240);q(house,house_vt)
    needs=allocate(0x140);records=allocate(143*26);q(house+0x48,needs);q(needs+0x118,records)
    u8(needs+2,6);c.memset(needs+3,255,96)
    u16(house+0x50,64);u16(house+0x52,64)
    for i,good in enumerate(goods):
        u8(needs+good+3,i);u8(needs+0x64+i*4,good);u16(needs+0x66+i*4,16)
    out=allocate(4)
    def want_only(index):
        for j in range(6):u16(house+0x54+j*2,0 if index==j else 1000)
        for good in goods:stock[good]=100*256
        win(w['market_load_flags'],product,63)
    for i,good in enumerate(goods):
        want_only(i);u32(out,999)
        old=c.c_int32(win(world_base+0x88b10,house,product,out)).value
        assert old==(128 if i<2 else -1),(good,old)
        assert win(w['house_choose_good'],house,product,out)==128 and u32(out)==good
        win(w['market_set_enabled'],product,good,0)
        assert c.c_int32(win(w['house_choose_good'],house,product,out)).value==-1
        win(w['market_set_enabled'],product,good,1)
        stock[good]=1
        assert c.c_int32(win(w['house_choose_good'],house,product,out)).value==-1
        stock[good]=2
        assert win(w['house_choose_good'],house,product,out)==128 and u32(out)==good
        u8(needs+good+3,255)
        assert c.c_int32(win(w['house_choose_good'],house,product,out)).value==-1
        u8(needs+good+3,i)
        u16(needs+0x66+i*4,0)
        assert c.c_int32(win(w['house_choose_good'],house,product,out)).value==-1
        u16(needs+0x66+i*4,16)
        u16(house+0x52,0)
        assert c.c_int32(win(w['house_choose_good'],house,product,out)).value==-1
        u16(house+0x52,64)
    # Reproduce the old raw/material sale guard before testing its repair.
    saved_guard=world[0xb4fb0:0xb4fb6]
    world[0xb4fb0:0xb4fb6]=bytes.fromhex('8d42e683f80e')
    for good in [24,25,45]:
        before=stock[good];win(world_base+0x81000,product,good,3,7)
        assert stock[good]==before
    world[0xb4fb0:0xb4fb6]=saved_guard
    # Execute the game's complete worker-at-market routine, including its
    # selector call, stock removal, carrying slot, then native house receipt.
    q(house_vt+0x1b0,w['house_choose_good']);q(house_vt+0x150,world_base+0x88a60)
    q(house_vt+0x38,callback(lambda *args:owner))
    identity=allocate(1);u8(identity,7);q(house_vt+0x118,callback(lambda *args:identity))
    collection=allocate(16);collection_vt=allocate(0x30);q(collection,collection_vt)
    q(collection_vt+0x10,callback(lambda *args:product));q(owner_vt+0xc8,callback(lambda *args:collection))
    worker=allocate(0x80);worker_vt=allocate(0x200);q(worker,worker_vt);q(house+0x28,worker)
    job=allocate(16);job_vt=allocate(0x180);q(job,job_vt)
    q(job_vt+0x118,callback(lambda *args:1));q(job_vt+0x110,callback(lambda *args:32))
    cargo=allocate(16);cargo_vt=allocate(0x30);q(cargo,cargo_vt)
    for at,rva in [(0,0x5990),(8,0xc8e0),(0x10,0xc8f0),(0x18,0x59a0)]:q(cargo_vt+at,world_base+rva)
    q(worker_vt+0x40,callback(lambda *args:house));q(worker_vt+0xf8,callback(lambda *args:job))
    q(worker_vt+0x110,callback(lambda *args:cargo));site=allocate(16);u16(site+8,12);u16(site+10,34)
    transfers=[]
    for i,good in enumerate(goods):
        want_only(i);u8(cargo+8,0);u16(cargo+10,0)
        before=stock[good]
        sale_record=owner+good*12
        old_sales=u16(sale_record+0x47c);old_removed=u16(sale_record+0x480)
        assert win(world_base+0x8bb50,site,worker)==1
        amount=u16(cargo+10)
        assert u8(cargo+8)==good and amount>0,(good,amount,u8(cargo+8))
        assert stock[good]==before-amount
        assert u16(sale_record+0x47c)==old_sales+amount
        assert u16(sale_record+0x480)==old_removed+amount
        assert c.c_int32(win(w['house_choose_good'],house,product,out)).value==-1
        assert win(world_base+0x88aa0,house,good,amount)==amount
        assert u16(house+0x54+i*2)==amount*16
        transfers.append((good,amount))
    q(house+0x28,0)
    for good in goods:stock[good]=(good+10)*256

    ui=allocate(0x808);ui_vtable=allocate(0x200);vector=allocate(32*8)
    q(ui,ui_vtable);q(ui+0x750,vector);q(ui+0x758,vector+16*8);q(ui+0x760,vector+32*8)
    for at in [0x6c8,0x710,0x730,0x738]:q(ui+at,allocate(64))
    widgets={};sizes={};positions={};properties={};parents={};kinds={}
    gadget_table=allocate(0x200)
    def prop(self,kind,record,z):
        value=q(record+8)
        if kind in {0x1c4,0x1c9}:value=c.string_at(value).decode('cp1252')
        else:value&=0xffffffff
        properties[(self,kind)]=value
        if kind==0x1c4:
            ptr=allocate(len(value)+1);c.memmove(ptr,value.encode()+b'\0',len(value)+1);q(self+0xa8,ptr)
        elif kind==0x1c6:u32(self+0xa4,value)
    q(gadget_table+0x80,view_base+0x62c0);q(gadget_table+0x88,view_base+0x62d0)
    def parent_widget(self,parent,*args):
        parents.setdefault(self,[]).append(parent)
        if kinds.get(self)==0xb1c:q(self+8,parent)
    q(gadget_table+0x58,callback(parent_widget))
    def size_widget(self,x,y,z):
        sizes[self]=(x&0xffffffff,y&0xffffffff);u32(self+0x20,x);u32(self+0x24,y)
    def position_widget(self,x,y,z):
        positions[self]=(c.c_int32(x).value,c.c_int32(y).value);u32(self+0x18,x);u32(self+0x1c,y)
    q(gadget_table+0xa8,callback(size_widget))
    q(gadget_table+0xc0,callback(position_widget))
    q(gadget_table+0xa0,callback(prop))
    overlay_table=allocate(0x180)
    q(overlay_table+0xa0,view_base+0x11150)
    q(overlay_table+0x58,callback(lambda self,parent,*args:q(self+8,parent)))
    q(overlay_table+0x100,view_base+0x3640)
    overlay_draws=[]
    q(overlay_table+0x138,callback(lambda self,*args:overlay_draws.append((u32(self+0xa0),q(self+8)))))
    graphics=allocate(16);graphics_table=allocate(0x180);q(graphics,graphics_table)
    submissions=[]
    def submit(self,context,tag,z):
        submissions.append(context)
        assert context,'An uninitialized red-cross resource reached drawing'
    q(graphics_table+0x100,callback(submit));q(graphics_table+0x108,noop)
    def gadget():
        ptr=allocate(0x100);q(ptr,gadget_table);q(ptr+0xc8,graphics)
        q(ptr+0x78,q(ui+0x710))
        cross=allocate(0xb0);q(cross,overlay_table);q(ptr+0xb8,cross)
        u32(cross+0xa0,65535);u32(ptr+0x64,1);u8(ptr+0xb0,1)
        return ptr
    def make_widget(index):
        ptr=gadget();u32(ptr+0x28,index);q(vector+index*8,ptr);widgets[index]=ptr;return ptr
    for i in range(16):make_widget(i)
    for i,rva in [(6,0x54000),(7,0x55dd0)]:
        q(widgets[i]+0x50,view_base+rva);q(widgets[i]+0x58,ui)
    # Original first-two native widgets already have a resolved overlay.
    for i in [6,7]:win(view_base+0x58d0,widgets[i],777)
    def factory(self,kind,out,parent):
        assert kind in {0xb07,0xb1c,0xb17}
        ptr=gadget();q(out,ptr);kinds[ptr]=kind
    def register(self,ptr,index,z):
        assert 16<=index<32
        q(vector+index*8,ptr);widgets[index]=ptr;q(ui+0x758,vector+(index+1)*8);return index
    q(ui_vtable+0x178,callback(factory));q(ui_vtable+0x50,callback(register))
    resource_vt=allocate(0x100);q(q(ui+0x710),resource_vt)
    def find_access(self,kind,record,z):
        assert kind==10 and c.string_at(record+8)==b'MARKTSTAND_RAHMEN_1'
        u32(record+8,883)
    q(resource_vt+0x98,callback(find_access))
    # Run the game's actual root draw order and tGadText draw routine.
    text_resource_vt=allocate(0x200);q(q(ui+0x730),text_resource_vt)
    for at in [0xb0,0xd0,0xf0]:q(text_resource_vt+at,noop)
    font=allocate(0x20);font_vt=allocate(0x100);font_inner_vt=allocate(0x100)
    q(font,font_vt);q(font+8,font_inner_vt);u32(font_inner_vt+4,0);q(font_inner_vt+0xf0,noop)
    q(font_vt,noop);q(font_vt+0x20,noop)
    drawing={'widget':0};paint=[]
    def draw_text(self,text,*args):
        gadget=drawing['widget'];x,y=positions[gadget]
        if x>=0 and y>=0:paint.append(('text',gadget,c.string_at(text).decode()))
    q(font_vt+0x10,callback(draw_text))
    redirect(view,0x9efb1,callback(lambda *args:font))
    def draw_widget(self,*args):
        if self not in positions:return
        drawing['widget']=self
        if kinds.get(self)==0xb1c:win(view_base+0x4c90,self)
        elif kinds.get(self)==0xb17 and positions[self][0]>=0:paint.append(('frame',self,''))
    q(gadget_table+0x138,callback(draw_widget))
    q(ui_vtable+0x188,noop);u32(ui+0x780,0xffffffff)
    for i in [8,9]:kinds[widgets[i]]=0xb1c;q(widgets[i]+8,q(ui+0x730))
    def visible_prices():
        paint.clear();win(view_base+0x1f150,ui);visible={}
        for kind,gadget,text in paint:
            x,y=positions[gadget]
            if kind=='text':visible[gadget]=text
            else:
                width,height=sizes[gadget]
                for target in list(visible):
                    tx,ty=positions[target]
                    if x<=tx<x+width and y<=ty<y+height:del visible[target]
        return visible
    redirect(view,0x54ef0,noop)
    redirect(view,0x54300,callback(lambda self,prod,*args:q(self+0x7f8,prod)))
    for rva in [0x4a910,0x4ab90,0x54440]:redirect(view,rva,noop)
    # The imported integer formatter is replaced with an ABI-correct mock.
    def itoa(value,out,radix,z):
        assert radix==10
        c.memmove(out,str(value).encode()+b'\0',len(str(value))+1);return out
    q(view_base+0xa1288,callback(itoa))
    for good in range(143):
        at=view_base+0xce490+good*12;u32(at,good);u32(at+8,1000+good)
        label=c.create_string_buffer(('good-'+str(good)).encode());keep.append(label)
        q(view_base+0xce010+good*8,c.addressof(label))
    bus=allocate(16);bus_table=allocate(0x200);q(bus,bus_table)
    holder=allocate(0x50);holder_table=allocate(0x200);q(holder,holder_table);q(ui+0x7e8,holder);q(holder+0x40,bus)
    q(holder_table+0x140,frame_base+0x24200)
    # Use the actual local command function: it must authorize all six goods.
    q(bus_table+0xd8,frame_base+0x78630)
    # The old command validator silently rejected slot 2. Check that this
    # regression is real and that the new native path permits the command.
    saved_count_call=frame[0x78667:0x7866e]
    frame[0x78667:0x7866e]=bytes.fromhex('41ff92c0010000')
    win(frame_base+0x78630,bus,24,0,product)
    assert win(w['market_enabled'],product,24)==1
    frame[0x78667:0x7866e]=saved_count_call
    win(frame_base+0x78630,bus,24,0,product)
    assert win(w['market_enabled'],product,24)==0
    win(frame_base+0x78630,bus,24,1,product)
    # Network games serialize the same good and enabled fields. Execute the
    # original encoder and exercise the separate patched decoder count gate.
    network=allocate(16);network_vt=allocate(0x300);q(network,network_vt)
    packets=[]
    q(network_vt+0x288,callback(lambda self,packet,size,z:packets.append(c.string_at(packet,size))))
    for good in goods:
        for enabled in [0,1]:
            win(frame_base+0x7d340,network,good,enabled,product)
            assert packets[-1]==struct.pack('<BHHBH',0x74,12,34,enabled,good)
    assert win(f['market_command_count'],definition,0)==6
    assert win(f['market_command_count'],definition,1)==0
    # Price inputs are varied below; the helper follows the real table formula.
    world_obj=allocate(16);world_vt=allocate(0x200);q(world_obj,world_vt)
    q(holder_table+0x120,callback(lambda *args:world_obj))
    city=allocate(16);city_vt=allocate(0x200);q(city,city_vt)
    indices={'climate':0,'level':0}
    q(world_vt+0x120,callback(lambda *args:city))
    q(world_vt+0xf0,callback(lambda *args:indices['level']))
    q(city_vt+0x190,callback(lambda *args:indices['climate']))
    game_data=allocate(16);data_vt=allocate(0x100);q(game_data,data_vt);q(ui+0x7c8,game_data)
    prices=allocate(16);prices_vt=allocate(0x30);q(prices,prices_vt)
    q(data_vt+0xe0,callback(lambda *args:prices));q(prices_vt+0x10,callback(lambda *args:records))
    for good in range(56):
        for k in range(7):u16(records+good*26+4+k*2,good*10+k)
        for k in range(4):u16(records+good*26+18+k*2,20+k*3)
    # Actual city accounting, including direct native cash credit and clearing
    # the pending sale counters. No stock or revenue decision is mocked.
    player=allocate(0xc0);q(player,world_base+0xfabe0);q(player+0x20,prices)
    island=allocate(16);island_vt=allocate(0x200);q(island,island_vt)
    q(island_vt+0x38,callback(lambda *args:world_obj))
    q(island_vt+0x190,callback(lambda *args:indices['climate']))
    q(owner+0x20,island);q(owner+0x28,player)
    revenue_goods=list(range(26,41))+[24,25,45]
    income_checks=0
    for climate in range(7):
        for level in range(4):
            indices.update(climate=climate,level=level)
            u16(owner+0xe,0);u32(player+0x98,0)
            expected=128
            for i,good in enumerate(revenue_goods):
                quantity=256+i;u16(owner+good*12+0x47c,quantity)
                expected+=(good*10+climate+20+level*3)*quantity
            u16(owner+12*12+0x47c,123)
            win(world_base+0xad350,owner,2000)
            assert u32(player+0x98)==expected//256,(climate,level,u32(player+0x98),expected//256)
            assert all(u16(owner+good*12+0x47c)==0 for good in revenue_goods)
            assert u16(owner+12*12+0x47c)==123
            income_checks+=1
    # Run the actual 0.4.0 creator and click/draw path once. Its new buttons
    # leave the overlay in the constructor's unresolved state, which reaches
    # rendering as a null resource. Catch that boundary error in this harness.
    legacy,legacy_base,lv=mapped['LegacyView.dll']
    redirect(legacy,0x54ef0,noop)
    assert win(lv['ui_create'],ui)==0
    broken=widgets[16]
    assert q(q(broken+0xb8)+8)==0 and u32(q(broken+0xb8)+0xa0)==65535
    q(ui+0x7f8,product)
    win(legacy_base+0x51e0,broken,0,1,1)
    win(legacy_base+0x59f0,broken,0)
    assert submissions[-1]==0 and 'uninitialized red-cross' in errors[-1]
    errors.pop();overlay_draws.pop()
    for index in range(16,20):del widgets[index]
    q(ui+0x758,vector+16*8)
    win(w['market_set_enabled'],product,24,1)
    oldprice,oldprice_base,pv=mapped['PreviousView.dll']
    redirect(oldprice,0x54ef0,noop);q(oldprice_base+0xa1288,q(view_base+0xa1288))
    assert win(pv['ui_create'],ui)==0
    win(pv['ui_prices'],ui,1)
    assert visible_prices()=={},'0.4.1 frames must reproduce all six hidden prices'
    assert len([x for x in paint if x[0]=='text'])==6
    assert win(v['ui_create'],ui)==0
    assert len(widgets)==32
    assert win(v['ui_set_prod'],ui,product)==0
    for i,(good,index) in enumerate(zip(goods,[6,7,16,17,18,19])):
        gadget=widgets[index]
        assert sizes[gadget]==(50,50)
        assert positions[gadget]==(22+(i%3)*75,278+(i//3)*84)
        assert properties[gadget,0x198]==1000+good
        assert properties[gadget,0x1c4]==str(good+10)
        assert properties[gadget,0x1c9]=='good-'+str(good)
        if i>=2:
            assert parents[gadget]==[q(ui+0x710),q(ui+0x738)]
            assert q(gadget+0x58)==ui
            assert u32(q(gadget+0xb8)+0xa0)==777 and q(q(gadget+0xb8)+8)==q(ui+0x710)
        # The real native click event sets the crossed-out state before
        # dispatching, so execute the actual draw path as well, for all six.
        win(view_base+0x51e0,gadget,0,1,1)
        assert win(w['market_enabled'],product,good)==0
        u32(gadget+0xa0,1)
        win(view_base+0x59f0,gadget,0)
        assert overlay_draws[-1]==(777,q(ui+0x710))
        win(view_base+0x51e0,gadget,0,1,0)
        assert win(w['market_enabled'],product,good)==1
    for index in [2,3]: assert positions[widgets[index]]==(-10000,-10000)
    assert positions[widgets[15]]==(-10000,-10000)
    assert positions[widgets[4]]==(60,133) and positions[widgets[5]]==(55,123)
    assert all(positions[widgets[i]]==(-10000,-10000) for i in [8,9])
    for climate in range(7):
        for level in range(4):
            indices.update(climate=climate,level=level);win(v['ui_tick'],ui)
            for good,index in zip(goods,[26,27,28,29,30,31]):
                assert properties[widgets[index],0x1c4]==str(good*10+climate+20+level*3)
    for i,index in enumerate([26,27,28,29,30,31]):
        x,y=positions[widgets[index]];bx,by=positions[widgets[20+i]]
        assert (bx,by)==(12+(i%3)*75,328+(i//3)*84)
        assert sizes[widgets[20+i]]==(71,34) and properties[widgets[20+i],0x198]==883
        assert sizes[widgets[index]]==(40,15)
        assert bx<=x and by<=y and x+40<=bx+71 and y+15<=by+34<453
    rendered=visible_prices()
    assert len(rendered)==6 and set(rendered)=={widgets[i] for i in range(26,32)},(paint,rendered)
    assert all(rendered[widgets[i]]==properties[widgets[i],0x1c4] for i in range(26,32))
    # Layout updates add a nonzero panel origin exactly once. Every icon
    # clears the native preview, income strip and maintenance footer.
    c.c_float.from_address(ui+0x6f8).value=17.0
    c.c_float.from_address(ui+0x6fc).value=29.0
    win(v['ui_layout'],ui,0,0)
    rects=[]
    for i,index in enumerate([6,7,16,17,18,19]):
        x,y=positions[widgets[index]]
        assert (x,y)==(39+(i%3)*75,307+(i//3)*84)
        rects.append((x-17,y-29,x-17+50,y-29+50))
    for x1,y1,x2,y2 in rects:
        assert 0<=x1<x2<=245 and 266<y1<y2<=412
    assert all(a[2]<=b[0] or b[2]<=a[0] or a[3]<=b[1] or b[3]<=a[1]
               for i,a in enumerate(rects) for b in rects[i+1:])
    assert positions[widgets[20]]==(29,357) and positions[widgets[25]]==(179,441)
    c.c_float.from_address(ui+0x6f8).value=0
    c.c_float.from_address(ui+0x6fc).value=0
    win(v['ui_tick'],ui)
    for index in [16,17,18,19]:assert properties[widgets[index],0x1ad]==0
    # Selecting an ordinary two-slot stand hides all extra controls.
    u8(definition+0x20e,37);u8(definition+0x20f,39)
    win(v['ui_layout'],ui,0,0)
    for index in [16,17,18,19]:
        assert sizes[widgets[index]]==(0,0)
        assert positions[widgets[index]]==(-10000,-10000)
    assert positions[widgets[6]]==(45,331) and positions[widgets[7]]==(153,331)
    assert positions[widgets[2]]==(60,286) and positions[widgets[3]]==(168,286)
    assert positions[widgets[15]]==(35,383)
    assert positions[widgets[4]]==(60,153) and positions[widgets[5]]==(55,143)
    assert positions[widgets[8]]==(70,393) and positions[widgets[9]]==(178,393)
    assert sizes[widgets[8]]==sizes[widgets[9]]==(50,15)
    assert win(f['market_command_count'],definition,0)==2
    assert c.c_int32(win(w['house_choose_good'],house,product,out)).value==c.c_int32(win(world_base+0x88b10,house,product,out)).value
    for index in range(20,32):assert positions[widgets[index]]==(-10000,-10000)
    from category_check import check_categories
    category_results=check_categories(win,allocate,q,u32,u8,callback,redirect,view,view_base,v,errors)
    assert not errors,errors
    return {**category_results,'flag_and_getter_checks':checks,'visible_slots_tested':6,'native_sale_toggle_commands':12,
            'native_worker_transfers':transfers,'original_selector_regression':'reproduced',
            'original_stock_guard_regression':'reproduced','original_command_count_regression':'reproduced',
            'native_city_income_checks':income_checks,'native_network_packets':len(packets),
            'original_red_cross_regression':'reproduced with the 0.4.0 creator',
            'native_price_text_draws':6,'original_hidden_price_regression':'reproduced with 0.4.1 creator',
            'red_cross_draws':len(overlay_draws),'price_values_checked':7*4*6,
            'original_market_layout_preserved':True,'compact_layout_and_panel_origin':'passed',
            'callbacks_and_shadow_space':'passed'}


if __name__=='__main__':
    directory=Path(sys.argv[1])
    spec=json.loads((Path(__file__).resolve().parents[1]/'food_patch.json').read_bytes())
    modules={m['name']:((directory/m['name']).read_bytes(),m['symbols']) for m in spec['native_modules'] if 'symbols' in m}
    # Reconstruct only for the isolated regression run, from reviewed inverse
    # deltas; neither package contains a redistributed original game DLL.
    prior=json.loads((Path(__file__).parent/'compat-0.4.0.json').read_bytes())
    old_view=next(e for e in prior['native_modules'] if e['name']=='View.dll')
    source=old_view['sources']['vanilla'];change=old_view['changes'][source]
    length=change['result_size']-len(base64.b64decode(change['append_base64']))
    original=bytearray(modules['View.dll'][0][:length])
    current_view=next(e for e in spec['native_modules'] if e['name']=='View.dll')
    for patch in current_view['changes'][source]['patches']:
        at=patch['offset'];before=bytes.fromhex(patch['before'])
        assert at+len(before)<=length
        original[at:at+len(before)]=before
    assert mod.fm.sha(original)==source
    modules['LegacyView.dll']=(mod.apply_native(bytes(original),old_view),old_view['symbols'])
    prior041=json.loads((Path(__file__).parent/'compat-0.4.1.json').read_bytes())
    entry=next(e for e in prior041['native_modules'] if e['name']=='View.dll')
    modules['PreviousView.dll']=(mod.apply_native(bytes(original),entry),entry['symbols'])
    print(json.dumps(execute(modules)))
