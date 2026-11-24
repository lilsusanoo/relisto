# Relisto

**L'archivio dei tuoi annunci Vinted: foto, testi e dettagli sempre a portata di mano,
così rimettere in vendita un articolo non significa rifare tutto da zero.**

Creato da [lilsusanoo](https://dondo.info).

<!-- Aggiungi qui uno screenshot: ![Catalogo](docs/catalogo.png) -->

## A cosa serve

Su Vinted capita spesso di dover pubblicare di nuovo lo stesso articolo: hai tolto un
annuncio e vuoi rimetterlo in vendita, l'hai cancellato per errore, o vuoi riproporlo
con un prezzo diverso. Ogni volta devi ritrovare le foto, riscrivere titolo e
descrizione e ricordarti prezzo, taglia e condizioni.

Relisto tiene una copia di tutto **sul tuo computer**:

1. **Salva**: incolli il link di un tuo annuncio e Relisto conserva foto, titolo,
   descrizione, prezzo, marca, taglia, condizioni e colore.
2. **Ritrova**: tutti gli annunci salvati sono in un catalogo a griglia, con ricerca.
3. **Riusa**: quando rimetti in vendita un articolo, lo pubblichi tu su Vinted come al
   solito, copiando titolo e descrizione con un clic e prendendo le foto dalla cartella.

Relisto **non pubblica, modifica o cancella nulla su Vinted** e non usa il tuo account:
legge solo la pagina pubblica dell'annuncio, una volta, quando premi "Estrai".

> Relisto è un progetto indipendente e **non è affiliato, associato o approvato da Vinted**.
> È pensato per archiviare **i propri** annunci. Usalo nel rispetto dei
> [Termini e condizioni di Vinted](https://www.vinted.it/terms_and_conditions).

## Funzionalità

- **Estrazione da link**: foto in alta qualità (senza la foto profilo del venditore),
  titolo, descrizione, prezzo, marca, taglia, condizioni e colore.
- **Catalogo a griglia** in stile Vinted, con ricerca per titolo, marca e taglia.
- **Pagina di dettaglio**: galleria foto (clic per ingrandire), titolo e descrizione
  modificabili e copiabili con un clic, pulsante per aprire l'annuncio originale.
- **Archivio laterale** richiudibile (⌘B / Ctrl+B).
- Interfaccia scura moderna, scorrimento fluido con trackpad e rotella.
- Tutto resta sul tuo computer, nella cartella `Annunci/`.

## Installazione

Serve Python 3.10 o più recente (con Tk; su macOS va bene il Python di
[python.org](https://www.python.org/downloads/) oppure `brew install python python-tk`).

```bash
git clone https://github.com/lilsusanoo/relisto.git
cd relisto
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python relisto.py
```

## Come si usa

1. Premi **+ Nuovo annuncio** (⌘N / Ctrl+N) e incolla il link di un tuo articolo Vinted.
2. Premi **Estrai**: l'annuncio compare nel **Catalogo**.
3. Quando rimetti in vendita l'articolo, aprilo nel catalogo: copia titolo e descrizione
   con **Copia** e prendi le foto con **Apri cartella**, poi crea l'annuncio su Vinted
   come fai di solito.

Ogni annuncio è una cartella in `Annunci/` con:

| File | Contenuto |
| --- | --- |
| `foto_1.jpg`, `foto_2.jpg`, … | le foto dell'articolo |
| `info.txt` | titolo e descrizione |
| `dettagli.json` | prezzo, valuta, marca, taglia, condizioni, colore, link |

### Scorciatoie

| Tasti | Azione |
| --- | --- |
| ⌘N / Ctrl+N | Nuovo annuncio |
| ⌘B / Ctrl+B | Mostra/nascondi l'archivio |
| ⌘S / Ctrl+S | Salva le modifiche |
| ↑ / ↓, Invio | Scorri l'archivio e apri l'articolo |

## Creare l'app (macOS / Windows)

```bash
pip install pyinstaller
pyinstaller --noconfirm relisto.spec
```

L'app si trova in `dist/` (`Relisto.app` su macOS). Spostala nella cartella dove vuoi
tenere gli annunci: la cartella `Annunci/` viene creata accanto all'app.

## Limiti noti

- Relisto legge i dati dalla pagina pubblica dell'annuncio: se Vinted cambia la struttura
  del sito, l'estrazione può smettere di funzionare finché il codice non viene aggiornato.
- Visualizzazioni e preferiti non sono disponibili, perché la pagina pubblica non li mostra.
- Gli annunci estratti con versioni vecchie non hanno prezzo e dettagli: basta estrarli di nuovo.

## Licenza

[MIT](LICENSE) © 2026 [lilsusanoo](https://dondo.info)
