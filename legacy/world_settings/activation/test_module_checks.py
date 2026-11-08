"""Pure module-policy checks; no process access or game run."""
from pathlib import Path
import json
from module_checks import verify_modules,profile_status
HERE=Path(__file__).resolve().parent


def main():
    source=Path('C:/OriginalAnno');copy=Path('C:/MarkedCopy')
    native={n:'original-'+n for n in ['AnnoFrame.dll','AnnoScene.dll','AnnoWelt.dll','AnnoGame.dll','View.dll','CompLogic.dll','CompLogicClassic.dll']}
    private={'WorldSettingsAI/'+n:'private-'+n for n in ['CompLogic.dll','CompLogicClassic.dll']}
    inputs=dict(source=source,copy=copy,native_sha256=native,private_native_sha256=private)
    same=lambda a,b:str(a).replace('\\','/').casefold()==str(b).replace('\\','/').casefold()
    def module(name,path,digest):return dict(name=name,path=str(path),digest=digest)
    required=[module(n,source/n,v) for n,v in native.items() if n not in ['CompLogic.dll','CompLogicClassic.dll']]
    rows=[]
    def check(name,entries,accepted):
        digests={e['path']:e['digest'] for e in entries};modules={'__all__':entries}
        try:result=verify_modules(modules,inputs,same,lambda p:digests[str(p)])
        except RuntimeError:
            assert not accepted,name;result=False
        else:assert accepted and result,name
        rows.append(dict(name=name,accepted=accepted,passed=True))
    check('required native modules, no AI loaded',required,True)
    for name in ['CompLogic.dll','CompLogicClassic.dll']:
        original=module(name,source/name,native[name]);relative='WorldSettingsAI/'+name
        copied=module(name,copy/relative,private[relative])
        check('original '+name,required+[original],True)
        check('private '+name,required+[copied],True)
        check('both original and private '+name,required+[original,copied],True)
        check('foreign '+name,required+[module(name,Path('C:/Foreign')/name,native[name])],False)
        check('changed private '+name,required+[module(name,copy/relative,'modified')],False)
        check('changed original '+name,required+[module(name,source/name,'modified')],False)
    for index,item in enumerate(required):
        check('missing '+item['name'],required[:index]+required[index+1:],False)
        check('duplicate '+item['name'],required+[dict(item)],False)
        changed=[dict(e) for e in required];changed[index]['digest']='modified'
        check('changed '+item['name'],changed,False)
        changed=[dict(e) for e in required];changed[index]['path']='C:/Foreign/'+item['name']
        check('foreign '+item['name'],changed,False)
    for value in range(5):
        assert profile_status(value)==dict(ai_profile_status=value,ai_profile_validated=value!=0,
                                          validated_ai_count=value-1 if value else None)
        rows.append(dict(name='status '+str(value),accepted=True,passed=True))
    for value in [-1,5,0xffffffff,None]:
        try:profile_status(value)
        except RuntimeError:pass
        else:raise AssertionError('Invalid status accepted: '+str(value))
        rows.append(dict(name='invalid status '+str(value),accepted=False,passed=True))
    result=dict(scope=__doc__,game_executed=False,process_access=False,cases=len(rows),results=rows)
    (HERE/'module_check_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases=len(rows),passed=True,game_executed=False)))


if __name__=='__main__':main()
