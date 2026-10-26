"""Economic calendar for the current week (Forex Factory feed), in Paris time.

    python macro_calendar.py          # today and tomorrow, medium and high impact
    python macro_calendar.py --week   # rest of the week
"""
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
PARIS = ZoneInfo("Europe/Paris")


def events(days=1, impacts=("High", "Medium")):
    """Events from today to today + days, as dicts with a Paris-time datetime."""
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    start = date.today()
    out = []
    for e in json.load(urllib.request.urlopen(req, timeout=20)):
        when = datetime.fromisoformat(e["date"]).astimezone(PARIS)
        if e["impact"] in impacts and start <= when.date() <= start + timedelta(days=days):
            out.append({"when": when, "currency": e["country"], "title": e["title"], "impact": e["impact"],
                        "forecast": e["forecast"] or "–", "previous": e["previous"] or "–"})
    return out


def main():
    print("| Day | Time (Paris) | Ccy | Event | Impact | Forecast | Previous |\n|---|---|---|---|---|---|---|")
    for e in events(7 if "--week" in sys.argv else 1):
        print(f"| {e['when']:%a %d/%m} | {e['when']:%H:%M} | {e['currency']} | {e['title']} | {e['impact']} "
              f"| {e['forecast']} | {e['previous']} |")


if __name__ == "__main__":
    main()
