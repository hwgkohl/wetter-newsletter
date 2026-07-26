#!/usr/bin/env python3
"""Wetterabruf. Quelle: Kachelmannwetter / Meteologix AG"""

import json, os, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.kachelmannwetter.com/v02"
ROOT = Path(__file__).resolve().parent
KEY = os.environ.get("KACHELMANN_API_KEY", "").strip()
STANDARD = ["current/{lat}/{lon}", "forecast/{lat}/{lon}/3day",
            "forecast/{lat}/{lon}/trend14days"]


def hole(pfad):
    url = f"{BASE}/{pfad}?units=metric"
    req = urllib.request.Request(url, headers={
        "X-API-Key": KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:250]
    except Exception as e:
        return 0, str(e)[:250]


def kuerze(o, t=0):
    if t > 3:
        return "..."
    if isinstance(o, dict):
        return {k: kuerze(v, t + 1) for k, v in list(o.items())[:25]}
    if isinstance(o, list):
        return [kuerze(x, t + 1) for x in o[:2]]
    return o


def main():
    cfg = json.loads((ROOT / "orte.json").read_text(encoding="utf-8"))
    orte = list(cfg.get("orte", [])) + list(cfg.get("reiseorte", []))
    pfade = cfg.get("pfade", STANDARD)
    b = {"erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "quelle": "Kachelmannwetter / Meteologix AG", "test": {}, "orte": []}

    treffer = None
    for m in pfade:
        s, i = hole(m.format(**orte[0]))
        b["test"][m] = {"status": s, "vorschau": kuerze(i) if s == 200 else i}
        if s == 200 and "forecast" in m and treffer is None:
            treffer = m

    b["gefundener_pfad"] = treffer
    for ort in orte:
        for m in ([treffer] if treffer else []) + ["current/{lat}/{lon}"]:
            s, i = hole(m.format(**ort))
            b["orte"].append({"ort": ort["name"], "pfad": m, "status": s,
                              "daten": kuerze(i) if s == 200 else i})

    (ROOT / "wetter.json").write_text(
        json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Treffer:", treffer)


main()
