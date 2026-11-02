#!/usr/bin/env python3
"""Schickt die Schlagzeilen aus latest.json als ntfy-Push aufs Handy.

Ein Tipp auf die Benachrichtigung öffnet die Leseseite.
Aufruf: python3 notify.py [branch]   (Standard: aktueller Git-Branch)

ntfy.sh begrenzt anonyme Nachrichten pro IP. Die Cloud-Sandbox teilt sich IPs mit
anderen, daher kommt öfter HTTP 429. Das Skript versucht es dann mehrmals erneut.
Normalerweise ruft es die GitHub Action .github/workflows/notify.yml auf.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DIR = Path(__file__).resolve().parent

# Pausen zwischen den Versuchen in Sekunden (Summe 480 s), per NTFY_RETRY_WAITS="30,60,…" änderbar
RETRY_WAITS = [int(x) for x in
               os.environ.get('NTFY_RETRY_WAITS', '30,60,90,120,180').split(',') if x.strip()]


def main():
    config = json.loads((DIR / 'config.json').read_text())
    digest = json.loads((DIR / 'latest.json').read_text())
    branch = sys.argv[1] if len(sys.argv) > 1 else subprocess.run(
        ['git', '-C', str(DIR), 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True, text=True, check=True).stdout.strip()

    lines = [digest['intro'], '']
    for topic in digest['topics']:
        for it in topic['items']:
            lines.append(f'• {topic["name"]}: {it["title"]}')
    total = sum(len(t['items']) for t in digest['topics'])
    body = {
        'topic': config['ntfy_topic'],
        'title': f'{digest["title"]} ({total} Meldungen)',
        'message': '\n'.join(lines)[:3800],
        'click': f'{config["pages_url"]}/{digest["date"]}.html' if config.get('pages_url') else
                 f'https://github.com/{config["github_repo"]}/blob/{branch}/digests/{digest["date"]}.md',
        'tags': ['newspaper'],
    }
    req = urllib.request.Request(config.get('ntfy_server', 'https://ntfy.sh'),
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    for attempt, wait in enumerate([0] + RETRY_WAITS, 1):
        if wait:
            print(f'ntfy: warte {wait} s …', flush=True)
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f'ntfy: HTTP {r.status} (Versuch {attempt})')
                return
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            print(f'ntfy: HTTP {e.code} (Versuch {attempt})', flush=True)
        except urllib.error.URLError as e:
            print(f'ntfy: {e.reason} (Versuch {attempt})', flush=True)
    sys.exit('ntfy: aufgegeben, alle Versuche gescheitert')


if __name__ == '__main__':
    main()
