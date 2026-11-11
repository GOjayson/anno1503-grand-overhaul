"""Anno 1503 modular installer and feature-profile commands."""
import argparse
import json
from pathlib import Path
import sys

from .features import default_catalog
from .profile import ProfileError,default_profile,load_profile,save_profile,selected_features


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
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
        options.add_argument('--profile',type=Path)
        options.add_argument('--food-only',action='store_true')
        options.add_argument('--world-only',action='store_true')
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
                        scope='Choose Food, World Settings, or both on a managed copy; Food is optional.')
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
                if args.world_only:
                    profile['features']['world_settings']=True
                    profile['features']['food_overhaul']=False
                if args.command=='check-install':
                    result=installer.check_install(args.source,args.copy,profile,args.baselines,args.package,progress)
                else:
                    result=installer.install(args.source,args.copy,profile,baseline_dir=args.baselines,
                                             package=args.package,progress=progress)
            elif args.command=='restore':result=installer.restore(args.copy,progress=progress)
            elif args.command=='status':result=installer.inspect_copy(args.copy)
            else:
                process=installer.launch_world_settings(args.copy)
                result=dict(launcher_started=True,pid=process.pid)
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except (ValueError,RuntimeError,OSError)as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
