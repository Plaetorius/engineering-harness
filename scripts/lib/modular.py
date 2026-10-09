"""Small filesystem-based extension CLI."""
import argparse
import json
import sys
from harness import Refusal
from packs import Pack, discover, new_pack
from projects import Project
from checks import run


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    groups = parser.add_subparsers(dest='group', required=True)
    pack = groups.add_parser('pack').add_subparsers(dest='action', required=True)
    for action in ('new', 'validate', 'activate', 'deactivate', 'list'):
        p = pack.add_parser(action)
        if action != 'list':
            p.add_argument('selection')
        if action == 'new':
            p.add_argument('--directory', required=True)
        else:
            p.add_argument('--project')
            p.add_argument('--pack-root', action='append', default=[])
        if action in ('activate', 'deactivate'):
            p.add_argument('--apply', action='store_true')
            p.add_argument('--trust-pack', action='append', default=[])
    for group, actions in (('project', ('inspect', 'sync', 'recover')), ('check', ('list', 'run'))):
        subs = groups.add_parser(group).add_subparsers(dest='action', required=True)
        for action in actions:
            p = subs.add_parser(action)
            p.add_argument('--project', required=True)
            if action in ('sync', 'recover'):
                p.add_argument('--apply', action='store_true')
            if action == 'sync':
                p.add_argument('--pack-root', action='append', default=[])
                p.add_argument('--trust-pack', action='append', default=[])
            if action == 'run':
                p.add_argument('--execute', action='store_true')
                p.add_argument('--check', action='append', default=[])
    p = groups.add_parser('doctor')
    p.add_argument('--project')
    p.add_argument('--preserve-settings', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = None
        if args.group == 'pack':
            if args.action == 'new':
                new_pack(args.directory, args.selection)
                result = Pack(args.directory).descriptor()
            elif args.action == 'validate':
                result = Pack(args.selection).descriptor()
            elif args.action == 'list':
                active = Project(args.project).profile()['packs'] if args.project else []
                result = {'available': [p.descriptor() for p in discover(roots=args.pack_root).values()], 'active': active}
            else:
                if not args.project:
                    parser.error('--project is required for activation/deactivation')
                Project(args.project).mutation(args.action, args.selection, roots=args.pack_root,
                                               trust=args.trust_pack, apply=args.apply)
        elif args.group == 'project':
            project = Project(args.project)
            if args.action == 'inspect':
                result = project.inspect()
            elif args.action == 'recover':
                project.recover(args.apply)
            else:
                project.mutation('sync', roots=args.pack_root, trust=args.trust_pack, apply=args.apply)
        elif args.group == 'check':
            result = run(Project(args.project), execute=getattr(args, 'execute', False), selected=getattr(args, 'check', []))
        else:
            packs = discover().values()
            for pack in packs:
                pack.compatible()
            if args.project:
                result = Project(args.project).inspect()
            else:
                import harness
                code = harness.main(['doctor'] + (['--preserve-settings'] if args.preserve_settings else []))
                if code:
                    return code
                result = {'packs_validated': len(list(packs))}
        if result is not None:
            print(json.dumps(result, indent=2))
            if result.get('execution_ok') is False:
                return 1
        return 0
    except (Refusal, OSError) as exc:
        print('REFUSED: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
