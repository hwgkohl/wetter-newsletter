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
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
from pathlib import Path

BASE = "https://api.kachelmannwetter.com/v02"
DWD_POLLEN = ("https://opendata.dwd.de/climate_environment/health/alerts/"
              "s31fg.json")
POLLEN_PARTREGION = 92   # Hessen / Rhein-Main -- deckt Oberursel, Bad Homburg
                         # und Frankfurt ab. Aus der Datei selbst abgelesen,
                         # nicht geraten (Sondierung 04.08.2026).
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
    "sunshine": "sonnig",
}

# Kachelmann liefert Wind und Boeen in Metern pro Sekunde, obwohl die
# Pipeline sie bis zum 19.08.2026 als km/h weitergegeben hat. Belegt am
# 18.08.2026 an sieben lizenzierten Orten: Boeen x 3,6 treffen den Wert von
# kachelmannwetter.com und die Gegenquelle om_tage (Ouddorp 13,8 -> 49,7
# gegen 47 im Screenshot). Deshalb wird hier umgerechnet und der Rohwert
# zur Nachvollziehbarkeit daneben behalten.
MS_ZU_KMH = 3.6

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
    txt = TEXT.get(sym)
    d = {
        "datum": t.get("dateTime"),
        "tag": t.get("dayName"),
        "max": t.get("tempMax"),
        "min": t.get("tempMin"),
        "regen_prozent": t.get("precProb"),
        "regen_mm": t.get("precCurrent"),
        "wind_kmh": kmh(t.get("windSpeed")),
        "boeen_kmh": kmh(t.get("windGust")),
        "wind_ms_roh": t.get("windSpeed"),
        "boeen_ms_roh": t.get("windGust"),
        "sonne_std": t.get("sunHours"),
        "symbol": sym,
        "text": txt if txt else sym.replace("_", " "),
    }
    # Unbekannte Symbole werden ausgewiesen, nicht stillschweigend als
    # englisches Wort weitergegeben -- sonst landen sie unbemerkt im Blatt.
    if sym and txt is None:
        d["symbol_unbekannt"] = True
    return d


def kmh(wert):
    """Kachelmann-Windwert (m/s) in km/h. Nichtzahlen bleiben unangetastet."""
    if isinstance(wert, (int, float)):
        return round(wert * MS_ZU_KMH, 1)
    return wert


def astronomie(lat, lon):
    """Sonnenauf- und -untergang aus der Kachelmann-API.

    Endpunkt /tools/astronomy stammt aus dem Endpunktverzeichnis der API
    (Sondierung 04.08.2026). Die Feldnamen der Antwort sind noch NICHT
    verifiziert, deshalb wird die Rohantwort gespeichert und nicht auf
    eigene Feldnamen umgebogen. Sobald die Struktur bekannt ist, kann hier
    sauber gemappt werden.
    """
    return hole(f"tools/astronomy/{lat}/{lon}")


def trend14(lat, lon):
    """14-Tage-Trend, ebenfalls aus dem Endpunktverzeichnis.

    Auch hier zunaechst Rohantwort, aus demselben Grund.
    """
    return hole(f"forecast/{lat}/{lon}/trend14days")


