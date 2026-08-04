#!/usr/bin/env python3
"""Einmaliger Test: Liefert die Kachelmann-v02-API Pollendaten?

Aufruf im Repo, mit gesetztem KACHELMANN_API_KEY:
    python3 pollen_probe.py

Das Skript aendert nichts. Es probiert Kandidatenpfade fuer Oberursel und
gibt aus, was zurueckkommt -- Statuscode, und bei Erfolg die Struktur der
Antwort. Die Ausgabe bitte vollstaendig an die Redaktion schicken; daraus
laesst sich der richtige Pfad und das Feldmapping ableiten.
"""

import json, os, urllib.error, urllib.request

BASE = "https://api.kachelmannwetter.com/v02"
KEY = os.environ.get("KACHELMANN_API_KEY", "").strip()
LAT, LON = 50.2033, 8.5769          # Oberursel (Taunus)

KANDIDATEN = [
    f"pollen/{LAT}/{LON}",
    f"pollen/{LAT}/{LON}/3day",
    f"forecast/{LAT}/{LON}/pollen",
    f"airquality/{LAT}/{LON}",
    f"airquality/{LAT}/{LON}/pollen",
    f"bio/{LAT}/{LON}",
    f"index/{LAT}/{LON}/pollen",
]

if not KEY:
    raise SystemExit("KACHELMANN_API_KEY ist nicht gesetzt.")

print(f"Teste {len(KANDIDATEN)} Kandidatenpfade gegen {BASE}\n")

treffer = []
for pfad in KANDIDATEN:
    url = f"{BASE}/{pfad}?units=metric"
    req = urllib.request.Request(
        url, headers={"X-API-Key": KEY, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            roh = r.read().decode("utf-8")
        d = json.loads(roh)
        print(f"[OK ] {pfad}")
        print(f"      Top-Level-Schluessel: {list(d.keys())}")
        print(f"      Erste 400 Zeichen: {roh[:400]}\n")
        treffer.append(pfad)
    except urllib.error.HTTPError as ex:
        print(f"[{ex.code}] {pfad}")
    except Exception as ex:
        print(f"[ERR] {pfad}: {str(ex)[:100]}")

print()
if treffer:
    print("Brauchbare Pfade:", ", ".join(treffer))
else:
    print("Kein Kandidatenpfad liefert Daten.")
    print("Dann fuehrt der gebuchte Tarif keine Pollen und es bleibt bei")
    print("Variante A des Loesungsvorschlags: DWD-Pollenflug-Gefahrenindex.")
