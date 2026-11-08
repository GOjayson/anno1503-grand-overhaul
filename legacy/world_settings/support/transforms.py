"""The previously validated resource transformations, composed in memory in one installation."""
from decimal import Decimal
import re,struct
import formats as fm
GOOD="WILD2"
GOODS=[("NAHRUNG","0.6"),("WILD2","0.15"),("KART2","0.15"),("BROT2","0.05"),("MEAT2","0.05")]

def add_definition(data: bytes) -> bytes:
    text = data.decode("cp1252")
    if GOOD in text:
        raise fm.ModError("Game Meat is already defined")
    food_definition = re.search(
        r"(?ms)^  Id:[ \t]+NAHRUNG\r?\n.*?(?=^  Id:)", text)
    if not food_definition:
        raise fm.ModError("Cannot locate the Food definition")
    new_definition = re.sub(r"(Id:[ \t]+)NAHRUNG", r"\g<1>" + GOOD,
                            food_definition[0], count=1)
    text = text[:food_definition.end()] + new_definition + text[food_definition.end():]
    return text.encode("cp1252")

def game_labels(data: bytes) -> bytes:
    text = data.decode("cp1252")
    pattern = re.compile(r"(?ms)(^\[WARE_ROHSTOFF\]\r?\n)(.*?)(?=^\[|\Z)")
    match = pattern.search(text)
    if not match:
        raise fm.ModError("Raw-material labels are missing")
    goods = [line for line in match[2].splitlines() if line.strip()]
    if len(goods) != 21:
        raise fm.ModError("Expected 21 original raw-material labels")
    translations = {
        "eisenerz": ("Wildbret", "Wildbret-/Schmuckstand"),
        "iron ore": ("Game meat", "Game meat / jewelry stand"),
        "ijzererts": ("Wildvlees", "Wildvlees-/juwelenkraam"),
    }
    if goods[0].casefold() not in translations:
        raise fm.ModError("Unsupported text language: " + goods[0])
    good_name, stall_name = translations[goods[0].casefold()]
    addition = match[1] + match[2].rstrip("\r\n") + "\r\n" + good_name + "\r\n"
    text = text[:match.start()] + addition + text[match.end():]
    text, count = re.subn(r"(?m)^1313:[^\r\n]*", "1313:" + stall_name, text)
    if count != 1:
        raise fm.ModError("Jewelry stand label was not found exactly once")
    return text.encode("cp1252")

def game_icon_sources(data: bytes) -> bytes:
    text = data.decode("cp1252")
    for label in ["WARENICONS_ROHSTOFF", "WARENICONS_ROHSTOFF_GREY"]:
        expression = re.compile(
            r'(?ms)(Access:[ \t]*"' + label + r'"(?:(?!Access:).)*?Segments:[ \t]*)21([ \t]*,[ \t]*1)')
        text, count = expression.subn(r"\g<1>22\2", text)
        if count != 1:
            raise fm.ModError("Could not extend raw-material icon group " + label)
    return text.encode("cp1252")

def game_extend_ui(index: bytes, textures: bytes) -> tuple[bytes, bytes]:
    entries = fm.read_access(index)
    access = dict(entries)
    colour, grey, consumer = [access[n] for n in
                             ["WARENICONS_ROHSTOFF", "WARENICONS_ROHSTOFF_GREY", "WARENICONS_BEDARF"]]
    if grey - colour != 21 or consumer - grey != 21:
        raise fm.ModError("Expected the original 21-good raw-material UI layout")
    if access["WARENICONS_BEDARF_GREY"] - consumer != 15:
        raise fm.ModError("The working Fish consumer icon slot is missing")
    frames = fm.texture_frames(textures)
    if any(i not in frames for i in range(colour, consumer + 1)):
        raise fm.ModError("A raw-material icon is missing")
    for first in (colour, grey):
        fm.consumer_icon_dimensions(frames[first + 9], first + 9)

    def shifted(ident):
        return ident + int(ident >= grey) + int(ident >= consumer)

    payload = bytearray()
    for tag, start, end in fm.anno_chunks(textures):
        part = textures[start:end]
        if tag == "TEXTURE":
            ident = struct.unpack_from("<I", part, 20)[0]
            # Temporary Cattle icon (raw ID 12, ordinal 9). Fish art and all
            # other frames are preserved byte-for-byte except their IDs.
            if ident == grey:
                payload.extend(fm.reidentify_texture(frames[colour + 9], grey))
            if ident == consumer:
                payload.extend(fm.reidentify_texture(frames[grey + 9], consumer + 1))
            part = fm.reidentify_texture(part, shifted(ident))
        payload.extend(part)
    new_textures = fm.make_chunk("ANNO", bytes(payload))
    new_index = fm.make_chunk("ANNO", fm.make_chunk("ACCESS", b"".join(
        (f"{name},{shifted(ident)}".encode("ascii") + b"\0") for name, ident in entries)))
    after = fm.texture_frames(new_textures)
    if len(after) != len(frames) + 2:
        raise fm.ModError("Incorrect Game Meat icon count")
    for ident, frame in frames.items():
        if fm.reidentify_texture(after[shifted(ident)], ident) != frame:
            raise fm.ModError("An existing UI frame changed")
    return new_index, new_textures

