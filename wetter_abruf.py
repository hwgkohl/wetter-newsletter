#!/usr/bin/env python3
"""Wetterabruf fuer den Oberursel-Newsletter.

Quelle 1: Kachelmannwetter / Meteologix AG (Tageswerte, API-Key noetig)
Quelle 2: Open-Meteo (Tageswerte zur Gegenprobe + Stundenwerte, kein Key)

Open-Meteo ist bewusst als zweite, unabhaengige Quelle drin:
- liefert Stundenwerte fuer Niederschlag (Tagessummen allein sind irrefuehrend)
- springt ein, wenn Kachelmann fuer einen Ort ausfaellt
- ermoeglicht eine Abweichungspruefung zwischen beiden Modellen
"""

import json, os, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://api.kachelmannwetter.com/v02"
OM_BASE = "https://api.open-meteo.com/v1/forecast"
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

# WMO-Wettercodes von Open-Meteo, auf die vorhandene Textlogik gemappt
WMO = {
    0: "klar", 1: "meist sonnig", 2: "heiter", 3: "bedeckt",
    45: "Nebel", 48: "Nebel", 51: "Nieselregen", 53: "Nieselregen",
    55: "Nieselregen", 61: "leichter Regen", 63: "Regen", 65: "starker Regen",
    71: "Schnee", 73: "Schnee", 75: "starker Schnee", 77: "Schneegriesel",
    80: "Regenschauer", 81: "Regenschauer", 82: "starke Regenschauer",
    85: "Schneeschauer", 86: "Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Gewitter mit Hagel",
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


def open_meteo(orte):
    """Holt alle Orte in einem einzigen Request.

    Rueckgabe: Liste in derselben Reihenfolge wie 'orte', je Ort ein dict
    mit 'tage' (3 Tage) und 'stunden' (nur heute, 00-23 Uhr).
    Bei Fehler: Liste gleicher Laenge mit None-Eintraegen.
    """
    p = urllib.parse.urlencode({
        "latitude": ",".join(str(o["lat"]) for o in orte),
        "longitude": ",".join(str(o["lon"]) for o in orte),
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                  "precipitation_sum,precipitation_probability_max,"
                  "sunshine_duration,wind_speed_10m_max,wind_gusts_10m_max"),
        "hourly": "temperature_2m,precipitation,precipitation_probability",
        "timezone": "Europe/Berlin",
        "forecast_days": 3,
    })
    try:
        with urllib.request.urlopen(f"{OM_BASE}?{p}", timeout=25) as r:
            roh = json.loads(r.read().decode("utf-8"))
    except Exception as ex:
        print(f"Open-Meteo nicht erreichbar: {str(ex)[:120]}")
        return [None] * len(orte)

    # Bei einer einzelnen Koordinate liefert die API kein Array zurueck
    if isinstance(roh, dict):
        roh = [roh]
    if len(roh) != len(orte):
        print(f"Open-Meteo: {len(roh)} Antworten fuer {len(orte)} Orte")
        return [None] * len(orte)

    aus = []
    for d in roh:
        dd = d.get("daily", {})
        tage = []
        for i, datum in enumerate(dd.get("time", [])):
            sek = dd.get("sunshine_duration", [None] * 9)[i]
            code = dd.get("weather_code", [None] * 9)[i]
            tage.append({
                "datum": datum,
                "max": dd.get("temperature_2m_max", [None] * 9)[i],
                "min": dd.get("temperature_2m_min", [None] * 9)[i],
                "regen_prozent": dd.get(
                    "precipitation_probability_max", [None] * 9)[i],
                "regen_mm": dd.get("precipitation_sum", [None] * 9)[i],
                "wind_kmh": dd.get("wind_speed_10m_max", [None] * 9)[i],
                "boeen_kmh": dd.get("wind_gusts_10m_max", [None] * 9)[i],
                "sonne_std": (round(sek / 3600.0, 1)
                              if isinstance(sek, (int, float)) else None),
                "text": WMO.get(code, ""),
            })

        hh = d.get("hourly", {})
        zeiten = hh.get("time", [])
        heute = tage[0]["datum"] if tage else ""
        stunden = []
        for i, z in enumerate(zeiten):
            if not z.startswith(heute):
                continue
            stunden.append({
                "zeit": z[11:16],
                "temp": hh.get("temperature_2m", [None] * len(zeiten))[i],
                "regen_mm": hh.get("precipitation", [None] * len(zeiten))[i],
                "regen_prozent": hh.get(
                    "precipitation_probability", [None] * len(zeiten))[i],
            })
        aus.append({"tage": tage, "stunden": stunden})
    return aus


def main():
    cfg = json.loads((ROOT / "orte.json").read_text(encoding="utf-8"))
    orte = list(cfg.get("orte", [])) + list(cfg.get("reiseorte", []))
    b = {"erzeugt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "quelle": "Kachelmannwetter / Meteologix AG",
         "quelle_2": "Open-Meteo (CC BY 4.0)",
         "orte": []}

    om = open_meteo(orte)

    for idx, o in enumerate(orte):
        e = {"name": o["name"], "reiseort": o in cfg.get("reiseorte", [])}
        try:
            r = hole(f"forecast/{o['lat']}/{o['lon']}/3day")
            e["lauf"] = r.get("run")
            e["tage"] = [tag(t) for t in r.get("data", [])]
        except Exception as ex:
            e["fehler"] = str(ex)[:200]

        if om[idx]:
            e["om_tage"] = om[idx]["tage"]
            e["stunden"] = om[idx]["stunden"]
            # Wenn Kachelmann ausgefallen ist, Open-Meteo hochstufen
            if "tage" not in e:
                e["tage"] = om[idx]["tage"]
                e["quelle_ersatz"] = "Open-Meteo"

        b["orte"].append(e)

    (ROOT / "wetter.json").write_text(
        json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for o in b["orte"] if "tage" in o)
    ersatz = sum(1 for o in b["orte"] if o.get("quelle_ersatz"))
    stund = sum(1 for o in b["orte"] if o.get("stunden"))
    print(f"{ok} von {len(orte)} Orten abgerufen "
          f"({ersatz} davon per Open-Meteo-Ersatz, {stund} mit Stundenwerten)")


main()
