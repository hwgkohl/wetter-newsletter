#!/usr/bin/env python3
"""Wetterabruf mit Selbstdiagnose. Quelle: Kachelmannwetter / Meteologix AG"""

import json, os, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.kachelmannwetter.com/v02"
ROOT = Path(__file__).resolve().parent
KEY = os.environ.get("KACHELMANN_API_KEY", "").strip()

KANDIDATEN = [
    "current/{lat}/{lon}",
    "forecast/{lat}/{lon}/advanced",
    "forecast/{lat}/{lon}/standard",
    "forecast/{lat}/{lon}/daily",
    "forecast/{lat}/{lon}/trend",
    "forecast/{lat}/{lon}",
]


def hole(pfad):
    url = f"{BASE}/{pfad}"
    url += "&units=metric" if "?" in url else "?units=metric"
    req = urllib.request.Request(url, headers={
        "X-API-Key": KEY, "Accept": "application/json",
        "User-Agent": "Oberursel-Newsletter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            koerper = e.read().decode("utf-8")[:300]
        except Exception:
            koerper = ""
        return e.code, koerper
    except Exception as e:
        return 0, str(e)[:300]


def kuerze(obj, tiefe=0):
    if tiefe > 3:
        return "..."
    if isinstance(obj, dict):
        return {k: kuerze(v, tiefe + 1) for k, v in list(obj.items())[:25]}
    if isinstance(obj, list):
        return [kuerze(x, tiefe + 1) for x in obj[:2]]
    return obj


def main():
    cfg = json.loads((ROOT / "orte.json").read_text(encoding="utf-8"))
    orte = list(cfg.get("orte", [])) + list(cfg.get("reiseorte", []))
    o = orte[0]

    bericht = {
        "erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quelle": "Kachelmannwetter / Meteologix AG",
        "key_vorhanden": bool(KEY),
        "key_laenge": len(KEY),
        "test": {},
    }

    treffer = None
    for muster in KANDIDATEN:
        status, inhalt = hole(muster.format(lat=o["lat"], lon=o["lon"]))
        bericht["test"][muster] = {
            "status": status,
            "vorschau": kuerze(inhalt) if status == 200 else inhalt,
        }
        if status == 200 and muster.startswith("forecast") and treffer is None:
            treffer = muster

    if treffer:
        bericht["gefundener_pfad"] = treffer
        bericht["orte"] = []
        for ort in orte:
            status, inhalt = hole(treffer.format(lat=ort["lat"], lon=ort["lon"]))
            bericht["orte"].append({
                "name": ort["name"],
                "status": status,
                "daten": kuerze(inhalt) if status == 200 else inhalt,
            })
    else:
        bericht["gefundener_pfad"] = None

    (ROOT / "wetter.json").write_text(
        json.dumps(bericht, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Diagnose geschrieben. Treffer:", treffer)


if __name__ == "__main__":
    main()
