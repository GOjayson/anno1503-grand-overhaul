"""Anno 1503 modular installer and feature-profile commands."""
import argparse
import json
from pathlib import Path
import sys

from . import lan_preflight
from .features import default_catalog
from .profile import ProfileError,default_profile,load_profile,save_profile,selected_features


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
    lan=sub.add_parser('lan',help='Run the experimental two-player LAN preflight')
    lan_preflight.add_commands(lan)
    sub.add_parser('features',help='Show current feature availability and dependencies')
    new=sub.add_parser('new-profile',help='Save the default feature selection')
    new.add_argument('path',type=Path);new.add_argument('--name',default='Default')
    validate=sub.add_parser('validate',help='Validate a saved feature selection')
    validate.add_argument('path',type=Path)
    sub.add_parser('gui',help='Open the modular installer')
    for action in ('check-install','install'):
        setup=sub.add_parser(action,help='Check or install selected features on a separate game copy')
        setup.add_argument('--source',type=Path,required=True)
        setup.add_argument('--copy',type=Path,required=True)
        options=setup.add_mutually_exclusive_group()
        options.add_argument('--profile',type=Path,help='Load feature choices; enabled Food uses the preserved 0.5 profile')
        options.add_argument('--food-only',action='store_true',help='Preserved Food 0.5 only; use --food06 for the new tiered diet')
        options.add_argument('--food06',action='store_true',help='Food 0.6 only; requires a NEW world and does not migrate Food 0.5 saves')
        options.add_argument('--food06-world',action='store_true',help='Food 0.6 with World Settings; separate reviewed profile for NEW worlds')
        options.add_argument('--world-only',action='store_true')
        options.add_argument('--bug-fixes-only',action='store_true',help='Install only Bug Fixes for the installed supported languages')
        setup.add_argument('--bug-fixes',action='store_true',help='Add Bug Fixes to the selected features')
        setup.add_argument('--baselines',type=Path)
        setup.add_argument('--package',type=Path)
    for action in ('restore','status','launch'):
        setup=sub.add_parser(action,help=action.capitalize()+' a managed Grand Overhaul copy')
        setup.add_argument('--copy',type=Path,required=True)
    args=ap.parse_args(argv)
    try:
        if args.command=='gui':
            from .selector import main as gui
            gui();return 0
        if args.command=='features':
            result=dict(features=[f.to_dict()for f in default_catalog().features],
                        scope='Choose Food, World Settings and Bug Fixes on a managed copy.')
        elif args.command=='lan':
            result=lan_preflight.run_command(args)
        elif args.command=='new-profile':
            saved=save_profile(args.path,default_profile(name=args.name))
            result=dict(saved=str(saved),installed=False)
        elif args.command=='validate':
            profile=load_profile(args.path)
            result=dict(valid=True,name=profile['name'],
                        enabled=[f.id for f in selected_features(profile)],installed=False)
        else:
            from . import installer
            progress=lambda message:print(message,file=sys.stderr,flush=True)
            if args.command in ('check-install','install'):
                profile=load_profile(args.profile) if args.profile else default_profile()
                if args.food_only:
                    profile['features']['food_overhaul']=True
                    profile['features']['world_settings']=False
                if args.food06:
                    profile['features']['food_overhaul']=True
                    profile['features']['world_settings']=False
                if args.food06_world:
                    profile['features']['food_overhaul']=True
                    profile['features']['world_settings']=True
                if args.world_only:
                    profile['features']['world_settings']=True
                    profile['features']['food_overhaul']=False
                if args.bug_fixes_only:
                    profile['features'].update(food_overhaul=False, world_settings=False, bug_fixes=True)
                elif args.bug_fixes:
                    profile['features']['bug_fixes']=True
                selection = {}
                if profile['features']['food_overhaul']:
                    selection['food_version'] = installer.FOOD06_VERSION if (args.food06 or args.food06_world) else installer.FOOD05_VERSION
                if args.command=='check-install':
                    result=installer.check_install(args.source,args.copy,profile,args.baselines,args.package,progress,**selection)
                else:
                    result=installer.install(args.source,args.copy,profile,baseline_dir=args.baselines,
                                             package=args.package,progress=progress,**selection)
            elif args.command=='restore':result=installer.restore(args.copy,progress=progress)
            elif args.command=='status':result=installer.inspect_copy(args.copy)
            else:
                process=installer.launch_installed_game(args.copy,progress=progress)
                result=dict(launcher_started=True,pid=process.pid)
        print(json.dumps(result,indent=2,ensure_ascii=args.command=='lan'));return 0
    except (ValueError,RuntimeError,OSError)as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
