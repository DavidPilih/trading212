# t212-portfolio

Python skripti za Trading 212 ([uradni API](https://docs.trading212.com/api)): `t212_portfolio.py` samo bere stanje (vrednost, gotovina, pozicije), `t212_trgovanje.py` kupuje in prodaja z varovalkami. Potrebuje samo standardno knjižnico Pythona 3.

## Nastavitev

1. V Trading 212 (Settings → API) ustvari ključ. Za samo branje zadostujeta *Account data* in *Portfolio*, za trgovanje še dovoljenje za naročila.
2. Odpri datoteko `.env` v tej mapi in vpiši ključ in skrivnost:
   ```
   API_KEY=tvoj_kljuc
   SECRET_KEY=tvoja_skrivnost
   ```
   Če `.env` ne obstaja, kopiraj `.env.example` v `.env`. Datoteka `.env` je v `.gitignore` in se nikoli ne commita.

## Uporaba

```
python t212_portfolio.py                 # celoten povzetek
python t212_portfolio.py vrednost        # skupna vrednost in D/I
python t212_portfolio.py gotovina        # gotovina
python t212_portfolio.py pozicije        # vse pozicije
python t212_portfolio.py pozicija EQQB   # ena pozicija (ticker ali ISIN)
python t212_portfolio.py --shrani        # povzetek doda še v stanje_t212.txt
```

Funkcije lahko uporabiš tudi iz drugega Python programa:

```python
import t212_portfolio as t
t.nalozi_env()
print(t.preveri_vrednost())
print(t.preveri_pozicijo("IE00BMC38736"))
```

## Trgovanje (t212_trgovanje.py)

Nakup in prodaja s trdimi varovalkami v kodi:

- Bot za nakupe **skupaj porabi največ 500 EUR** (`BOT_PRORACUN_EUR` ga lahko samo zniža). Prodaje proračuna ne vračajo.
- Nakup samo z **limitnim naročilom** za instrument v **EUR**; znesek (količina × limit) se rezervira, preden se naročilo odda.
- Prodaja samo **delnic, ki jih je kupil bot** (napolnjeni nakupi minus prejšnje prodaje, največ toliko, kot je v poziciji). Ročno kupljenih ali prej obstoječih delnic ne proda.
- Vedno kupi **kotacijo v EUR**: podaš lahko ISIN ali katerikoli ticker (npr. SMH na LSE v USD), bot poišče isti ETF v EUR. Če EUR kotacije ni, nakup zavrne.
- Ob vsakem oddanem nakupu, prodaji ali preklicu pošlje **e-pošto na Gmail** (`GMAIL_USER` in `GMAIL_APP_PASSWORD` v `.env`; geslo je Google App Password, ne tvoje navadno geslo).
- Brez `--potrdi` se nič ne odda, izpiše se le, kaj bi se zgodilo.
- Dnevnik je v `bot_dnevnik.json` (ni v gitu). **Ne briši ga.**

Ključ mora imeti dovoljenje za naročila. Najprej preizkusi z `T212_OKOLJE=demo`.

```
python t212_trgovanje.py najdi IE00BFZXGZ54           # poišči poln ticker
python t212_trgovanje.py stanje                       # proračun in botove pozicije
python t212_trgovanje.py kupi IE00BMC38736 0.5 30 --potrdi   # ISIN ali ticker
python t212_trgovanje.py prodaj EQQBd_EQ 0.5 --potrdi
python t212_trgovanje.py preklici <id> --potrdi
```

## Pogoste napake

| Sporočilo | Kaj narediti |
|---|---|
| `API_KEY ni nastavljen` | Vpiši ključ v `.env`. |
| `HTTP 401` | Napačen ključ/skrivnost ali napačno okolje (live/demo). |
| `HTTP 403` | Ključ nima dovoljenja *Account data* ali *Portfolio*. |
| `HTTP 429` | Prehitri zagoni, počakaj 10 sekund. |
