#!/bin/zsh
# Safety net for the GitHub schedule, which often skips runs on small repos. Run every 30 min on my Mac
# (launchd): if today's brief is not published by 7:30am Paris, build and publish it from here.
cd "$(dirname "$0")" || exit 1
day=$(TZ=Europe/Paris date +%F)
[[ $(date +%u) -le 5 && $(TZ=Europe/Paris date +%H%M) -ge 730 ]] || exit 0
git pull -q --rebase || exit 1
[[ -f docs/briefs/$day.html ]] && exit 0
date
.venv/bin/python brief.py >/dev/null 2>&1 || { echo "brief.py failed"; exit 1; }
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1000,1250 --virtual-time-budget=5000 --user-data-dir="$TMPDIR/brief-chrome" \
  --screenshot="$PWD/preview.png" "file://$PWD/docs/index.html" 2>/dev/null
git rm -q --ignore-unmatch "docs/previews/*.png"
mkdir -p docs/previews && mv preview.png docs/previews/$day.png
sed -i '' -E "s#\(docs/previews/[0-9-]+\.png\)#(docs/previews/$day.png)#" README.md
git add docs README.md catchup.sh && git commit -q -m "Morning brief $day" && git push -q && echo "published $day"
