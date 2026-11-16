# trading212

Moj mali projekt za Trading 212. Imam 500 € in cilj je v enem letu premagati S&P 500.

Dve skripti:

- `t212_portfolio.py` samo prebere stanje računa (vrednost, gotovina, pozicije)
- `t212_trgovanje.py` kupuje in prodaja, ampak z omejitvami (spodaj)

Uporablja samo standardni Python 3, nič pip install.

## Nastavitev

V Trading 212 pod Settings > API naredi ključ. Za branje rabiš Account data in Portfolio, za trgovanje še Orders.

Potem kopiraj `.env.example` v `.env` in vpiši:

```
API_KEY=...
SECRET_KEY=...
```

`.env` je v .gitignore, tako da ne pride na GitHub.

## Branje stanja

```
python t212_portfolio.py                 # vse skupaj
python t212_portfolio.py vrednost
python t212_portfolio.py gotovina
python t212_portfolio.py pozicije
python t212_portfolio.py pozicija EQQB   # ticker ali ISIN
python t212_portfolio.py --shrani        # izpis shrani še v stanje_t212.txt
```

Lahko ga tudi importaš:

```python
import t212_portfolio as t
t.nalozi_env()
print(t.preveri_vrednost())
```

## Trgovanje

Pravila, ki so zapisana direktno v kodi:

- skupaj lahko za nakupe porabi največ 500 € (prodaje tega ne vrnejo)
- kupuje samo z limit naročili
- vedno vzame EUR kotacijo, npr. če daš SMH (LSE, USD), poišče isti ETF v EUR. Če ga ni v EUR, ne kupi
- prodaja samo to, kar je sam kupil, ročno kupljenih delnic se ne dotakne
- brez `--potrdi` samo izpiše, kaj bi naredil

Kaj je kupil, si zapisuje v `bot_dnevnik.json`. Tega ne briši, sicer pozabi, koliko je že porabil.

Najprej sem testiral z `T212_OKOLJE=demo`.

```
python t212_trgovanje.py najdi IE00BFZXGZ54
python t212_trgovanje.py stanje
python t212_trgovanje.py kupi IE00BMC38736 0.5 30 --potrdi
python t212_trgovanje.py prodaj EQQBd_EQ 0.5 --potrdi
python t212_trgovanje.py preklici <id> --potrdi
```

Če v `.env` izpolniš še `GMAIL_USER` in `GMAIL_APP_PASSWORD` (app password, ne pravo geslo), pošlje mail ob vsakem naročilu.

## Predlog naročila (s telefona)

Pregled pripravi `narocilo.json` (kaj kupiti, koliko kosov, limit, razlog). Potem samo:

```
run
```

Izpiše predlog, bot naredi suhi tek (proračun, EUR kotacija), nato vpraša `Izvedem? da/ne`.
Ob `da` odda limitno naročilo, ob `ne` nič. V obeh primerih se predlog premakne v
`narocila_arhiv/`, da se ne izvede dvakrat. Predlog po datumu `velja_do` poteče.
Če kosi x limit preseže `znesek_eur` iz predloga, ga ne izvede.

`run povzetek` pokaže stanje računa (prej je to delal sam `run`).

## Napake

- `API_KEY ni nastavljen`: manjka ključ v `.env`
- `HTTP 401`: napačen ključ ali pa live/demo ni pravi
- `HTTP 403`: ključ nima pravih dovoljenj
- `HTTP 429`: prehitro, počakaj par sekund
