#!/usr/bin/env python3
"""Send the headlines from latest.json as an ntfy push notification to the phone.

Tapping the notification opens the reading page.
Usage: NTFY_TOPIC=<topic> python3 notify.py [branch]   (default: current git branch)

The ntfy topic works like a password (anyone who knows it can read and send messages),
so it is never stored in the repo: it comes from the NTFY_TOPIC environment variable,
which the GitHub Action fills from a repository secret.

ntfy.sh rate-limits anonymous senders per IP, so on HTTP 429 the script retries several times.
It is normally run by the GitHub Action .github/workflows/notify.yml.
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

# Pauses between attempts in seconds (480 s in total), override with NTFY_RETRY_WAITS="30,60,…"
RETRY_WAITS = [int(x) for x in
               os.environ.get('NTFY_RETRY_WAITS', '30,60,90,120,180').split(',') if x.strip()]


def main():
    config = json.loads((DIR / 'config.json').read_text())
    topic = os.environ.get('NTFY_TOPIC', '').strip()
    if not topic:
        sys.exit('ntfy: NTFY_TOPIC is not set')
    digest = json.loads((DIR / 'latest.json').read_text())
    branch = sys.argv[1] if len(sys.argv) > 1 else subprocess.run(
        ['git', '-C', str(DIR), 'rev-parse', '--abbrev-ref', 'HEAD'],
        capture_output=True, text=True, check=True).stdout.strip()

    lines = [digest['intro'], '']
    for t in digest['topics']:
        for it in t['items']:
            lines.append(f'• {t["name"]}: {it["title"]}')
    total = sum(len(t['items']) for t in digest['topics'])
    body = {
        'topic': topic,
        # The digest itself is written in German, so the notification is too
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
            print(f'ntfy: waiting {wait} s …', flush=True)
            time.sleep(wait)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f'ntfy: HTTP {r.status} (attempt {attempt})')
                return
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
            print(f'ntfy: HTTP {e.code} (attempt {attempt})', flush=True)
        except urllib.error.URLError as e:
            print(f'ntfy: {e.reason} (attempt {attempt})', flush=True)
    sys.exit('ntfy: giving up, all attempts failed')


if __name__ == '__main__':
    main()
