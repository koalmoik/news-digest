# Anleitung für die tägliche Digest-Routine

Du erstellst Peters täglichen Morgen-Digest: ein kurzer, hochwertiger Nachrichtenüberblick
über Österreich und die Welt, in etwa 10 Minuten lesbar. Arbeite die Schritte der Reihe nach ab.

## 1. Soll heute ein Digest entstehen?

Die Routine startet täglich um 06:00 und 07:00 UTC, damit es trotz Sommer-/Winterzeit
immer einen Lauf um 08:00 Wiener Zeit gibt.

```bash
TZ=Europe/Vienna date +'%F %H'
```

- Gibt es `digests/<heutiges Datum>.json` schon → **sofort beenden**, nichts tun.
- Ist es in Wien vor 08 Uhr → **sofort beenden**, nichts tun.
- Sonst weiter.

## 2. Meldungen holen

```bash
python3 fetch_feeds.py > work/list.txt
```

Lies `work/list.txt` vollständig. Jede Zeile: `#Nr Quelle [AT|INT] | Titel — Teaser`,
`$` markiert Quellen mit teilweiser Paywall. Andere Quellen als diese gibt es nicht. Erfinde
keine Fakten, Links oder Quellen. Du darfst höchstens 5 Artikel-Links per curl oder WebFetch
öffnen, falls ein Teaser für eine korrekte Zusammenfassung nicht reicht.

## 3. Auswählen und schreiben → `work/draft.json`

Themen, genau diese Namen, in dieser Reihenfolge:
`Innenpolitik`, `EU`, `Welt`, `Wirtschaft`, `Klima`, `Tech/KI`, `Wissenschaft`, `Nahost`, `USA`

- **Innenpolitik** heißt österreichische Innenpolitik. Bevorzuge dafür ORF, Der Standard, Die Presse, SN.
- **Welt:** große internationale Ereignisse, die nicht zu EU, Nahost oder USA passen
  (z. B. Ukraine-Krieg, China, Russland, Wahlen anderswo, große Katastrophen).
- **Wirtschaft:** Österreich und international gemischt.
- Pro Thema 1–2 Meldungen, bei einem wirklich großen Ereignis höchstens 3. Insgesamt 14–18.
  Gibt es zu einem Thema nichts Relevantes, lass es weg.
- Auswahl nach Bedeutung: Was muss ein informierter Mensch in Österreich heute wissen?
  Nicht aufnehmen: Sport, Promis, Lifestyle, Lokal-Kriminalität, Liveticker, Kommentare und
  Meinungsstücke, Werbung.
- Dieselbe Geschichte aus mehreren Quellen → **eine** Meldung mit bis zu 3 Quellen.
  Freie Quellen (ohne `$`) zuerst, eine österreichische Quelle zuerst, wenn es eine gibt.
- **title:** eigene, sachliche deutsche Schlagzeile, max. ca. 70 Zeichen, kein Clickbait.
- **summary:** 2–3 Sätze auf Deutsch (auch bei englischen Quellen): Was ist passiert, und
  warum ist es wichtig? Neutral, konkret, mit Zahlen und Namen, wo vorhanden.
- **intro:** 1–2 Sätze, die den Tag zusammenfassen (das Wichtigste zuerst).

Format:

```json
{
  "intro": "…",
  "topics": [
    {"name": "Innenpolitik", "items": [
      {"title": "…", "summary": "…", "sources": [12, 87]}
    ]}
  ]
}
```

`sources` sind die Nummern aus `work/list.txt`.

## 4. Digest bauen

```bash
python3 build_digest.py
```

Meldet das Skript `FEHLER`, korrigiere `work/draft.json` und führe es erneut aus.

## 5. Veröffentlichen

```bash
git add digests latest.json latest.md
git commit -m "Digest $(TZ=Europe/Vienna date +%F)"
git push origin HEAD:main
```

Wird der Push auf `main` abgelehnt, nimm stattdessen den Branch `claude/digest`:
`git push --force origin HEAD:claude/digest`. Merk dir, welcher Branch geklappt hat.

## 6. Handy benachrichtigen

```bash
python3 notify.py <branch aus Schritt 5>
```

Ändere nichts anderes im Repo. Antworte am Ende mit einer Zeile: Anzahl Meldungen und Branch.
