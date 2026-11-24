# Relisto

**A local archive of your Vinted listings: photos, texts and details always at hand,
so putting an item up for sale again doesn't mean starting from scratch.**

Made by [lilsusanoo](https://dondo.info).

<!-- Add a screenshot here: ![Catalog](docs/catalog.png) -->

## What it's for

On Vinted you often need to list the same item again: you took a listing down and want
to sell it again, you deleted it by mistake, or you want to offer it at a different
price. Every time you have to find the photos again, rewrite the title and description
and remember the price, size and condition.

Relisto keeps a copy of everything **on your computer**:

1. **Save**: paste the link of one of your listings and Relisto keeps its photos, title,
   description, price, brand, size, condition and colour.
2. **Find**: all saved listings live in a searchable grid catalog.
3. **Reuse**: when you sell an item again, you list it on Vinted yourself as usual,
   copying the title and description with one click and taking the photos from the folder.

Relisto **never publishes, edits or deletes anything on Vinted** and never uses your
account: it only reads the listing's public page, once, when you press "Extract".

> Relisto is an independent project and is **not affiliated with, endorsed or approved
> by Vinted**. It is meant for archiving **your own** listings. Please use it in line with
> [Vinted's Terms and Conditions](https://www.vinted.com/terms_and_conditions).

## Features

- **Extract from a link**: high-quality photos (without the seller's profile picture),
  title, description, price, brand, size, condition and colour.
- **Vinted-style grid catalog**, searchable by title, brand and size.
- **Detail page**: photo gallery (click to enlarge), editable title and description you
  can copy with one click, and a button to open the original listing.
- **Collapsible archive sidebar** (⌘B / Ctrl+B).
- **English and Italian**: picked automatically from your system language, switchable
  any time with the **EN | IT** toggle in the top bar.
- Modern dark interface, smooth scrolling with trackpad and mouse wheel.
- Everything stays on your computer, in the `Listings/` folder.

## Installation

You need Python 3.10 or newer with Tk (on macOS the [python.org](https://www.python.org/downloads/)
installer works, or `brew install python python-tk`).

```bash
git clone https://github.com/lilsusanoo/relisto.git
cd relisto
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python relisto.py
```

## How to use it

1. Press **+ New listing** (⌘N / Ctrl+N) and paste the link of one of your Vinted items.
2. Press **Extract**: the listing appears in the **Catalog**.
3. When you sell the item again, open it in the catalog: copy the title and description
   with **Copy**, get the photos with **Open folder**, then create the listing on Vinted
   as you normally would.

Each listing is a folder inside `Listings/` containing:

| File | Contents |
| --- | --- |
| `photo_1.jpg`, `photo_2.jpg`, … | the item's photos |
| `info.txt` | title and description |
| `details.json` | price, currency, brand, size, condition, colour, link |

### Shortcuts

| Keys | Action |
| --- | --- |
| ⌘N / Ctrl+N | New listing |
| ⌘B / Ctrl+B | Show/hide the archive |
| ⌘S / Ctrl+S | Save changes |
| ↑ / ↓, Enter | Move through the archive and open an item |

## Building the app (macOS / Windows)

```bash
pip install pyinstaller
pyinstaller --noconfirm relisto.spec
```

The app ends up in `dist/` (`Relisto.app` on macOS). Move it to the folder where you
want to keep your listings: the `Listings/` folder is created next to the app.

## Known limitations

- Relisto reads data from the listing's public page: if Vinted changes its website,
  extraction may stop working until the code is updated.
- Views and favourites are not available, because the public page doesn't show them.
- Text fields such as condition and colour are saved in the language of the Vinted site
  you copied the link from (e.g. "Very good" on vinted.co.uk, "Ottime" on vinted.it).

## License

[MIT](LICENSE) © 2026 [lilsusanoo](https://dondo.info)
