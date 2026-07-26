#!/usr/bin/env python3
"""Wetterabruf fuer den Oberursel-Newsletter.
Quelle: Kachelmannwetter / Meteologix AG"""

import json, os, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.kachelmannwetter.com/v02"
ROOT = Path(__file__).resolve().parent
KEY = os.environ.get("KACHELMANN_API_KEY", "").strip()

TEXT = {
    "clear": "klar", "sunny": "sonnig", "mostlysunny": "meist sonnig",
    "partlycloudy": "heiter", "mostlycloudy": "stark bewoelkt",
    "cloudy": "bewoelkt", "overcast": "bedeckt", "fog": "Nebel",
    "rain": "Regen", "lightrain": "leichter Regen", "heavyrain": "starker Regen",
    "showers": "Schauer", "rainshowers": "Regenschauer",
    "thunderstorm": "Gewitter", "thunderstorms": "Gewitter",
    "snow": "Schnee", "snowshowers": "Schneeschauer", "sleet": "Schneeregen",
    "hail": "Hagel", "drizzle": "Nieselregen",
}


def hole(pfad):
    req = urllib.request.Request(
        f"{BASE}/{pfad}?units=metric",
        headers={"X-API-Key": KEY, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def tag(t):
    sym = t.get("weatherSymbol") or ""
    return {
        "datum": t.get("dateTime"),
        "tag": t.get("dayName"),
        "max": t.get("tempMax"),
        "min": t.get("tempMin"),
        "regen_prozent": t.get("precProb"),
        "regen_mm": t.get("precCurrent"),
        "wind_kmh": t.get("windSpeed"),
        "boeen_kmh": t.get("windGust"),
        "sonne_std": t.get("sunHours"),
        "symbol": sym,
        "text": TEXT.get(sym, sym.replace("_", " ")),
    }


def main():
    cfg = json.loads((ROOT / "orte.json").read_text(encoding="utf-8"))
    orte = list(cfg.get("orte", [])) + list(cfg.get("reiseorte", []))
    b = {"erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "quelle": "Kachelmannwetter / Meteologix AG", "orte": []}

    for o in orte:
        e = {"name": o["name"], "reiseort": o in cfg.get("reiseorte", [])}
        try:
            r = hole(f"forecast/{o['lat']}/{o['lon']}/3day")
            e["lauf"] = r.get("run")
            e["tage"] = [tag(t) for t in r.get("data", [])]
        except Exception as ex:
            e["fehler"] = str(ex)[:200]
        b["orte"].append(e)

    (ROOT / "wetter.json").write_text(
        json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for o in b["orte"] if "tage" in o)
    print(f"{ok} von {len(orte)} Orten abgerufen")


main()
