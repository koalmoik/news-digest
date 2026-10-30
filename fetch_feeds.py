#!/usr/bin/env python3
"""Holt alle Feeds aus feeds.json und sammelt die Meldungen der letzten Stunden.

Schreibt alles nach work/candidates.json und gibt eine kompakte, nummerierte Liste aus,
auf deren Nummern sich der Entwurf (work/draft.json) bezieht.
Nur Standardbibliothek, damit es in der Cloud-Umgebung ohne Installation läuft.
Aufruf: python3 fetch_feeds.py [stunden]
"""
import html
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

DIR = Path(__file__).resolve().parent
HOURS = int(sys.argv[1]) if len(sys.argv) > 1 else 26
SUMMARY_CHARS = 160
UA = 'Mozilla/5.0 (news-digest; private RSS reader)'


def local(tag):
    return tag.rsplit('}', 1)[-1]


def child_text(el, *names):
    for c in el:
        if local(c.tag) in names:
            if local(c.tag) == 'link' and c.get('href'):
                return c.get('href')
            if c.text and c.text.strip():
                return c.text.strip()
    return ''


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def clean(s):
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))
    s = re.sub(r'\s+', ' ', s).strip()
    return s if len(s) <= SUMMARY_CHARS else s[:SUMMARY_CHARS].rsplit(' ', 1)[0] + ' …'


def fetch(feed):
    req = urllib.request.Request(feed['url'], headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        return feed, [], f'{type(e).__name__}: {e}'
    items = []
    for el in root.iter():
        if local(el.tag) not in ('item', 'entry'):
            continue
        items.append({
            'title': clean(child_text(el, 'title')),
            'summary': clean(child_text(el, 'description', 'summary', 'content')),
            'url': child_text(el, 'link'),
            'published': parse_date(child_text(el, 'pubDate', 'published', 'updated', 'date')),
        })
    return feed, items, None


def main():
    feeds = json.loads((DIR / 'feeds.json').read_text())['feeds']
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS)
    seen, out, errors = set(), [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for feed, items, err in pool.map(fetch, feeds):
            if err:
                errors.append({'source': feed['name'], 'url': feed['url'], 'error': err})
            for it in items:
                if not it['title'] or not it['url'] or it['url'] in seen:
                    continue
                if it['published'] and it['published'] < cutoff:
                    continue
                seen.add(it['url'])
                out.append({
                    'source': feed['name'], 'region': feed['region'],
                    **({'paywall': feed['paywall']} if feed.get('paywall') else {}),
                    'title': it['title'], 'summary': it['summary'], 'url': it['url'],
                    'published': it['published'].isoformat(timespec='minutes') if it['published'] else None,
                })
    for n, it in enumerate(out, 1):
        it['n'] = n
    work = DIR / 'work'
    work.mkdir(exist_ok=True)
    (work / 'candidates.json').write_text(json.dumps({'errors': errors, 'items': out}, ensure_ascii=False))

    print(f'{len(out)} Meldungen aus den letzten {HOURS} h. Format: #Nr Quelle [Region] | Titel — Teaser')
    for e in errors:
        print(f'! Feed nicht erreichbar: {e["source"]} ({e["error"]})')
    for it in out:
        pay = ' $' if it.get('paywall') else ''
        teaser = f' — {it["summary"]}' if it['summary'] and it['summary'] != it['title'] else ''
        print(f'#{it["n"]} {it["source"]} [{it["region"]}]{pay} | {it["title"]}{teaser}')


if __name__ == '__main__':
    main()
