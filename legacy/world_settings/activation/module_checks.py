"""Pure path/hash policy for original modules and separately copied AI modules."""
from pathlib import Path

REQUIRED_NATIVE={"annoframe.dll","annoscene.dll","annowelt.dll","annogame.dll","view.dll"}


def profile_status(value):
    if not isinstance(value,int) or value<0 or value>4:
        raise RuntimeError('Invalid AI validation status returned by the exact runtime.')
    return dict(ai_profile_status=value,ai_profile_validated=value!=0,
                validated_ai_count=value-1 if value else None)


def verify_modules(modules,inputs,same,sha):
    source=inputs['source'];copy=inputs['copy']
    entries=modules.get('__all__')
    if entries is None:entries=[m for m in modules.values() if isinstance(m,dict)]
    private=inputs.get('private_native_sha256',{})
    for name,digest in inputs['native_sha256'].items():
        selected=[m for m in entries if m['name'].lower()==name.lower()]
        if name.lower() in REQUIRED_NATIVE and len(selected)!=1:
            raise RuntimeError('Expected exactly one inspected '+name+' module; no changes made.')
        allowed=[(source/name,digest)]
        allowed += [(copy/path,value) for path,value in private.items() if Path(path).name.lower()==name.lower()]
        for module in selected:
            matching=[value for path,value in allowed if same(module['path'],path)]
            if len(matching)!=1 or sha(module['path'])!=matching[0]:
                raise RuntimeError('Unexpected loaded '+name+' path or fingerprint; no changes made.')
    return True
