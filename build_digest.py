#!/usr/bin/env python3
"""Baut aus work/draft.json (Entwurf mit Kandidaten-Nummern) den fertigen Digest.

Setzt die echten Links aus work/candidates.json ein, prüft den Entwurf und schreibt
digests/<datum>.json + .md sowie latest.json + latest.md.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DIR = Path(__file__).resolve().parent
TZ = ZoneInfo('Europe/Vienna')
TOPICS = ['Innenpolitik', 'EU', 'Welt', 'Wirtschaft', 'Klima', 'Tech/KI', 'Wissenschaft', 'Nahost', 'USA']
WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
MONTHS = ['Jänner', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August',
          'September', 'Oktober', 'November', 'Dezember']


def fail(msg):
    sys.exit(f'FEHLER im Entwurf: {msg}')


def long_date(d):
    return f'{WEEKDAYS[d.weekday()]}, {d.day}. {MONTHS[d.month - 1]} {d.year}'


def build(draft, candidates, now):
    by_n = {c['n']: c for c in candidates}
    names = [t.get('name') for t in draft.get('topics', [])]
    if unknown := [n for n in names if n not in TOPICS]:
        fail(f'unbekannte Themen {unknown}, erlaubt sind {TOPICS}')
    if not isinstance(draft.get('intro'), str) or not draft['intro'].strip():
        fail('"intro" fehlt')

    date = now.date().isoformat()
    topics, count = [], 0
    for topic in sorted(draft['topics'], key=lambda t: TOPICS.index(t['name'])):
        items = []
        for it in topic.get('items', []):
            if not it.get('title') or not it.get('summary'):
                fail(f'Meldung ohne title/summary in {topic["name"]}')
            missing = [n for n in it.get('sources', []) if n not in by_n]
            if missing or not it.get('sources'):
                fail(f'"{it["title"]}": ungültige Quellen-Nummern {missing or "(keine)"}')
            count += 1
            sources = []
            for n in it['sources']:
                c = by_n[n]
                sources.append({'name': c['source'], 'url': c['url'],
                                **({'paywall': True} if c.get('paywall') else {})})
            items.append({'id': f'{date}-{count:02d}', 'title': it['title'].strip(),
                          'summary': it['summary'].strip(), 'sources': sources})
        if items:
            topics.append({'name': topic['name'], 'items': items})
    if not count:
        fail('keine Meldungen')
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
        fail(f'work/draft.json nicht lesbar: {e}')
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
    print(f'OK: {total} Meldungen in {len(digest["topics"])} Themen → digests/{digest["date"]}.md')


if __name__ == '__main__':
    main()
