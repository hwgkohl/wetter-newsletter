#!/usr/bin/env python3
"""Zweiter Sondierungslauf: Endpunktverzeichnis der Kachelmann-API auslesen.

Der erste Lauf ergab siebenmal HTTP 404 -- die geratenen Pfadnamen existieren
nicht. Ob die API ueberhaupt Pollen fuehrt, ist damit noch offen.

Statt weiter zu raten, holt dieses Skript die OpenAPI-Spezifikation. Die
Doku-Oberflaeche unter /v02/_doc.html laedt sie im Hintergrund; sie enthaelt
die vollstaendige Liste aller Endpunkte. Daraus laesst sich zweifelsfrei
ablesen, was es gibt und was nicht.

Aendert nichts, schreibt nur ins Log.
"""

import json, os, urllib.error, urllib.request

BASE = "https://api.kachelmannwetter.com/v02"
KEY = os.environ.get("KACHELMANN_API_KEY", "").strip()

SPEC_KANDIDATEN = [
    "_doc/openapi.json",
    "_doc/swagger.json",
    "openapi.json",
    "swagger.json",
    "_spec.json",
    "_doc.json",
    "api-docs",
    "_openapi",
]

STICHWORTE = ("pollen", "allerg", "bio", "air", "quality", "index", "health")


def hole_roh(pfad):
    req = urllib.request.Request(
        f"{BASE}/{pfad}",
        headers={"X-API-Key": KEY, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="replace")


print(f"Suche Spezifikation unter {BASE}\n")

spec = None
for pfad in SPEC_KANDIDATEN:
    try:
        roh = hole_roh(pfad)
        d = json.loads(roh)
        if isinstance(d, dict) and ("paths" in d or "openapi" in d or "swagger" in d):
            print(f"[OK ] {pfad}  -- Spezifikation gefunden\n")
            spec = d
            break
        print(f"[?  ] {pfad} -- JSON, aber keine Spezifikation")
    except urllib.error.HTTPError as ex:
        print(f"[{ex.code}] {pfad}")
    except Exception as ex:
        print(f"[ERR] {pfad}: {str(ex)[:90]}")

if not spec:
    print("\nKeine Spezifikation erreichbar.")
    print("Damit ist der Kachelmann-Weg ausgereizt: Wir wissen, dass sieben")
    print("plausible Pfadnamen nicht existieren, und kommen an das")
    print("Verzeichnis nicht heran. Empfehlung: DWD-Pollenflug-Gefahrenindex.")
    raise SystemExit(0)

pfade = sorted(spec.get("paths", {}).keys())
print(f"Die API kennt {len(pfade)} Endpunkte.\n")

treffer = [p for p in pfade if any(w in p.lower() for w in STICHWORTE)]
if treffer:
    print("--- Treffer zu Pollen, Luftqualitaet, Bio, Index ---")
    for p in treffer:
        methoden = ",".join(m.upper() for m in spec["paths"][p]
                            if m.lower() in ("get", "post"))
        print(f"  {methoden:6} {p}")
else:
    print("--- Kein Endpunkt enthaelt eines der Stichworte ---")

print("\n--- Vollstaendige Endpunktliste ---")
for p in pfade:
    print(f"  {p}")
