#!/usr/bin/env python3
"""
t212_trgovanje.py - nakup in prodaja prek Trading 212 API, s trdimi varovalkami.

VAROVALKE (v kodi, ne v nastavitvah):
  1. Proračun: bot lahko za nakupe SKUPAJ porabi največ 500 EUR (MAX_PRORACUN_EUR).
     Z BOT_PRORACUN_EUR v .env ga lahko samo ZNIŽAŠ, nikoli zvišaš.
     Prodaje proračuna ne vračajo: 500 EUR je skupna poraba v celotni življenjski dobi bota.
  2. Nakup samo z LIMITNIM naročilom za instrument v EUR, da je najvišji možni strošek
     (količina x limitna cena) znan vnaprej. Ta znesek se rezervira, preden se naročilo odda.
  3. Prodaja samo tistega, kar je kupil bot: količina iz njegovih NAPOLNJENIH nakupov,
     zmanjšana za njegove prejšnje prodaje, in nikoli več, kot je trenutno v poziciji.
     Delnic, ki so bile na računu prej ali kupljene ročno, bot ne more prodati.
  4. Preklic samo naročil, ki jih je oddal bot.
  5. Brez zastavice --potrdi se nič ne odda, izpiše se le, kaj bi se zgodilo.

Bot vodi dnevnik v bot_dnevnik.json (v isti mapi). NE BRIŠI GA: brez njega bot
pozabi porabo (proračun bi se ponastavil) in ne bi smel prodati ničesar.

Zagon:
  python t212_trgovanje.py stanje
  python t212_trgovanje.py kupi IE00BMC38736 0.5 30.00 [--gtc] --potrdi   (ISIN ali ticker; vedno kupi EUR kotacijo)
  python t212_trgovanje.py prodaj EQQBd_EQ 0.5 --potrdi
  python t212_trgovanje.py preklici <id_narocila> --potrdi
  python t212_trgovanje.py rocno IE00B53SZB19 0.225 1440.62   (zapiše ročni nakup iz aplikacije v proračun)

Ticker je poln Trading 212 ticker (npr. EQQBd_EQ). Poiščeš ga z:
  python t212_trgovanje.py najdi IE00BFZXGZ54

Najprej preizkusi na demo računu (T212_OKOLJE=demo v .env).
"""

import json
import os
import sys
from datetime import datetime

import t212_portfolio as t
from t212_portfolio import T212Napaka

MAX_PRORACUN_EUR = 500.0  # trda zgornja meja, ne spreminjaj
DNEVNIK = os.path.join(t.MAPA, "bot_dnevnik.json")
EPS = 1e-9


# --------------------------------------------------------------------------
# Dnevnik
# --------------------------------------------------------------------------