def dwd_pollen():
    """Pollenflug-Gefahrenindex des DWD fuer das Teilgebiet Rhein-Main.

    Wichtig -- der Grund, warum hier nicht einfach 'today' genommen wird:
    Der DWD gibt die Datei taeglich erst gegen 11:00 Uhr neu aus. Wer davor
    baut, bekommt noch die Ausgabe des Vortags; deren Feld 'today' meint dann
    den GESTRIGEN Tag. Deshalb wird das Ausgabedatum gegen den Kalendertag
    geprueft und das passende Feld gewaehlt. Passt keines, wird die Luecke
    ausgewiesen -- nie ein Wert geraten.
    """
    with urllib.request.urlopen(DWD_POLLEN, timeout=25) as r:
        d = json.loads(r.read().decode("utf-8"))

    block = None
    for e in d.get("content", []):
        if e.get("partregion_id") == POLLEN_PARTREGION:
            block = e
            break
    if block is None:
        return {"fehler": f"Teilgebiet {POLLEN_PARTREGION} nicht in der Datei"}

    # Klartext aus der mitgelieferten Legende, nicht aus eigener Tabelle
    lg = d.get("legend", {})
    klartext = {}
    for k, v in lg.items():
        if k.endswith("_desc"):
            continue
        klartext[v] = lg.get(f"{k}_desc", "")

    # Ortszeit, nicht UTC: Die Pipeline laeuft auch um 22:07 und 23:07 UTC,
    # das ist in Berlin bereits der Folgetag. Mit UTC waere die Feldwahl dort
    # um einen Tag verschoben -- und zwar unbemerkt.
    heute = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Berlin")).date()

    stand_roh = (d.get("last_update") or "")[:10]
    try:
        stand = date.fromisoformat(stand_roh)
    except ValueError:
        return {"fehler": f"Ausgabedatum unlesbar: {d.get('last_update')!r}"}

    # Wie viele Tage liegt die Ausgabe zurueck? Danach richtet sich das Feld.
    versatz = (heute - stand).days
    feld = {0: "today", 1: "tomorrow", 2: "dayafter_to"}.get(versatz)
    if feld is None:
        return {"fehler": (f"Ausgabe vom {stand_roh} ist {versatz} Tage alt, "
                           f"kein passendes Feld -- Luecke ausweisen"),
                "stand": d.get("last_update")}

    arten = {}
    for art, werte in block.get("Pollen", {}).items():
        stufe = werte.get(feld)
        if stufe is None:
            continue
        arten[art] = {"stufe": stufe, "text": klartext.get(stufe, "")}

    return {
        "region": block.get("region_name"),
        "teilgebiet": block.get("partregion_name"),
        "stand": d.get("last_update"),
        "naechste_ausgabe": d.get("next_update"),
        "feld_verwendet": feld,
        "gilt_fuer": heute.isoformat(),
        "versatz_tage": versatz,
        "arten": arten,
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
         "hinweis_wind": ("Kachelmann liefert Wind und Boeen in m/s. Ab dem "
                          "19.08.2026 werden sie mit 3,6 in km/h umgerechnet; "
                          "der Rohwert steht in wind_ms_roh/boeen_ms_roh. "
                          "Kachelmann-Wind und om_tage-Wind bleiben trotzdem "
                          "unterschiedliche Groessen: om_tage fuehrt "
                          "Tagesmaxima, Kachelmann offenbar einen Mittelwert. "
                          "Bei den Boeen stimmen beide nach der Umrechnung "
                          "ueberein, beim Mittelwind nicht."),
         "orte": []}

    om = open_meteo(orte)

    try:
        b["pollen"] = dwd_pollen()
        b["pollen_quelle"] = "Deutscher Wetterdienst, Pollenflug-Gefahrenindex"
    except Exception as ex:
        b["pollen"] = {"fehler": str(ex)[:200]}

    # Kachelmann nur fuer lizenzierte Standorte anfragen. Alle uebrigen
    # wuerden 403 liefern; die Liste steht in orte.json unter
    # "kachelmann_orte". Fehlt der Schluessel, werden alle Orte angefragt.
    lizenziert = cfg.get("kachelmann_orte")

    for idx, o in enumerate(orte):
        e = {"name": o["name"], "reiseort": o in cfg.get("reiseorte", [])}
        if lizenziert is None or o["name"] in lizenziert:
            try:
                r = hole(f"forecast/{o['lat']}/{o['lon']}/3day")
                e["lauf"] = r.get("run")
                e["tage"] = [tag(t) for t in r.get("data", [])]
                # Fuer die Kernorte einen unveraenderten Tag mitschreiben.
                # Zweck: nachlesen, welche Windfelder die Antwort ueberhaupt
                # fuehrt (etwa ein Tagesmaximum neben windSpeed), ohne dafuer
                # einen eigenen Abruf zu brauchen. Nur Tag 0, nur Kernorte.
                if not e["reiseort"] and r.get("data"):
                    e["tag0_roh"] = r["data"][0]
            except Exception as ex:
                e["fehler"] = str(ex)[:200]
        else:
            e["kachelmann"] = "nicht lizenziert, uebersprungen"

        # Sonnenzeiten und 14-Tage-Trend nur fuer die vier Kernregionen
        if not e["reiseort"]:
            try:
                e["astro_roh"] = astronomie(o["lat"], o["lon"])
            except Exception as ex:
                e["astro_fehler"] = str(ex)[:120]
            try:
                e["trend14_roh"] = trend14(o["lat"], o["lon"])
            except Exception as ex:
                e["trend14_fehler"] = str(ex)[:120]

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

    p = b.get("pollen", {})
    if p.get("arten"):
        print(f"Pollen {p['teilgebiet']}: Stand {p['stand']}, "
              f"Feld '{p['feld_verwendet']}' fuer {p['gilt_fuer']}")
        for art, w in sorted(p["arten"].items()):
            print(f"  {art:10} {w['stufe']:4}  {w['text']}")
    else:
        print(f"Pollen nicht verfuegbar: {p.get('fehler')}")

    astro = sum(1 for o in b["orte"] if o.get("astro_roh"))
    tr = sum(1 for o in b["orte"] if o.get("trend14_roh"))
    print(f"Astronomie: {astro} Orte | 14-Tage-Trend: {tr} Orte")
    for o in b["orte"]:
        if o.get("astro_fehler"):
            print(f"  astro {o['name']}: {o['astro_fehler']}")
        if o.get("trend14_fehler"):
            print(f"  trend {o['name']}: {o['trend14_fehler']}")

    unbekannt = sorted({t["symbol"] for o in b["orte"]
                        for t in o.get("tage", []) if t.get("symbol_unbekannt")})
    if unbekannt:
        print(f"Unuebersetzte Wettersymbole: {', '.join(unbekannt)}")

    ok = sum(1 for o in b["orte"] if "tage" in o)
    ersatz = sum(1 for o in b["orte"] if o.get("quelle_ersatz"))
    stund = sum(1 for o in b["orte"] if o.get("stunden"))
    print(f"{ok} von {len(orte)} Orten abgerufen "
          f"({ersatz} davon per Open-Meteo-Ersatz, {stund} mit Stundenwerten)")


main()