def diet(data, mode='all'):
    text=data.decode('cp1252')
    if 'BROT2' in text or 'MEAT2' in text:
        raise fm.ModError('The Food Market resource definitions are already installed')
    text=text.replace('FISCH2','KART2')
    header,tail=text.split('[BGRUPPE]',1)
    food=re.search(r'(?ms)^  Id:[ \t]+NAHRUNG\r?\n.*?(?=^  Id:)',header)
    if not food:raise fm.ModError('Missing native Food definition')
    additions=[]
    for name,unlock in [('BROT2','INFRA_STUFE_3B'),('MEAT2','INFRA_STUFE_2B')]:
        definition=re.sub(r'(Id:[ \t]+)NAHRUNG',r'\g<1>'+name,food[0],count=1)
        definition=definition.replace('INFRA_EVER',unlock)
        additions.append(definition)
    header=header[:food.end()]+''.join(additions)+header[food.end():]
    populations,footer=tail.split('[BAUSTUFEN]',1)
    groups=re.split(r'(?m)(?=^  BGruppeNr:)',populations)
    count=0
    for i,group in enumerate(groups):
        food_need=re.search(r'(?m)^  Ware:[ \t]+NAHRUNG[^\r\n]*\r?\n[ \t]*Menge:[ \t]+([0-9.]+)[^\r\n]*\r?\n[ \t]*Priority:[^\r\n]*\r?\n[ \t]*Force:[^\r\n]*\r?\n',group)
        potato_need=re.search(r'(?m)^  Ware:[ \t]+KART2[^\r\n]*\r?\n[ \t]*Menge:[ \t]+([0-9.]+)[^\r\n]*\r?\n[ \t]*Priority:[^\r\n]*\r?\n[ \t]*Force:[^\r\n]*\r?\n',group)
        if not food_need and not potato_need:continue
        if not food_need or not potato_need:raise fm.ModError('Unpaired baseline Food/Fish needs')
        amount=Decimal(food_need[1])+Decimal(potato_need[1])
        result=[]
        for name,fraction in (GOODS if mode=='all' else [('NAHRUNG','1')]):
            block=food_need[0].replace('NAHRUNG',name)
            value=format((amount*Decimal(fraction)).normalize(),'f')
            block=re.sub(r'(Menge:[ \t]+)[0-9.]+',r'\g<1>'+value,block)
            result.append(block)
        group=group[:food_need.start()]+''.join(result)+group[food_need.end():]
        # Locate after replacement, since lengths can change.
        group=re.sub(r'(?m)^  Ware:[ \t]+KART2[^\r\n]*\r?\n[ \t]*Menge:[^\r\n]*\r?\n[ \t]*Priority:[^\r\n]*\r?\n[ \t]*Force:[^\r\n]*\r?\n',
                     '' if mode!='all' else lambda m:m[0],group,count=0)
        # The old KART2 block follows the newly inserted diet. Remove the
        # final occurrence; the new KART2 requirement remains in the diet.
        matches=list(re.finditer(r'(?m)^  Ware:[ \t]+KART2[^\r\n]*\r?\n[ \t]*Menge:[^\r\n]*\r?\n[ \t]*Priority:[^\r\n]*\r?\n[ \t]*Force:[^\r\n]*\r?\n',group))
        if mode=='all':
            if len(matches)!=2:raise fm.ModError('Expected old and new Potato requirements')
            m=matches[-1];group=group[:m.start()]+group[m.end():]
        groups[i]=group;count+=1
    if count!=5:raise fm.ModError('Expected five population classes')
    return (header+'[BGRUPPE]'+''.join(groups)+'[BAUSTUFEN]'+footer).encode('cp1252')

