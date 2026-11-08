"""Convert the selected generated artwork into installer-ready indexed pixels.

Developer dependency: Pillow. The Windows installer needs only Python's stdlib.
Rebuild with: python developer/build_icons.py
"""
import hashlib
import json
from pathlib import Path
from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]


def build():
    for name in ['game-meat', 'potatoes', 'bread', 'butcher-meat']:
        source = PACKAGE / 'assets/source' / (name + '.png')
        rgb = Image.open(source).convert('RGB').resize((50,50), Image.Resampling.LANCZOS)
        indexed = rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        palette = indexed.getpalette()
        palette += [0] * (768 - len(palette))
        bgra = bytes(v for i in range(0,768,3) for v in [palette[i+2],palette[i+1],palette[i],0])
        item = dict(format='anno1503-indexed-icon-v1', width=50, height=50,
            palette_bgra=bgra.hex(), pixels=indexed.tobytes().hex(),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        (PACKAGE / 'assets' / (name.replace('-','_') + '_icon.json')).write_text(json.dumps(item,indent=2)+'\n')
        indexed.convert('RGB').save(PACKAGE / 'assets' / (name+'.png'))
    print('Built four distinct food icons, 50x50, with native-compatible indexed pixels.')


if __name__ == '__main__': build()
