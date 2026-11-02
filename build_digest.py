#!/usr/bin/env python3
"""Build the finished digest from work/draft.json (a draft referring to candidate numbers).

Fills in the real links from work/candidates.json, validates the draft and writes
digests/<date>.json + .md as well as latest.json + latest.md.
The digest content (topics, title, dates) is German, since that is the language it is read in.
"""
import json
import sys
from urllib.parse import urlsplit
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DIR = Path(__file__).resolve().parent
TZ = ZoneInfo('Europe/Vienna')
# Topic names as shown in the (German) digest
TOPICS = ['Innenpolitik', 'EU', 'Welt', 'Wirtschaft', 'Klima', 'Tech/KI', 'IT-Security', 'Wissenschaft', 'Nahost', 'USA']
WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
MONTHS = ['Jänner', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August',
          'September', 'Oktober', 'November', 'Dezember']


def fail(msg):
    sys.exit(f'ERROR in draft: {msg}')


def long_date(d):
    return f'{WEEKDAYS[d.weekday()]}, {d.day}. {MONTHS[d.month - 1]} {d.year}'


def build(draft, candidates, now):
    by_n = {c['n']: c for c in candidates}
    names = [t.get('name') for t in draft.get('topics', [])]
    if unknown := [n for n in names if n not in TOPICS]:
        fail(f'unknown topics {unknown}, allowed are {TOPICS}')
    if not isinstance(draft.get('intro'), str) or not draft['intro'].strip():
        fail('"intro" is missing')

    date = now.date().isoformat()
    topics, count = [], 0
    for topic in sorted(draft['topics'], key=lambda t: TOPICS.index(t['name'])):
        items = []
        for it in topic.get('items', []):
            if not it.get('title') or not it.get('summary'):
                fail(f'item without title/summary in {topic["name"]}')
            missing = [n for n in it.get('sources', []) if n not in by_n]
            if missing or not it.get('sources'):
                fail(f'"{it["title"]}": invalid source numbers {missing or "(none)"}')
            count += 1
            sources = []
            for n in it['sources']:
                c = by_n[n]
                if urlsplit(c['url']).scheme not in ('http', 'https'):
                    continue  # links come from third-party feeds: keep web links only
                sources.append({'name': c['source'], 'url': c['url'],
                                **({'paywall': True} if c.get('paywall') else {})})
            if not sources:
                fail(f'"{it["title"]}": no source with a valid web link')
            items.append({'id': f'{date}-{count:02d}', 'title': it['title'].strip(),
                          'summary': it['summary'].strip(), 'sources': sources})
        if items:
            topics.append({'name': topic['name'], 'items': items})
    if not count:
        fail('no items')
    return {'date': date, 'title': f'Morgen-Digest · {long_date(now)}',
            'generated': now.isoformat(timespec='minutes'), 'intro': draft['intro'].strip(),
            'topics': topics}


def markdown(digest):
    out = [f'# {digest["title"]}', '', f'_{digest["intro"]}_', '']
    for topic in digest['topics']:
        out += [f'## {topic["name"]}', '']
        for it in topic['items']:
            links = ' · '.join(f'[{s["name"]}{" 🔒" if s.get("paywall") else ""}]({s["url"]})'
                               for s in it['sources'])
            out += [f'### {it["title"]}', '', it['summary'], '', f'→ {links}', '']
    return '\n'.join(out)


def main():
    work = DIR / 'work'
    try:
        draft = json.loads((work / 'draft.json').read_text())
    except (OSError, json.JSONDecodeError) as e:
        fail(f'cannot read work/draft.json: {e}')
    candidates = json.loads((work / 'candidates.json').read_text())['items']
    digest = build(draft, candidates, datetime.now(TZ))

    text = json.dumps(digest, ensure_ascii=False, indent=1)
    md = markdown(digest)
    (DIR / 'digests').mkdir(exist_ok=True)
    (DIR / 'digests' / f'{digest["date"]}.json').write_text(text)
    (DIR / 'digests' / f'{digest["date"]}.md').write_text(md)
    (DIR / 'latest.json').write_text(text)
    (DIR / 'latest.md').write_text(md)
    total = sum(len(t['items']) for t in digest['topics'])
    print(f'OK: {total} items in {len(digest["topics"])} topics → digests/{digest["date"]}.md')


if __name__ == '__main__':
    main()