def preberi_dnevnik():
    if not os.path.exists(DNEVNIK):
        return {"nakupi": [], "prodaje": [], "rocni": []}
    with open(DNEVNIK, encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("rocni", [])  # ročni nakupi iz aplikacije: štejejo v proračun, bot jih ne prodaja
    return d


def shrani_dnevnik(d):
    zacasna = DNEVNIK + ".tmp"
    with open(zacasna, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
    os.replace(zacasna, DNEVNIK)


def _zdaj():
    return datetime.now().isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Proračun
# --------------------------------------------------------------------------

def proracun():
    """Veljavni proračun: najmanj od 500 in BOT_PRORACUN_EUR."""
    try:
        nastavljen = float(os.environ.get("BOT_PRORACUN_EUR") or MAX_PRORACUN_EUR)
    except ValueError:
        nastavljen = MAX_PRORACUN_EUR
    return max(0.0, min(MAX_PRORACUN_EUR, nastavljen))


def porabljeno(d=None):
    """Vsota rezervacij vseh botovih nakupov (konzervativno: tudi še nenapolnjenih)."""
    d = d or preberi_dnevnik()
    return (sum(n["rezervirano_eur"] for n in d["nakupi"])
            + sum(n["znesek_eur"] for n in d.get("rocni", [])))


def na_voljo(d=None):
    return proracun() - porabljeno(d)


# --------------------------------------------------------------------------
# Podatki z API
# --------------------------------------------------------------------------

_instrumenti = None


def instrument(ticker):
    """Metapodatki instrumenta (valuta, ISIN ...) ali None."""
    global _instrumenti
    if _instrumenti is None:
        _instrumenti = {i.get("ticker"): i for i in (t._get("/equity/metadata/instruments") or [])}
    return _instrumenti.get(ticker)


def najdi(oznaka):
    """Instrumenti, katerih ticker, ISIN ali ime vsebuje oznako."""
    instrument("")  # naloži seznam
    o = oznaka.upper()
    return [i for i in _instrumenti.values()
            if o in (i.get("ticker") or "").upper() or o == (i.get("isin") or "").upper()
            or o in (i.get("name") or "").upper()]


def je_isin(oznaka):
    return len(oznaka) == 12 and oznaka[:2].isalpha() and oznaka[2:].isalnum()


def eur_ticker(oznaka):
    """Vrne ticker kotacije v EUR za ISIN ali ticker (npr. namesto SMH v USD na LSE
    poišče isti ETF na borzi v EUR). Če EUR kotacije ni, sproži napako."""
    instrument("")  # naloži seznam
    if je_isin(oznaka.upper()):
        isin = oznaka.upper()
    else:
        instr = instrument(oznaka)
        if not instr:
            raise T212Napaka(f"ticker {oznaka} ne obstaja. Uporabi ISIN ali: python t212_trgovanje.py najdi <ISIN>")
        if (instr.get("currencyCode") or instr.get("currency")) == "EUR":
            return oznaka
        isin = (instr.get("isin") or "").upper()
    kandidati = sorted(
        (i for i in _instrumenti.values()
         if (i.get("isin") or "").upper() == isin and (i.get("currencyCode") or i.get("currency")) == "EUR"),
        key=lambda i: i.get("ticker") or "",
    )
    if not kandidati:
        raise T212Napaka(f"za {oznaka} ({isin}) na Trading 212 ni kotacije v EUR, zato ga bot ne kupi.")
    return kandidati[0]["ticker"]


def obvesti(zadeva, besedilo):
    """Pošlje e-pošto prek Gmaila (GMAIL_USER, GMAIL_APP_PASSWORD v .env). Napaka ne ustavi bota."""
    uporabnik = os.environ.get("GMAIL_USER", "").strip()
    geslo = os.environ.get("GMAIL_APP_PASSWORD", "").strip().replace(" ", "")
    prejemnik = os.environ.get("GMAIL_TO", "").strip() or uporabnik
    if not uporabnik or not geslo:
        print("(Obvestilo ni poslano: v .env manjka GMAIL_USER ali GMAIL_APP_PASSWORD.)", file=sys.stderr)
        return False
    try:
        import smtplib
        from email.message import EmailMessage
        sporocilo = EmailMessage()
        sporocilo["Subject"] = "[T212 bot] " + zadeva
        sporocilo["From"] = uporabnik
        sporocilo["To"] = prejemnik
        sporocilo.set_content(besedilo + "\n\n" + _zdaj() + f" | okolje: {os.environ.get('T212_OKOLJE', 'live')}")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(uporabnik, geslo)
            s.send_message(sporocilo)
        return True
    except Exception as e:
        print(f"(Obvestilo ni poslano: {e})", file=sys.stderr)
        return False


def _podatki_narocila(n):
    """Zgodovina vrača naročilo plosko ali pod ključem 'order'."""
    return n.get("order", n) if isinstance(n, dict) else {}


def napolnjena_kolicina(id_narocila, ticker):
    """Koliko je bilo pri naročilu dejansko napolnjeno. Če ni znano, 0 (varno za prodajo)."""
    try:
        aktivno = t._get(f"/equity/orders/{id_narocila}")
        if aktivno:
            return abs(float(aktivno.get("filledQuantity") or 0))
    except T212Napaka:
        pass  # ni več aktivno, poišči v zgodovini
    pot = f"/equity/history/orders?ticker={ticker}&limit=50"
    for _ in range(20):  # največ 20 strani
        stran = t._get(pot) or {}
        for el in stran.get("items", []):
            n = _podatki_narocila(el)
            if str(n.get("id")) == str(id_narocila):
                return abs(float(n.get("filledQuantity") or 0))
        pot = stran.get("nextPagePath")
        if not pot:
            break
        if pot.startswith("/api/v0"):
            pot = pot[len("/api/v0"):]
    return 0.0


def kolicina_v_poziciji(ticker):
    for p in t.pridobi_pozicije():
        if (p.get("instrument") or {}).get("ticker") == ticker or p.get("ticker") == ticker:
            return float(p.get("quantity") or 0)
    return 0.0


def botova_kolicina(ticker, d=None):
    """Koliko delnic tickerja sme bot prodati."""
    d = d or preberi_dnevnik()
    kupljeno = 0.0
    for n in d["nakupi"]:
        if n["ticker"] == ticker and n.get("id"):
            kupljeno += napolnjena_kolicina(n["id"], ticker)
    prodano = sum(p["kolicina"] for p in d["prodaje"] if p["ticker"] == ticker)
    return max(0.0, min(kupljeno - prodano, kolicina_v_poziciji(ticker)))


# --------------------------------------------------------------------------
# Naročila
# --------------------------------------------------------------------------

def kupi(ticker, kolicina, limitna_cena, gtc=False, potrdi=False):
    """Limitni nakup. Zavrne, če bi presegel proračun ali instrument ni v EUR."""
    kolicina, limitna_cena = float(kolicina), float(limitna_cena)
    if kolicina <= 0 or limitna_cena <= 0:
        raise T212Napaka("količina in limitna cena morata biti pozitivni.")
    zahtevano = ticker
    ticker = eur_ticker(ticker)  # vedno kupi kotacijo v EUR, če obstaja
    instr = instrument(ticker)
    valuta = instr.get("currencyCode") or instr.get("currency")
    if valuta != "EUR":
        raise T212Napaka(f"{ticker} kotira v {valuta}, bot kupuje samo instrumente v EUR.")

    strosek = round(kolicina * limitna_cena, 2)
    d = preberi_dnevnik()
    ostane = na_voljo(d)
    if strosek > ostane + EPS:
        raise T212Napaka(f"nakup bi stal do {strosek:.2f} EUR, v proračunu je še {ostane:.2f} EUR "
                         f"(skupaj {proracun():.2f}, porabljeno {porabljeno(d):.2f}).")
    opis = f"NAKUP {kolicina} x {ticker} po največ {limitna_cena} EUR = do {strosek:.2f} EUR"
    if zahtevano != ticker:
        opis += f" (namesto {zahtevano} kupim EUR kotacijo)"
    if not potrdi:
        return f"(suho) {opis}. Proračun po nakupu: {ostane - strosek:.2f} EUR. Za oddajo dodaj --potrdi."

    # Najprej rezerviraj v dnevniku, šele nato oddaj (če se program sesuje, je proračun že zmanjšan).
    zapis = {"id": None, "ticker": ticker, "kolicina": kolicina, "limit": limitna_cena,
             "rezervirano_eur": strosek, "cas": _zdaj()}
    d["nakupi"].append(zapis)
    shrani_dnevnik(d)
    try:
        odgovor = t._klic("/equity/orders/limit", "POST", {
            "ticker": ticker, "quantity": kolicina, "limitPrice": limitna_cena,
            "timeValidity": "GOOD_TILL_CANCEL" if gtc else "DAY",
        }) or {}
    except T212Napaka:
        d["nakupi"].remove(zapis)  # naročilo ni bilo sprejeto, sprosti rezervacijo
        shrani_dnevnik(d)
        raise
    zapis["id"] = odgovor.get("id")
    shrani_dnevnik(d)
    rezultat = f"ODDANO: {opis}. ID {zapis['id']}. Proračun še: {na_voljo(d):.2f} EUR."
    obvesti(f"Nakup {ticker}", rezultat)
    return rezultat


def prodaj(ticker, kolicina, potrdi=False):
    """Tržna prodaja, samo do količine, ki jo je kupil bot."""
    kolicina = float(kolicina)
    if kolicina <= 0:
        raise T212Napaka("količina mora biti pozitivna.")
    d = preberi_dnevnik()
    dovoljeno = botova_kolicina(ticker, d)
    if kolicina > dovoljeno + EPS:
        raise T212Napaka(f"bot sme prodati največ {dovoljeno} x {ticker} (samo svoje napolnjene nakupe).")
    opis = f"PRODAJA {kolicina} x {ticker} po tržni ceni"
    if not potrdi:
        return f"(suho) {opis}. Bot ima {dovoljeno} kos. Za oddajo dodaj --potrdi."
    zapis = {"id": None, "ticker": ticker, "kolicina": kolicina, "cas": _zdaj()}
    d["prodaje"].append(zapis)
    shrani_dnevnik(d)
    try:
        odgovor = t._klic("/equity/orders/market", "POST", {"ticker": ticker, "quantity": -kolicina}) or {}
    except T212Napaka:
        d["prodaje"].remove(zapis)
        shrani_dnevnik(d)
        raise
    zapis["id"] = odgovor.get("id")
    shrani_dnevnik(d)
    rezultat = f"ODDANO: {opis}. ID {zapis['id']}."
    obvesti(f"Prodaja {ticker}", rezultat)
    return rezultat


def preklici(id_narocila, potrdi=False):
    """Prekliče botov nakup in sprosti nenapolnjeni del rezervacije."""
    d = preberi_dnevnik()
    zapis = next((n for n in d["nakupi"] if str(n.get("id")) == str(id_narocila)), None)
    if not zapis:
        raise T212Napaka("to naročilo ni botov nakup, zato ga bot ne prekliče.")
    if not potrdi:
        return f"(suho) PREKLIC naročila {id_narocila}. Za oddajo dodaj --potrdi."
    try:
        t._klic(f"/equity/orders/{id_narocila}", "DELETE")
    except T212Napaka:
        pass  # morda je že poteklo ali napolnjeno; spodaj preverimo, da ni več aktivno
    try:
        t._get(f"/equity/orders/{id_narocila}")
        raise T212Napaka("naročilo je še aktivno, rezervacija ostane. Poskusi znova čez nekaj sekund.")
    except T212Napaka as e:
        if "še aktivno" in str(e):
            raise
    napolnjeno = napolnjena_kolicina(id_narocila, zapis["ticker"])
    zapis["rezervirano_eur"] = round(napolnjeno * zapis["limit"], 2)
    zapis["preklican"] = _zdaj()
    shrani_dnevnik(d)
    rezultat = f"PREKLICANO {id_narocila}. Napolnjeno {napolnjeno}, proračun še: {na_voljo(d):.2f} EUR."
    obvesti(f"Preklic {zapis['ticker']}", rezultat)
    return rezultat


def rocno(oznaka, kolicina, cena):
    """Zapiše nakup, opravljen ročno v aplikaciji, da šteje v proračun 500 EUR. Nič ne odda."""
    kolicina, cena = float(kolicina), float(cena)
    if kolicina <= 0 or cena <= 0:
        raise T212Napaka("količina in cena morata biti pozitivni.")
    d = preberi_dnevnik()
    zapis = {"oznaka": oznaka, "kolicina": kolicina, "cena": cena,
             "znesek_eur": round(kolicina * cena, 2), "datum": _zdaj()[:10]}
    d["rocni"].append(zapis)
    shrani_dnevnik(d)
    return f"Zapisan ročni nakup {kolicina} x {oznaka} = {zapis['znesek_eur']:.2f} EUR. Proračun še: {na_voljo(d):.2f} EUR."


def stanje():
    d = preberi_dnevnik()
    vrstice = [f"Proračun: {proracun():.2f} EUR | porabljeno: {porabljeno(d):.2f} | na voljo: {na_voljo(d):.2f}"]
    for ticker in sorted({n["ticker"] for n in d["nakupi"]}):
        vrstice.append(f"- {ticker}: bot sme prodati {botova_kolicina(ticker, d)} kos")
    for n in d.get("rocni", []):
        vrstice.append(f"- {n['oznaka']}: ročno {n['kolicina']} kos po {n['cena']} EUR = {n['znesek_eur']:.2f} EUR "
                       f"({n['datum']}, bot ga ne prodaja)")
    if len(vrstice) == 1:
        vrstice.append("Bot še ni nič kupil.")
    return "\n".join(vrstice)


# --------------------------------------------------------------------------
# Ukazna vrstica
# --------------------------------------------------------------------------

def main(argumenti):
    t.nalozi_env()
    potrdi = "--potrdi" in argumenti
    gtc = "--gtc" in argumenti
    a = [x for x in argumenti if not x.startswith("--")]
    ukaz = a[0].lower() if a else ""
    if ukaz == "stanje":
        print(stanje())
    elif ukaz == "rocno" and len(a) == 4:
        print(rocno(a[1], a[2], a[3]))
    elif ukaz == "najdi" and len(a) == 2:
        for i in najdi(a[1])[:20]:
            print(f"{i.get('ticker')} | {i.get('isin')} | {i.get('currencyCode')} | {i.get('name')}")
    elif ukaz == "kupi" and len(a) == 4:
        print(kupi(a[1], a[2], a[3], gtc=gtc, potrdi=potrdi))
    elif ukaz == "prodaj" and len(a) == 3:
        print(prodaj(a[1], a[2], potrdi=potrdi))
    elif ukaz == "preklici" and len(a) == 2:
        print(preklici(a[1], potrdi=potrdi))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except T212Napaka as e:
        print("NAPAKA: " + str(e), file=sys.stderr)
        sys.exit(1)
