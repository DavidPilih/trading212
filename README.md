# t212-portfolio

Preprosta Python skripta za **branje** stanja Trading 212 računa: skupna vrednost, gotovina in pozicije. Pošilja samo GET zahteve na uradni [Trading 212 API](https://docs.trading212.com/api), v kodi ni ničesar, kar bi oddalo ali preklicalo naročilo. Potrebuje samo standardno knjižnico Pythona 3.

## Nastavitev

1. V Trading 212 (Settings → API) ustvari ključ z dovoljenji **samo** *Account data* in *Portfolio* (brez "Orders").
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

## Pogoste napake

| Sporočilo | Kaj narediti |
|---|---|
| `API_KEY ni nastavljen` | Vpiši ključ v `.env`. |
| `HTTP 401` | Napačen ključ/skrivnost ali napačno okolje (live/demo). |
| `HTTP 403` | Ključ nima dovoljenja *Account data* ali *Portfolio*. |
| `HTTP 429` | Prehitri zagoni, počakaj 10 sekund. |
