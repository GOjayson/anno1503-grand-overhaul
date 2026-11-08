"""Staged climate and layout policies for the advanced in-game World screen."""
from .world_options import PRIVATE, authored, replace


def apply_planner(files: dict[str, bytes]) -> None:
    """Extend fresh staged source; never edit the historical source closure."""
    selection = PRIVATE + 'selection_policy.inc'
    marker = b'static int wsChooseBalancedFill(const WSWorldSettings*s,uint32_t count){'
    value = files[selection]
    if value.count(marker) != 1:
        raise ValueError('Reviewed climate filler function changed.')
    prefix, body = value.split(marker, 1)
    # This is deliberately the final frozen function in the reviewed include.
    if body.count(b'\n}') != 1 or not body.rstrip().endswith(b'}'):
        raise ValueError('Reviewed climate filler extent changed.')
    newline = b'\r\n' if b'\r\n' in value else b'\n'
    files[selection] = prefix + b'#include "advanced_climate.inc"' + newline
    files[PRIVATE + 'advanced_climate.inc'] = authored('advanced_climate.inc')

    layout = PRIVATE + 'balanced_layout.inc'
    files[layout] = replace(files[layout],
        b'static int wsPack(uint32_t count,uint32_t spacing){',
        b'#include "advanced_layout.inc"\n'
        b'static int wsPack(const WSWorldSettings*s,uint32_t count,uint32_t spacing){',
        'advanced layout settings')
    files[layout] = replace(files[layout],
        b' if(!wsCompactPack(count,spacing))return 0;\n wsSpreadPack(count,spacing);return 1;',
        b' if(!s||s->layoutStyle<0||s->layoutStyle>2)return 0;\n'
        b' if(s->layoutStyle==0){if(!wsCompactPack(count,spacing))return 0;wsSpreadPack(count,spacing);return 1;}\n'
        b' return wsAdvancedPack(s,count,spacing);', 'advanced layout dispatch')
    files[PRIVATE + 'advanced_layout.inc'] = authored('advanced_layout.inc')

    backend = PRIVATE + 'world_backend.c'
    files[backend] = replace(files[backend], b'wsPack(n,(uint32_t)s->spacing)',
                             b'wsPack(s,n,(uint32_t)s->spacing)', 'advanced layout call')
    files[backend] = replace(files[backend],
        b' if(pirates!=((s->factions&1u)!=0)',
        b' if(!wsAdvancedLayoutMatches(s,planCount)){wsMessage(error,cap,"The selected layout cannot preserve its central ocean.");return 0;}\n'
        b' if(pirates!=((s->factions&1u)!=0)', 'independent layout certificate')
    files[backend] = replace(files[backend],
        b'"Island size, count and spacing do not fit in the selected %u by %u world. Reduce count, island size or spacing."',
        b'"Island size, count, spacing and layout do not fit in the selected %u by %u world. Reduce them or choose another layout."',
        'layout fit diagnostic')
