#!/bin/bash
# Sets up the sync timer and the GNOME extension.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
EXT=news-digest@peter

mkdir -p ~/.config/systemd/user ~/.local/share/gnome-shell/extensions

# authenticate git fetch through the gh login
gh auth setup-git

# Fetch the digest from GitHub every 15 minutes
cat > ~/.config/systemd/user/news-digest.service <<UNIT
[Unit]
Description=Fetch the morning digest from GitHub
After=network-online.target

[Service]
Type=oneshot
ExecStart=$DIR/sync.sh
UNIT

cat > ~/.config/systemd/user/news-digest.timer <<UNIT
[Unit]
Description=Fetch the morning digest every 15 minutes, every 2 minutes in the morning

[Timer]
OnActiveSec=30s
OnUnitActiveSec=15min
# The new digest arrives between 6 and 7 a.m. – check more often then
OnCalendar=*-*-* 06:00/2
Persistent=true

[Install]
WantedBy=timers.target
UNIT

ln -sfn "$DIR/extension" ~/.local/share/gnome-shell/extensions/$EXT

systemctl --user daemon-reload
systemctl --user enable --now news-digest.timer
gnome-extensions enable $EXT 2>/dev/null \
  || echo "Extension: log out and back in once, then run: gnome-extensions enable $EXT"
echo "Done."
