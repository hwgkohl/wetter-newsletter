#!/usr/bin/env python3
"""
Taeglicher Wetterabruf fuer den Oberursel-Newsletter.
Datenquelle: Kachelmannwetter / Meteologix AG
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.kachelmannwetter.com/v02"
ROOT = Path(__file__).resolve().parent
KEY = os.environ.get("KACHELMANN_API_KEY", "").strip()


def hole(pfad: str, versuche: int = 3) -> dict:
    url = f"{BASE}/{pfad}"
    url += "&units=metric" if "?" in url else "?units=metric"
    letzter = None
    for n in range(versuche):
        req = urllib.request.Request(url, headers={
            "X-API-Key": KEY,
            "Accept": "application/json",
            "User-Agent": "Oberursel-Newsletter/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise
            letzter = f"HTTP {e.code}"
        except Exception as e:
            letzter = str(e)
        time.sleep(2 ** n)
    raise RuntimeError(letzter or "unbekannt")


def zahl(feld):
    if isinstance(feld, dict):
        feld = feld.get("value")
    if feld is None:
        return None
    try:
        return round(float(feld))
    except (TypeError, ValueError):
        return None


def destilliere(roh: dict, tage: int = 2) -> list:
    daten = roh.get("data", roh)
    if isinstance(daten, dict):
        for schluessel in ("days", "daily", "items", "forecast"):
            if isinstance(daten.get(schluessel), list):
                daten = daten[schluessel]
                break
    if not isinstance(daten, list):
        return []

    out = []
    for eintrag in daten[:tage]:
        if not isinstance(eintrag, dict):
            continue
        out.append({
            "datum": (eintrag.get("dateTime") or eintrag.get("date")
                      or eintrag.get("day") or "")[:10],
            "max": zahl(eintrag.get("tempMax") or eintrag.get("tmax")
                        or eintrag.get("temperatureMax")),
            "min": zahl(eintrag.get("tempMin") or eintrag.get("tmin")
                        or eintrag.get("temperatureMin")),
            "text": (eintrag.get("weatherText") or eintrag.get("symbolText")
                     or eintrag.get("description") or ""),
            "symbol": eintrag.get("symbol") or eintrag.get("weatherSymbol"),
            "regen_mm": zahl(eintrag.get("precSum") or eintrag.get("prec")),
            "wind_kmh": zahl(eintrag.get("windSpeed") or eintrag.get("wind")),
        })
    return out


def main() -> None:
    if not KEY:
        sys.exit("FEHLER: Secret KACHELMANN_API_KEY fehlt.")

    cfg = json.loads((ROOT / "orte.json").read_text(encoding="utf-8"))
    muster = cfg.get("forecast_pfad", "forecast/{lat}/{lon}/advanced")
    reise = cfg.get("reiseorte", [])
    alle = list(cfg.get("orte", [])) + list(reise)

    ergebnis = {
        "erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "quelle": "Kachelmannwetter / Meteologix AG",
        "orte": [],
    }
    fehler = []

    for o in alle:
        pfad = muster.format(lat=o["lat"], lon=o["lon"])
        eintrag = {"name": o["name"], "reiseort": o in reise}
        try:
            eintrag["tage"] = destilliere(hole(pfad))
            if not eintrag["tage"]:
                eintrag["fehler"] = "Antwort ohne verwertbare Tageswerte"
                fehler.append(o["name"])
        except Exception as e:
            eintrag["fehler"] = str(e)
            fehler.append(o["name"])
        ergebnis["orte"].append(eintrag)

    if len(fehler) == len(alle):
        sys.exit(f"FEHLER: kein Ort lieferte Daten. "
                 f"Erste Meldung: {ergebnis['orte'][0].get('fehler')}")

    (ROOT / "wetter.json").write_text(
        json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK - {len(alle) - len(fehler)} von {len(alle)} Orten abgerufen")
    if fehler:
        print(f"WARNUNG: keine Daten fuer {', '.join(fehler)}")


if __name__ == "__main__":
    main()
