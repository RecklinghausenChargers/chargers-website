#!/usr/bin/env python3
"""
Holt die aktuelle Verbandsliga-NRW-Tabelle von nrwfootball.de und schreibt sie
in data.json (Feld "tabelle"). Gedacht zum Ausführen durch den geplanten
GitHub-Actions-Job (siehe .github/workflows/update-tabelle.yml), jeden Sonntagabend.

Wichtig: Wenn sich die Struktur der nrwfootball.de-Seite ändert, bricht dieses
Skript absichtlich mit einem Fehler ab, statt data.json mit falschen oder leeren
Daten zu überschreiben. Ein Fehlschlag ist in den GitHub-Actions-Logs sichtbar
(Reiter "Actions" im Repository).
"""
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.nrwfootball.de/index.php/de/seniors-m/verbandsligen-seniors-m/vl-tabelle-2026/"
DATA_PATH = Path(__file__).resolve().parent.parent / "data.json"
ERWARTETE_MANNSCHAFTEN = 8  # Anzahl Teams in der Verbandsliga NRW 2026 — ggf. anpassen


def hole_tabelle_html() -> str:
    resp = requests.get(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0 (ChargersBot)"})
    resp.raise_for_status()
    return resp.text


def parse_zahl(text: str) -> int:
    text = text.strip().replace("+", "")
    if not text or text == "-":
        return 0
    return int(re.sub(r"[^\d-]", "", text) or 0)


def finde_tabelle(soup: BeautifulSoup):
    """Sucht unter allen <table>-Elementen die Tabelle mit der Liga-Tabelle,
    erkennbar an genau ERWARTETE_MANNSCHAFTEN Datenzeilen und dem Auftauchen
    von 'Recklinghausen' irgendwo im Text."""
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        text = table.get_text(" ", strip=True)
        if "Recklinghausen" in text and len(rows) >= ERWARTETE_MANNSCHAFTEN:
            return table
    return None


def parse_zeilen(table) -> list[dict]:
    zeilen = []
    for tr in table.find_all("tr"):
        zellen = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        if not zellen or not re.match(r"^\d+\.?$", zellen[0]):
            continue  # Kopfzeile oder leere Zeile überspringen
        if len(zellen) < 10:
            continue  # unerwartete Zeilenform, lieber überspringen als raten
        platz, team, spiele, punkte, siege, unentschieden, niederlagen, pf, pg, _diff = zellen[:10]
        zeilen.append({
            "platz": parse_zahl(platz),
            "team": team,
            "spiele": parse_zahl(spiele),
            "punkte": parse_zahl(punkte),
            "siege": parse_zahl(siege),
            "unentschieden": parse_zahl(unentschieden),
            "niederlagen": parse_zahl(niederlagen),
            "punkte_fuer": parse_zahl(pf),
            "punkte_gegen": parse_zahl(pg),
        })
    return zeilen


def main() -> int:
    html = hole_tabelle_html()
    soup = BeautifulSoup(html, "html.parser")
    table = finde_tabelle(soup)
    if table is None:
        print("FEHLER: Konnte die Tabelle auf nrwfootball.de nicht finden. "
              "Seite hat sich vermutlich geändert — data.json wird NICHT verändert.",
              file=sys.stderr)
        return 1

    zeilen = parse_zeilen(table)
    if len(zeilen) < ERWARTETE_MANNSCHAFTEN:
        print(f"FEHLER: Nur {len(zeilen)} von {ERWARTETE_MANNSCHAFTEN} erwarteten Zeilen "
              "gefunden — data.json wird NICHT verändert.", file=sys.stderr)
        return 1

    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    data["tabelle"]["zeilen"] = zeilen
    data["tabelle"]["stand"] = __import__("datetime").date.today().isoformat()
    data["tabelle"]["quelle"] = URL
    DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {len(zeilen)} Zeilen aktualisiert, Stand {data['tabelle']['stand']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
