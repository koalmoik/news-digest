#!/bin/bash
# Richtet den Sync-Timer und die GNOME-Erweiterung ein.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
EXT=news-digest@peter

mkdir -p ~/.config/systemd/user ~/.local/share/gnome-shell/extensions

# git fetch über das gh-Login authentifizieren
gh auth setup-git

# Digest alle 15 Minuten von GitHub holen
cat > ~/.config/systemd/user/news-digest.service <<UNIT
[Unit]
Description=Morgen-Digest von GitHub holen
After=network-online.target

[Service]
Type=oneshot
ExecStart=$DIR/sync.sh
UNIT

cat > ~/.config/systemd/user/news-digest.timer <<UNIT
[Unit]
Description=Morgen-Digest alle 15 Minuten holen

[Timer]
OnActiveSec=30s
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
UNIT

ln -sfn "$DIR/extension" ~/.local/share/gnome-shell/extensions/$EXT

systemctl --user daemon-reload
systemctl --user enable --now news-digest.timer
gnome-extensions enable $EXT 2>/dev/null \
  || echo "Erweiterung: einmal ab- und wieder anmelden, dann: gnome-extensions enable $EXT"
echo "Fertig."
