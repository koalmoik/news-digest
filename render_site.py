#!/usr/bin/env python3
"""Render all digests from digests/*.json as static reading pages for the phone.

The pages go to the public pages repo: plain HTML without JavaScript, all text escaped,
http(s) links only, excluded from search engines. The pages are in German, like the digest.
Usage: python3 render_site.py <path to the pages repo>
"""
import json
import sys
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

DIR = Path(__file__).resolve().parent
WEEKDAYS = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

CSS = """
:root {
  --bg: #f7f5f0; --card: #ffffff; --text: #1d1d1f; --muted: #6b6b70; --line: #e4e0d8;
  --accent: #1c63c7; --chip: #eef3fb; --lock: #a15c00;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141416; --card: #1e1e21; --text: #ececee; --muted: #9a9aa2; --line: #2e2e33;
    --accent: #78aeff; --chip: #23304a; --lock: #f0b45a;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 17px/1.55 "Iowan Old Style", "Charter", Georgia, serif;
}
.wrap { max-width: 40rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
.ui, .kicker, h2, .src, nav, footer { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.kicker { margin: 0; color: var(--accent); font-size: .8rem; font-weight: 700;
  letter-spacing: .08em; text-transform: uppercase; }
h1 { margin: .2rem 0 .8rem; font-size: 1.7rem; line-height: 1.2; }
.intro { margin: 0 0 1.2rem; font-style: italic; color: var(--muted); }
nav.toc { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: 1.5rem; }
nav.toc a { padding: .25rem .7rem; border-radius: 99px; background: var(--chip);
  color: var(--accent); font-size: .85rem; text-decoration: none; }
h2 { margin: 2rem 0 .7rem; padding-bottom: .3rem; border-bottom: 2px solid var(--line);
  font-size: .9rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
article { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 1rem 1.1rem; margin-bottom: .8rem; }
h3 { margin: 0 0 .4rem; font-size: 1.15rem; line-height: 1.3; }
article p { margin: 0 0 .6rem; }
.src { display: flex; flex-wrap: wrap; gap: .4rem; margin: 0; font-size: .85rem; }
.src a { color: var(--accent); text-decoration: none; padding: .2rem .6rem;
  border: 1px solid var(--line); border-radius: 99px; }
.src .lock { color: var(--lock); }
footer { display: flex; justify-content: space-between; gap: 1rem; margin-top: 2rem; font-size: .9rem; }
footer a { color: var(--accent); text-decoration: none; }
"""


def safe_url(url):
    return url if urlsplit(url).scheme in ('http', 'https') else None


def slug(name):
    return name.lower().replace('/', '-').replace(' ', '-')


def short_date(iso):
    d = date.fromisoformat(iso)
    return f'{WEEKDAYS[d.weekday()]} {d.day:02d}.{d.month:02d}.'


def page(digest, prev_date, next_date):
    e = escape
    out = [
        '<!doctype html><html lang="de"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="robots" content="noindex, nofollow"><meta name="referrer" content="no-referrer">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<meta name="color-scheme" content="light dark">',
        f'<title>{e(digest["title"])}</title><style>{CSS}</style></head><body><div class="wrap">',
        f'<p class="kicker">Morgen-Digest</p><h1>{e(digest["title"].split(" · ", 1)[-1])}</h1>',
        f'<p class="intro">{e(digest["intro"])}</p>',
        '<nav class="toc">' + ''.join(
            f'<a href="#{slug(t["name"])}">{e(t["name"])}</a>' for t in digest['topics']) + '</nav>',
    ]
    for topic in digest['topics']:
        out.append(f'<section id="{slug(topic["name"])}"><h2>{e(topic["name"])}</h2>')
        for it in topic['items']:
            links = []
            for s in it['sources']:
                url = safe_url(s['url'])
                if url:
                    lock = ' <span class="lock">🔒</span>' if s.get('paywall') else ''
                    links.append(f'<a href="{e(url)}" rel="noopener noreferrer">{e(s["name"])}{lock}</a>')
            out.append(f'<article><h3>{e(it["title"])}</h3><p>{e(it["summary"])}</p>'
                       f'<p class="src">{"".join(links)}</p></article>')
        out.append('</section>')
    prev_link = f'<a href="{prev_date}.html">← {short_date(prev_date)}</a>' if prev_date else '<span></span>'
    next_link = f'<a href="{next_date}.html">{short_date(next_date)} →</a>' if next_date else '<span></span>'
    out.append(f'<footer>{prev_link}{next_link}</footer></div></body></html>')
    return '\n'.join(out)


def main():
    site = Path(sys.argv[1]).resolve()
    digests = sorted((DIR / 'digests').glob('????-??-??.json'))
    dates = [p.stem for p in digests]
    for i, path in enumerate(digests):
        digest = json.loads(path.read_text())
        html = page(digest, dates[i - 1] if i else None, dates[i + 1] if i + 1 < len(dates) else None)
        (site / f'{path.stem}.html').write_text(html)
        if i + 1 == len(dates):
            (site / 'index.html').write_text(html)
    (site / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    (site / '.nojekyll').write_text('')
    print(f'{len(dates)} pages → {site}')


if __name__ == '__main__':
    main()
