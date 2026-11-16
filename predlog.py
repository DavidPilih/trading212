#!/usr/bin/env python3
"""
predlog.py - izpiše naročilo, ki ga je pripravil pregled (narocilo.json), in ga
po tvoji potrditvi izvede prek t212_trgovanje.py (z vsemi njegovimi varovalkami).

Zagon:  run            (ali: python predlog.py)

narocilo.json (v isti mapi, ni v gitu):
{
  "id": "2026-11-18-smh",
  "velja_do": "2026-11-18",            # po tem datumu se ne izvede več
  "akcija": "kupi" | "prodaj" | "nic",
  "isin": "IE00BMC38736",              # kupi: ISIN (bot vzame EUR kotacijo)
  "ticker": "VVSMd_EQ",                # prodaj: T212 ticker
  "ime": "VanEck Semiconductor UCITS ETF",
  "kosi": 2.0,
  "limit": 62.50,                      # kupi: limitna cena v EUR
  "znesek_eur": 125,                   # najvišji dovoljeni znesek (kosi x limit ga ne sme preseči)
  "gtc": false,
  "razlog": "kratka utemeljitev"
}
Po izvedbi ali zavrnitvi se datoteka premakne v narocila_arhiv/, da se ne izvede dvakrat.
"""

import json
import os
import sys
from datetime import date, datetime

MAPA = os.path.dirname(os.path.abspath(__file__))
NAROCILO = os.path.join(MAPA, "narocilo.json")
ARHIV = os.path.join(MAPA, "narocila_arhiv")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def arhiviraj(n, status, izid=""):
    os.makedirs(ARHIV, exist_ok=True)
    n = dict(n, status=status, izid=izid, zakljuceno=datetime.now().isoformat(timespec="seconds"))
    ime = f"{n.get('id') or 'narocilo'}_{status}.json"
    with open(os.path.join(ARHIV, ime), "w", encoding="utf-8") as f:
        json.dump(n, f, indent=2, ensure_ascii=False)
    os.remove(NAROCILO)


def izpis(n):
    a = n["akcija"]
    print("=" * 46)
    print(f" PREDLOG: {a.upper()}  ({n.get('id', '')}, velja do {n.get('velja_do', '?')})")
    print("=" * 46)
    print(f" {n.get('ime', '')}")
    if a == "kupi":
        print(f" ISIN:    {n['isin']}  (bot vzame EUR kotacijo)")
        print(f" Kosov:   {n['kosi']}")
        print(f" Limit:   {n['limit']:.2f} EUR / kos")
        print(f" Največ:  {n['kosi'] * n['limit']:.2f} EUR"
              f"{'  (velja do preklica)' if n.get('gtc') else '  (velja danes)'}")
    else:
        print(f" Ticker:  {n['ticker']}")
        print(f" Kosov:   {n['kosi']}  (tržna prodaja)")
    print(f" Razlog:  {n.get('razlog', '')}")
    print("-" * 46)


def preveri(n):
    a = n.get("akcija")
    if a not in ("kupi", "prodaj", "nic"):
        raise ValueError(f"neznana akcija: {a}")
    if a == "nic":
        return
    n["kosi"] = float(n["kosi"])
    if n["kosi"] <= 0:
        raise ValueError("kosi morajo biti pozitivni")
    if a == "kupi":
        n["limit"] = float(n["limit"])
        meja = float(n["znesek_eur"])
        if n["kosi"] * n["limit"] > meja + 0.01:
            raise ValueError(f"kosi x limit = {n['kosi'] * n['limit']:.2f} EUR presega znesek {meja:.2f} EUR")
        if not n.get("isin"):
            raise ValueError("manjka isin")
    elif not n.get("ticker"):
        raise ValueError("manjka ticker")


def main():
    if not os.path.exists(NAROCILO):
        print("Ni novega predloga. (Ko ga pregled pripravi, ga vidiš tukaj.)")
        print("Stanje računa: run povzetek")
        return 0
    with open(NAROCILO, encoding="utf-8") as f:
        n = json.load(f)
    try:
        preveri(n)
    except (ValueError, KeyError) as e:
        print(f"Predlog je pokvarjen ({e}), zato ga ne izvedem.")
        return 1

    if n["akcija"] == "nic":
        print(f"Danes nič. {n.get('razlog', '')}")
        arhiviraj(n, "nic")
        return 0

    velja_do = n.get("velja_do")
    if velja_do and date.today() > date.fromisoformat(velja_do):
        print(f"Predlog {n.get('id')} je potekel ({velja_do}), zato ga ne izvedem.")
        arhiviraj(n, "potekel")
        return 0

    import t212_portfolio as t
    import t212_trgovanje as b
    from t212_portfolio import T212Napaka
    t.nalozi_env()

    izpis(n)
    try:
        if n["akcija"] == "kupi":
            suho = b.kupi(n["isin"], n["kosi"], n["limit"], gtc=bool(n.get("gtc")), potrdi=False)
        else:
            suho = b.prodaj(n["ticker"], n["kosi"], potrdi=False)
    except T212Napaka as e:
        print(f"Bot ga ne bi izvedel: {e}")
        print("Predlog ostane; nič ni oddano.")
        return 1
    print(" Bot: " + suho.replace(" Za oddajo dodaj --potrdi.", ""))
    print("-" * 46)

    try:
        odgovor = input("Izvedem? Napiši da ali ne: ").strip().lower()
    except EOFError:
        print("\nNi odgovora, nič ni oddano. Predlog ostane.")
        return 1
    if odgovor not in ("da", "d", "ja", "yes", "y"):
        arhiviraj(n, "zavrnjen")
        print("Zavrnjeno. Nič ni oddano.")
        return 0

    try:
        if n["akcija"] == "kupi":
            izid = b.kupi(n["isin"], n["kosi"], n["limit"], gtc=bool(n.get("gtc")), potrdi=True)
        else:
            izid = b.prodaj(n["ticker"], n["kosi"], potrdi=True)
    except T212Napaka as e:
        print(f"NAPAKA, naročilo ni oddano: {e}")
        return 1
    arhiviraj(n, "izveden", izid)
    print(izid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