def food_labels(data):
    text=data.decode('cp1252')
    raw=re.search(r'(?ms)^\[WARE_ROHSTOFF\]\r?\n(.*?)(?=^\[)',text)
    names=[line for line in raw[1].splitlines() if line.strip()]
    translations={'eisenerz':('Fisch','Kartoffeln','Brot','Fleisch','Lebensmittelmarkt','Schmuckstand','Weinstand'),
                  'iron ore':('Fish','Potatoes','Bread',"Butcher's meat",'Food market','Jewelry stand','Wine stand'),
                  'ijzererts':('Vis','Aardappelen','Brood','Vlees','Voedselmarkt','Juwelenkraam','Wijnkraam')}
    values=translations.get(names[0].casefold())
    if not values or len(names)!=22:raise fm.ModError('Unsupported Game Meat label layout')
    fish,potato,bread,meat,market,jewelry,wine=values
    for group,expected,change,addition in [('WARE_ROHSTOFF',22,{},bread),('WARE_BAUMAT',4,{},meat),('WARE_BEDARF',15,{0:fish,14:potato},None)]:
        pattern=re.compile(r'(?ms)(^\['+group+r'\]\r?\n)(.*?)(?=^\[|\Z)')
        m=pattern.search(text)
        if not m:raise fm.ModError('Missing label group: '+group)
        entries=[line for line in m[2].splitlines() if line.strip()]
        if len(entries)!=expected:raise fm.ModError('Unexpected label count: '+group)
        for at,value in change.items():entries[at]=value
        if addition:entries.append(addition)
        text=text[:m.start()]+m[1]+'\r\n'.join(entries)+'\r\n\r\n'+text[m.end():]
    for ident,name in [(1310,market),(1313,jewelry),(1316,wine)]:
        text,count=re.subn(r'(?m)^'+str(ident)+r':[^\r\n]*',str(ident)+':'+name,text)
        if count!=1:raise fm.ModError('Missing market label '+str(ident))
    return text.encode('cp1252')

def food_extend_ui(index,textures):
    access=fm.read_access(index);ids=dict(access);frames=fm.texture_frames(textures)
    raw=ids['WARENICONS_ROHSTOFF'];rawgrey=ids['WARENICONS_ROHSTOFF_GREY']
    consumer=ids['WARENICONS_BEDARF'];consumergrey=ids['WARENICONS_BEDARF_GREY']
    material=ids['WARENICONS_BAUMATERIAL'];materialgrey=ids['WARENICONS_BAUMATERIAL_GREY']
    if rawgrey-raw!=22 or consumer-rawgrey!=22 or consumergrey-consumer!=15 or materialgrey-material!=4:
        raise fm.ModError('Expected the tested Game Meat icon groups')
    # Append one raw icon (Bread) and one material icon (Meat), each in
    # colour/grey. Move the existing Fish artwork onto native Food ID 26.
    material_end=materialgrey+4
    additions={rawgrey:frames[consumer],consumer:frames[consumergrey],
               materialgrey:frames[raw+9],material_end:frames[rawgrey+9]}
    swap={consumer:frames[consumer+14],consumergrey:frames[consumergrey+14],
          consumer+14:frames[consumer],consumergrey+14:frames[consumergrey]}
    def shifted(i):return i+sum(i>=p for p in additions)
    payload=[]
    for tag,a,b in fm.anno_chunks(textures):
        if tag!='TEXTURE':payload.append(textures[a:b]);continue
        ident=struct.unpack_from('<I',textures,a+20)[0]
        if ident in additions:
            new_id=ident+sum(ident>p for p in additions)
            payload.append(fm.reidentify_texture(additions[ident],new_id))
        payload.append(fm.reidentify_texture(swap.get(ident,textures[a:b]),shifted(ident)))
    new_index=fm.make_chunk('ANNO',fm.make_chunk('ACCESS',b''.join(f'{name},{shifted(ident)}\0'.encode() for name,ident in access)))
    new_tex=fm.make_chunk('ANNO',b''.join(payload))
    if len(fm.texture_frames(new_tex))!=len(frames)+4:raise fm.ModError('Food icon insertion failed')
    return new_index,new_tex
