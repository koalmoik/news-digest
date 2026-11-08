# news-digest

A daily morning news digest for Austria and the world, written by a scheduled Claude Code
routine and delivered to the GNOME desktop and the phone. The digest itself is in German.

## How it works

1. **06:05 Vienna time:** a scheduled cloud routine follows [`INSTRUCTIONS.md`](INSTRUCTIONS.md):
   - `fetch_feeds.py` collects the last 26 hours from the RSS feeds in `feeds.json`,
   - the model picks 16–20 important stories and writes German summaries (`work/draft.json`),
   - `build_digest.py` validates the draft, fills in the real links and writes
     `digests/<date>.json/.md` and `latest.json/.md`,
   - `render_site.py` renders static reading pages into the public
     [`news-digest-pages`](https://github.com/koalmoik/news-digest-pages) repo (GitHub Pages).
2. **Phone:** the GitHub Action [`notify.yml`](.github/workflows/notify.yml) runs when a new
   digest is pushed and sends the headlines via [ntfy](https://ntfy.sh); tapping the
   notification opens the reading page.
3. **Desktop:** a systemd user timer runs `sync.sh`, which copies the newest `latest.json` into
   `~/.cache/news-digest/`. The GNOME Shell extension in `extension/` shows it in the top bar,
   tracks read items and keeps a reading streak.

## Setup

### Phone notifications

The ntfy topic acts as a password: anyone who knows it can read and send messages.
It is therefore only stored as a repository secret, never in the repo.

1. Pick a long random topic, e.g. `news-digest-$(python3 -c 'import secrets; print(secrets.token_hex(16))')`.
2. Save it as the Actions secret `NTFY_TOPIC` (`gh secret set NTFY_TOPIC`).
3. Subscribe to the topic in the ntfy app.

`config.json` holds the non-secret settings (ntfy server, repo and pages URL).

### Desktop

Clone the repo anywhere (the extension finds `sync.sh` through its symlink), log in with
`gh auth login` and run:

```bash
./install.sh
```

The extension UI is available in English and German and follows the system locale. To override
it, create `~/.config/news-digest/config.json` with `{"language": "de"}` (or `"en"`).

## Security notes

- Feed content is untrusted: rendered pages escape all text, contain no JavaScript, use a strict
  Content Security Policy and only link to `http(s)` URLs; `build_digest.py` and the extension
  also drop or refuse non-web links.
- The workflow only has read access to the repo and gets the ntfy topic from a secret.
