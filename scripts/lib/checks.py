"""Generic argv-based checks; discovery never executes commands."""
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid
from harness import Refusal, atomic_write, digest, json_bytes, regular_bytes
from packs import relative_path, schema, validate_schema


def resolve(project, profile, pack, check):
    if 'project_command' in check:
        command = profile['commands'].get(check['project_command'])
        if command is None:
            return None
        argv = command['argv']
        cwd = relative_path(project.root, command['cwd'], directory=True)
        timeout = min(command['timeout_seconds'], check['timeout_seconds'])
    else:
        argv = check['argv']
        owner = project.root if check['cwd'] == 'project' else pack.root
        cwd = relative_path(owner, check.get('cwd_subdir', '.'), directory=True)
        timeout = check['timeout_seconds']
    expanded = []
    for arg in argv:
        for token, root in (('{pack}', pack.root), ('{project}', project.root)):
            if arg == token or arg.startswith(token + '/'):
                suffix = arg[len(token):].lstrip('/')
                arg = str(relative_path(root, suffix or '.', directory=not suffix))
                break
        expanded.append(arg)
    return expanded, cwd, timeout


def run(project, execute=False, selected=()):
    profile, state, packs = project.verified_packs(execution=execute)
    available = {p.manifest['id'] + ':' + c['id']: (p, c) for p in packs for c in p.manifest['checks']}
    if set(selected) - available.keys():
        raise Refusal('Unknown selected check identifier')
    ids = list(selected) if selected else list(available)
    ids += [i for i in profile['required_checks'] if i not in ids]
    plans = {}
    for identifier in ids:
        pair = available.get(identifier)
        plans[identifier] = resolve(project, profile, *pair) if pair else None
    if not execute:
        return {'execution': 'dry-run', 'checks': [{'id': i, 'argv': v[0] if v else None,
                  'cwd': str(v[1]) if v else None, 'timeout_seconds': v[2] if v else None}
                 for i, v in plans.items()]}
    run_id = uuid.uuid4().hex
    folder = project.local / 'reports' / run_id
    from harness import parents_safe
    parents_safe(folder / 'entry')
    if ids:
        folder.mkdir(parents=True, mode=0o700)
    results = []
    for identifier, plan in plans.items():
        pair = available.get(identifier)
        pack = pair[0] if pair else None
        result = {'id': identifier, 'pack_version': pack.manifest['version'] if pack else 'unavailable',
                  'pack_digest': pack.digest if pack else 'unavailable', 'status': 'skipped',
                  'duration_seconds': 0, 'exit_code': None, 'reason': 'Check or project command unavailable',
                  'stdout': None, 'stderr': None}
        if plan:
            project.verified_packs(execution=True)
            argv, cwd, timeout = plan
            out = folder / (str(len(results)) + '.stdout')
            err = folder / (str(len(results)) + '.stderr')
            result.update(stdout=out.relative_to(project.root).as_posix(), stderr=err.relative_to(project.root).as_posix())
            start = time.monotonic()
            with out.open('xb') as stdout, err.open('xb') as stderr:
                try:
                    process = subprocess.Popen(argv, cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=True)
                    try:
                        code = process.wait(timeout=timeout)
                        result.update(status='success' if code == 0 else 'failure', exit_code=code, reason=None)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                        result.update(status='execution-error', reason='Timeout exceeded')
                except OSError as exc:
                    result.update(status='execution-error', reason=str(exc))
            result['duration_seconds'] = time.monotonic() - start
        results.append(result)
    statuses = {r['id']: r['status'] for r in results}
    required = all(statuses.get(i) == 'success' for i in profile['required_checks'])
    report = {'schema_version': 1, 'run_id': run_id,
              'profile_digest': digest(regular_bytes(project.profile_path) or json_bytes(profile)),
              'results': results, 'required_checks_passed': required,
              'execution_ok': required and all(r['status'] not in ('failure', 'execution-error') for r in results),
              'acceptance_criteria': profile['acceptance_criteria']}
    validate_schema(report, schema('check-result'))
    if ids:
        atomic_write(folder / 'result.json', json_bytes(report))
    return report
