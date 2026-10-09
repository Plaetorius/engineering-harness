#!/usr/bin/env python3
"""Offline PNG rendering with an already installed Mermaid CLI (mmdc); optionally opens the image for the user."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def render(source, output_directory):
    text = Path(source).read_text(encoding='utf-8')
    if len(text.encode()) > 128_000:
        raise ValueError('Diagram too large; use progressive detail')
    if not re.match(r'\A\s*(flowchart\s+(?:LR|RL|TD|TB|BT)\b|sequenceDiagram\b)', text):
        raise ValueError('Use a flowchart or sequence diagram')
    if re.search(r'%%\{|^\s*---|\bclick\b|https?://|file:|data:|<[^>]*>|@\{|:::|\bstyle\b|\bclassDef\b', text, re.I | re.M):
        raise ValueError('Diagram contains unsupported directives, links or external/HTML content')
    output = Path(output_directory)
    if output.is_symlink() or not output.is_dir():
        raise ValueError('Select an existing approved output directory')
    # Canonicalize approved parent; artifacts are always fresh, never replacements.
    output = output.resolve()
    renderer = shutil.which('mmdc')
    if renderer is None:
        return {'status': 'unavailable', 'syntax_validated': False, 'reason': 'Installed mmdc not found'}
    folder = Path(tempfile.mkdtemp(prefix='architecture-map-', dir=output))
    local_source = folder / 'diagram.mmd'
    local_source.write_text(text, encoding='utf-8')
    config = folder / 'config.json'
    config.write_text(json.dumps({'securityLevel': 'strict', 'startOnLoad': False,
                                 'flowchart': {'htmlLabels': False}}), encoding='utf-8')
    png = folder / 'diagram.png'
    try:
        # PNG is the default artifact: it opens in any viewer. -s 2 keeps labels sharp; white background for light/dark viewers.
        result = subprocess.run([renderer, '-i', str(local_source), '-o', str(png), '-c', str(config), '-s', '2', '-b', 'white'],
                                cwd=folder, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return {'status': 'execution-error', 'syntax_validated': False, 'source': str(local_source),
                'reason': 'Local renderer could not complete'}
    if result.returncode != 0 or not png.is_file() or png.is_symlink():
        return {'status': 'failure', 'syntax_validated': False, 'source': str(local_source),
                'reason': 'Local rendering failed; inspect sanitized source and tool compatibility'}
    return {'status': 'success', 'syntax_validated': True, 'source': str(local_source), 'png': str(png)}


def open_image(path):
    """Open the rendered PNG in the user's default viewer. Local file only; never a URL."""
    opener = shutil.which('open') if sys.platform == 'darwin' else shutil.which('xdg-open')
    if opener is None:
        return False
    try:
        return subprocess.run([opener, str(path)], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('--output-directory', required=True)
    parser.add_argument('--open', action='store_true', help='open the rendered PNG in the default viewer')
    args = parser.parse_args()
    try:
        result = render(args.source, args.output_directory)
    except (ValueError, OSError, UnicodeError) as exc:
        print(json.dumps({'status': 'refused', 'syntax_validated': False, 'reason': str(exc)}))
        return 1
    if args.open and result['status'] == 'success':
        result['opened'] = open_image(result['png'])
    print(json.dumps(result, indent=2))
    return 0 if result['status'] in ('success', 'unavailable') else 1


if __name__ == '__main__':
    raise SystemExit(main())
