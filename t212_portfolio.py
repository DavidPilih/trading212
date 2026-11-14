#!/usr/bin/env python3
"""
t212_portfolio.py - preveri stanje Trading 212 računa (SAMO BRANJE).

Vse funkcije pošiljajo le GET zahteve na uradni Trading 212 Public API:
  /equity/account/summary  -> gotovina, vrednost naložb, dobiček/izguba
  /equity/positions        -> odprte pozicije

Ta datoteka sama ne oddaja naročil. Nakup in prodaja (z varovalkami) sta
ločena v t212_trgovanje.py.

Ključ in skrivnost bere iz datoteke .env v isti mapi (ali iz okoljskih spremenljivk):
  API_KEY          - API ključ (obvezno)
  SECRET_KEY       - API skrivnost (obvezno za nove ključe)
  T212_OKOLJE      - "live" (privzeto) ali "demo"

Zagon:
  python t212_portfolio.py              -> celoten povzetek (za copy-paste)
  python t212_portfolio.py vrednost     -> samo skupna vrednost računa
  python t212_portfolio.py gotovina     -> samo gotovina
  python t212_portfolio.py pozicije     -> samo pozicije
  python t212_portfolio.py pozicija EQQB    -> ena pozicija (ticker ali ISIN)
  python t212_portfolio.py --shrani     -> povzetek še doda v stanje_t212.txt

Uporablja samo standardno knjižnico Pythona (nič ni treba nameščati s pip).
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime

MAPA = os.path.dirname(os.path.abspath(__file__))

OSNOVNI_URL = {
    "live": "https://live.trading212.com/api/v0",
    "demo": "https://demo.trading212.com/api/v0",
}


# --------------------------------------------------------------------------
# Nastavitve in povezava z API
# --------------------------------------------------------------------------

def nalozi_env(pot=os.path.join(MAPA, ".env")):
    """Prebere KEY=VALUE vrstice iz .env v os.environ (obstoječih ne prepiše)."""
    if not os.path.exists(pot):
        return
    with open(pot, encoding="utf-8") as f:
        for vrstica in f:
            vrstica = vrstica.strip()
            if not vrstica or vrstica.startswith("#") or "=" not in vrstica:
                continue
            kljuc, vrednost = vrstica.split("=", 1)
            vrednost = vrednost.strip().strip('"').strip("'")
            if vrednost and not os.environ.get(kljuc.strip()):
                os.environ[kljuc.strip()] = vrednost


class T212Napaka(Exception):
    pass


def _glava_avtentikacije():
    kljuc = (os.environ.get("API_KEY") or os.environ.get("T212_API_KEY") or "").strip()
    skrivnost = (os.environ.get("SECRET_KEY") or os.environ.get("T212_API_SECRET") or "").strip()
    if not kljuc:
        raise T212Napaka("API_KEY ni nastavljen. Vpiši ga v datoteko .env.")
    if skrivnost:
        # HTTP Basic: uporabnik = ključ, geslo = skrivnost.
        return "Basic " + base64.b64encode(f"{kljuc}:{skrivnost}".encode()).decode()
    # Starejši ključi brez skrivnosti: ključ gre neposredno v glavo.
    return kljuc


def _klic(pot, metoda="GET", telo=None):
    """Klic na API. Ta datoteka uporablja samo GET; POST/DELETE kliče le t212_trgovanje.py."""
    okolje = os.environ.get("T212_OKOLJE", "live").strip().lower() or "live"
    if okolje not in OSNOVNI_URL:
        raise T212Napaka('T212_OKOLJE mora biti "live" ali "demo".')
    podatki = json.dumps(telo).encode() if telo is not None else None
    glave = {"Authorization": _glava_avtentikacije(), "Accept": "application/json"}
    if podatki is not None:
        glave["Content-Type"] = "application/json"
    zahteva = urllib.request.Request(OSNOVNI_URL[okolje] + pot, data=podatki, method=metoda, headers=glave)
    try:
        with urllib.request.urlopen(zahteva, timeout=20) as odgovor:
            vsebina = odgovor.read().decode()
            return json.loads(vsebina) if vsebina.strip() else None
    except urllib.error.HTTPError as e:
        razlage = {
            401: "ključ ali skrivnost ni pravilna (ali napačno okolje live/demo).",
            403: "ključ nima potrebnega dovoljenja.",
            429: "preveč zahtev naenkrat. Počakaj 10 sekund in poskusi znova.",
        }
        try:
            podrobno = e.read().decode()[:300]
        except Exception:
            podrobno = ""
        raise T212Napaka(f"{metoda} {pot} -> HTTP {e.code}: {razlage.get(e.code, e.reason)} {podrobno}".strip())
    except urllib.error.URLError as e:
        raise T212Napaka(f"ni povezave do Trading 212 ({e.reason}).")


def _get(pot):
    return _klic(pot, "GET")


# --------------------------------------------------------------------------
# Bralne funkcije (vračajo podatke kot slovarje / sezname)
# --------------------------------------------------------------------------

def pridobi_racun():
    """Surov povzetek računa (/equity/account/summary)."""
    return _get("/equity/account/summary") or {}


def pridobi_pozicije():
    """Surov seznam odprtih pozicij (/equity/positions)."""
    return _get("/equity/positions") or []


def preveri_gotovino(racun=None):
    """Gotovina: prosto, rezervirano za naročila, v pitah."""
    racun = racun or pridobi_racun()
    g = racun.get("cash") or {}
    return {
        "valuta": racun.get("currency", ""),
        "prosto": g.get("availableToTrade") or 0,
        "rezervirano": g.get("reservedForOrders") or 0,
        "v_pitah": g.get("inPies") or 0,
    }


def preveri_vrednost(racun=None):
    """Skupna vrednost računa, vrednost naložb, vloženo in dobiček/izguba."""
    racun = racun or pridobi_racun()
    n = racun.get("investments") or {}
    gotovina = preveri_gotovino(racun)
    nalozbe = n.get("currentValue") or 0
    vlozeno = n.get("totalCost") or 0
    nerealiziran = n.get("unrealizedProfitLoss") or 0
    return {
        "valuta": racun.get("currency", ""),
        "skupaj": gotovina["prosto"] + gotovina["rezervirano"] + gotovina["v_pitah"] + nalozbe,
        "nalozbe": nalozbe,
        "vlozeno": vlozeno,
        "nerealiziran_di": nerealiziran,
        "nerealiziran_di_odstotek": (100 * nerealiziran / vlozeno) if vlozeno else None,
        "realiziran_di": n.get("realizedProfitLoss") or 0,
    }


def preveri_pozicije(pozicije=None):
    """Odprte pozicije, urejene po vrednosti (največja prva)."""
    pozicije = pridobi_pozicije() if pozicije is None else pozicije
    rezultat = []
    for p in pozicije:
        instr = p.get("instrument") or {}
        den = p.get("walletImpact") or {}
        vlozeno = den.get("totalCost")
        di = den.get("unrealizedProfitLoss")
        rezultat.append({
            "ticker": instr.get("ticker", "?"),
            "isin": instr.get("isin", "?"),
            "ime": instr.get("name", ""),
            "kolicina": p.get("quantity"),
            "povp_cena": p.get("averagePricePaid"),
            "trenutna_cena": p.get("currentPrice"),
            "valuta_instrumenta": instr.get("currency", ""),
            "vrednost": den.get("currentValue"),
            "vlozeno": vlozeno,
            "di": di,
            "di_odstotek": (100 * di / vlozeno) if (di is not None and vlozeno) else None,
            "valuta_vpliv": den.get("fxImpact"),
            "valuta": den.get("currency", ""),
        })
    return sorted(rezultat, key=lambda x: -(x["vrednost"] or 0))


def preveri_pozicijo(oznaka, pozicije=None):
    """Ena pozicija po tickerju (npr. EQQB) ali ISIN. Vrne None, če je ni."""
    oznaka = oznaka.upper()
    for p in preveri_pozicije(pozicije):
        if oznaka in (p["isin"].upper(), p["ticker"].upper(), kratek_ticker(p["ticker"]).upper()):
            return p
    return None


# --------------------------------------------------------------------------
# Oblikovanje izpisa
# --------------------------------------------------------------------------

def st(x, dec=2):
    """Število v slovenskem zapisu: 1234.5 -> 1.234,50"""
    if x is None:
        return "?"
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pred(x, dec=2):
    """Število s predznakom: +1,23 ali -1,23"""
    if x is None:
        return "?"
    return ("+" if x >= 0 else "") + st(x, dec)


def kratek_ticker(t):
    # "EQQB_DE_EQ" ali "EQQBd_EQ" -> "EQQB"
    return t.split("_")[0].rstrip("d") if t else "?"


def _odst(x):
    return f" ({pred(x)} %)" if x is not None else ""


def besedilo_vrednost(v):
    return (
        f"Skupaj račun: {st(v['skupaj'])} {v['valuta']}\n"
        f"Naložbe: {st(v['nalozbe'])} {v['valuta']} (vloženo {st(v['vlozeno'])})\n"
        f"Nerealiziran D/I: {pred(v['nerealiziran_di'])} {v['valuta']}{_odst(v['nerealiziran_di_odstotek'])}"
        f" | Realiziran D/I (vse): {pred(v['realiziran_di'])} {v['valuta']}"
    )


def besedilo_gotovina(g):
    s = f"Gotovina: {st(g['prosto'])} {g['valuta']}"
    if g["rezervirano"]:
        s += f" + rezervirano za naročila {st(g['rezervirano'])}"
    if g["v_pitah"]:
        s += f" + v pitah {st(g['v_pitah'])}"
    return s


def besedilo_pozicija(p):
    s = (
        f"- {kratek_ticker(p['ticker'])} [{p['ticker']}, {p['isin']}] {p['ime']}: "
        f"{st(p['kolicina'], 6)} kos | povp. cena {st(p['povp_cena'], 4)} {p['valuta_instrumenta']} | "
        f"zdaj {st(p['trenutna_cena'], 4)} {p['valuta_instrumenta']} | "
        f"vrednost {st(p['vrednost'])} {p['valuta']} | "
        f"D/I {pred(p['di'])} {p['valuta']}{_odst(p['di_odstotek'])}"
    )
    if p["valuta_vpliv"]:
        s += f" (od tega valuta {pred(p['valuta_vpliv'])} {p['valuta']})"
    return s


def besedilo_pozicije(pozicije):
    if not pozicije:
        return "Pozicije: ni odprtih pozicij"
    return "Pozicije:\n" + "\n".join(besedilo_pozicija(p) for p in pozicije)


def povzetek():
    """Celoten povzetek računa kot besedilo (dva GET klica)."""
    racun = pridobi_racun()
    pozicije = preveri_pozicije()
    cas = datetime.now().strftime("%d. %m. %Y %H:%M")
    return "\n".join([
        f"=== Trading 212 stanje {cas} ({racun.get('currency', '')}) ===",
        besedilo_vrednost(preveri_vrednost(racun)),
        besedilo_gotovina(preveri_gotovino(racun)),
        besedilo_pozicije(pozicije),
    ])


# --------------------------------------------------------------------------
# Ukazna vrstica
# --------------------------------------------------------------------------

def main(argumenti):
    nalozi_env()
    shrani = "--shrani" in argumenti
    argumenti = [a for a in argumenti if a != "--shrani"]
    ukaz = argumenti[0].lower() if argumenti else "povzetek"

    if ukaz == "povzetek":
        izpis = povzetek()
    elif ukaz == "vrednost":
        izpis = besedilo_vrednost(preveri_vrednost())
    elif ukaz == "gotovina":
        izpis = besedilo_gotovina(preveri_gotovino())
    elif ukaz == "pozicije":
        izpis = besedilo_pozicije(preveri_pozicije())
    elif ukaz == "pozicija" and len(argumenti) > 1:
        p = preveri_pozicijo(argumenti[1])
        izpis = besedilo_pozicija(p) if p else f"Pozicije {argumenti[1]} ni v portfelju."
    else:
        print(__doc__)
        return 2

    print(izpis)
    if shrani:
        datoteka = os.path.join(MAPA, "stanje_t212.txt")
        with open(datoteka, "a", encoding="utf-8") as f:
            f.write(izpis + "\n\n")
        print(f"\n(Dodano v {datoteka})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except T212Napaka as e:
        print("NAPAKA: " + str(e), file=sys.stderr)
        sys.exit(1)
