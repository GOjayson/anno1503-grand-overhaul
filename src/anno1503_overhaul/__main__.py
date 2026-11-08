"""Feature-profile commands. These commands never install or activate game code."""
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
    sub.add_parser('gui',help='Open the feature-profile selector')
    args=ap.parse_args(argv)
    try:
        if args.command=='gui':
            from .selector import main as gui
            gui();return 0
        if args.command=='features':
            result=dict(features=[f.to_dict()for f in default_catalog().features],
                        scope='Feature selection only; a common modular installer is under development.')
        elif args.command=='new-profile':
            saved=save_profile(args.path,default_profile(name=args.name))
            result=dict(saved=str(saved),installed=False)
        else:
            profile=load_profile(args.path)
            result=dict(valid=True,name=profile['name'],
                        enabled=[f.id for f in selected_features(profile)],installed=False)
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except (ProfileError,OSError)as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
