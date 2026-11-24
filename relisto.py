"""Relisto: a local archive of your Vinted listings (photos, texts, price and
details), ready to reuse when you put an item up for sale again.

Created by lilsusanoo - https://dondo.info
Independent project, not affiliated with Vinted.
"""
import os
import json
import webbrowser
import re
import sys
import html
import shutil
import ctypes
import locale
import platform
import subprocess
import threading
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageOps, ImageTk
import customtkinter as ctk

# Optional: system trash (pip install send2trash)
try:
    from send2trash import send2trash
except Exception:
    send2trash = None

# --- MAC AND WINDOWS PATHS (working folder) ---
if getattr(sys, 'frozen', False):
    percorso_eseguibile = os.path.dirname(sys.executable)
    if sys.platform == "darwin" and ".app" in percorso_eseguibile:
        base_dir = os.path.abspath(os.path.join(percorso_eseguibile, "../../.."))
    else:
        base_dir = percorso_eseguibile
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

os.chdir(base_dir)

LISTINGS_DIR = os.path.join(base_dir, "Listings")

# Older versions used an Italian folder name: rename it once
_OLD_LISTINGS_DIR = os.path.join(base_dir, "Annunci")
if os.path.isdir(_OLD_LISTINGS_DIR) and not os.path.exists(LISTINGS_DIR):
    try:
        os.rename(_OLD_LISTINGS_DIR, LISTINGS_DIR)
    except Exception:
        pass
os.makedirs(LISTINGS_DIR, exist_ok=True)

# Move listings created by very old versions into the listings folder
for _name in os.listdir(base_dir):
    _src = os.path.join(base_dir, _name)
    if _name.startswith("Output_") and os.path.isdir(_src):
        _dst = os.path.join(LISTINGS_DIR, _name)
        if not os.path.exists(_dst):
            try:
                shutil.move(_src, _dst)
            except Exception:
                pass

# --- WINDOWS TASKBAR ---
if platform.system() == "Windows":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('relisto.app.1')
    except Exception:
        pass

# --- CORE SETTINGS ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

MIN_IMAGE_SIZE = 300     # skip avatars and icons
MAX_IMAGES = 10


def make_session():
    """HTTP session with automatic retries on temporary errors."""
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(HEADERS)
    return s


def normalize_vinted_url(raw):
    """Return a valid https Vinted URL, or None."""
    raw = raw.strip()
    if not raw:
        return None
    if not re.match(r'^https?://', raw, re.I):
        raw = "https://" + raw
    try:
        host = (urlparse(raw).hostname or "").lower()
    except Exception:
        return None
    if re.search(r'(^|\.)vinted\.[a-z.]+$', host):
        return raw
    return None


def extract_item_id(url):
    m = re.search(r'/items/(\d+)', url)
    return m.group(1) if m else None


def clean_filename(title):
    """Keep letters (accented too) and digits, drop the rest."""
    clean_t = title.replace("| Vinted", "").strip()
    safe_title = re.sub(r'[^\w\s-]', '', clean_t, flags=re.UNICODE)
    safe_title = safe_title.strip().replace(" ", "_")[:50].strip("_")
    return safe_title or "untitled"


def display_name_from_folder(folder_name):
    name = folder_name
    if name.startswith("Output_"):
        name = name[len("Output_"):]
    parts = name.split("_", 1)
    if len(parts) == 2 and parts[0].isdigit():
        name = parts[1]
    return name.replace("_", " ")


def list_photos(folder_path):
    # "photo_N.jpg" (current) or "foto_N.jpg" (older versions)
    files = [f for f in os.listdir(folder_path)
             if f.startswith(("photo_", "foto_")) and f.lower().endswith(".jpg")]
    files.sort(key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0)
    return files


def read_info(folder_path):
    """Read info.txt and return (title, description).

    Supports both the current English markers and the Italian ones
    written by older versions (TITOLO/DESCRIZIONE).
    """
    info_path = os.path.join(folder_path, "info.txt")
    if not os.path.exists(info_path):
        return "", ""
    with open(info_path, "r", encoding="utf-8") as f:
        content = f.read()

    for title_mark, desc_mark in (("TITLE:\n", "DESCRIPTION:\n"), ("TITOLO:\n", "DESCRIZIONE:\n")):
        if desc_mark in content:
            title_section, desc = content.split(desc_mark, 1)
            title = title_section.split(title_mark)[-1].strip() if title_mark in title_section else title_section.strip()
            return title, desc.strip()
    return content.replace("TITLE:\n", "").replace("TITOLO:\n", "").strip(), ""


def write_info(folder_path, title, desc):
    with open(os.path.join(folder_path, "info.txt"), "w", encoding="utf-8") as f:
        f.write(f"TITLE:\n{title}\n\nDESCRIPTION:\n{desc}")


class MetaParser(HTMLParser):
    """Read meta tags robustly (any attribute order or quoting)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.page_title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            d = {k.lower(): (v or "") for k, v in attrs}
            key = d.get("property") or d.get("name")
            if key and "content" in d and key not in self.meta:
                self.meta[key] = d["content"]
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.page_title += data


def parse_page_meta(page_html):
    parser = MetaParser()
    try:
        parser.feed(page_html)
    except Exception:
        pass
    title = parser.meta.get("og:title") or parser.page_title or "Item_Unknown"
    desc = parser.meta.get("og:description") or parser.meta.get("description") or ""
    # html.unescape just in case (e.g. double-encoded text)
    return html.unescape(title).replace("| Vinted", "").strip(), html.unescape(desc).strip()


def find_profile_photo_ids(page_html):
    """IDs of profile pictures (seller etc.).

    In the page data the item photos live in "photos":[...], while a
    user's avatar is a single "photo":{...} object.
    """
    text = page_html.replace('\\"', '"')
    return set(re.findall(
        r'"photo"\s*:\s*\{[^{}]*?"id"\s*:\s*"([A-Za-z0-9_-]+)"', text
    ))


DETAILS_FILE = "details.json"
OLD_DETAILS_FILE = "dettagli.json"   # written by older (Italian) versions
OLD_DETAIL_KEYS = {"prezzo": "price", "valuta": "currency", "marca": "brand",
                   "taglia": "size", "condizioni": "condition", "colore": "color"}
CURRENCY_SYMBOLS = {"EUR": "€", "GBP": "£", "USD": "$", "PLN": "zł", "CZK": "Kč",
                    "SEK": "kr", "DKK": "kr", "HUF": "Ft", "RON": "lei"}


def _json_str(value):
    """Decode JSON escapes, if any (e.g. \\u0026)."""
    try:
        return json.loads(f'"{value}"')
    except Exception:
        return value


def parse_item_details(page_html):
    """Price, brand, size, condition and colour from the page data."""
    text = page_html.replace('\\"', '"')
    details = {}

    m = re.search(r'"priceCurrency"\s*:\s*"([A-Z]{3})"\s*,\s*"price"\s*:\s*"?([\d.]+)', text)
    if m:
        details["currency"], details["price"] = m.group(1), m.group(2)
    else:
        m = re.search(r'"price"\s*:\s*\{\s*"amount"\s*:\s*"([\d.]+)"\s*,\s*"currency_code"\s*:\s*"([A-Z]{3})"', text)
        if m:
            details["price"], details["currency"] = m.group(1), m.group(2)

    fields = {"brand": "brand", "size": "size", "size_familiar": "size",
              "status": "condition", "color": "color"}
    for code, value in re.findall(
        r'"code"\s*:\s*"(brand|size|size_familiar|status|color)"\s*,\s*"data"\s*:\s*\{[^{}]*?"value"\s*:\s*"([^"]*)"',
        text
    ):
        key = fields[code]
        if value and key not in details:
            details[key] = _json_str(value).strip()

    if "brand" not in details:
        m = re.search(r'"brand"\s*:\s*\{\s*"@type"\s*:\s*"Brand"\s*,\s*"name"\s*:\s*"([^"]+)"', text)
        if m:
            details["brand"] = _json_str(m.group(1)).strip()
    return details


def format_price(details):
    amount = details.get("price")
    if not amount:
        return ""
    currency = details.get("currency", "EUR")
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    try:
        value = f"{float(amount):,.2f}"
    except ValueError:
        value = amount
    if currency in ("EUR", "GBP", "USD"):
        return f"{symbol}{value}"
    return f"{value} {symbol}"


def details_summary(details):
    """E.g. "Nike · L · Very good"."""
    return " · ".join(details[k] for k in ("brand", "size", "condition") if details.get(k))


def read_details(folder_path):
    """details.json, or the dettagli.json written by older versions."""
    for name in (DETAILS_FILE, OLD_DETAILS_FILE):
        try:
            with open(os.path.join(folder_path, name), "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if isinstance(data, dict):
            return {OLD_DETAIL_KEYS.get(k, k): v for k, v in data.items()}
    return {}


def write_details(folder_path, details):
    with open(os.path.join(folder_path, DETAILS_FILE), "w", encoding="utf-8") as f:
        json.dump(details, f, ensure_ascii=False, indent=2)


def make_card_image(path, size, radius, bg):
    """Photo cropped to fill, with rounded top corners."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        photo = ImageOps.fit(im.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1 + radius), radius=radius, fill=255
    )
    out = Image.new("RGB", size, bg)
    out.paste(photo, (0, 0), mask)
    return out


def validate_image(path):
    """Check the file is a valid, large enough image."""
    try:
        with Image.open(path) as img:
            img.load()
            w, h = img.size
        if w < MIN_IMAGE_SIZE or h < MIN_IMAGE_SIZE:
            return False, tr("too small (probably an avatar/icon)")
        return True, ""
    except Exception as e:
        return False, str(e)


# --- SCROLL ---
WHEEL_NOTCH_PX = 60       # pixels per mouse wheel notch
MAC_PX_PER_DELTA = 5.0    # pixels per delta unit on macOS

# --- COLOUR PALETTE (modern dark) ---
BG_MAIN = "#0c0c0f"
BG_SURF = "#141418"
BG_FIELD = "#1b1b21"
BORDER = "#2a2a32"
TEXT_MAIN = "#ececf1"
TEXT_MUTED = "#8e8e99"
ACCENT = "#8b5cf6"
ACCENT_HOVER = "#7c3aed"
ACCENT_SOFT = "#251b40"
LOG_BG = "#101014"
BTN_HOVER = "#23232b"
SELECTED_BG = ACCENT_SOFT
SELECTED_BORDER = ACCENT
DANGER = "#ef4444"
DANGER_HOVER = "#dc2626"
SUCCESS = "#22c55e"

# --- CATALOG ---
CARD_W = 164              # item card width
CARD_IMG_H = 218          # photo height (about 3:4 like on Vinted)
CARD_GAP = 16
CARD_BG = "#16161b"
CARD_RADIUS = 12

# --- LAYOUT ---
SIDEBAR_W = 272
TOPBAR_H = 58
GALLERY_H = 230
SETTINGS_PATH = os.path.join(base_dir, ".relisto_settings.json")


def resource_path(relative):
    """Path of a file shipped with the app (works inside the PyInstaller bundle too)."""
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, relative)

AUTHOR = "lilsusanoo"
AUTHOR_URL = "https://dondo.info"
AUTHOR_SITE_LABEL = "dondo.info"

# --- LANGUAGE ---------------------------------------------------------------
# English is the source language; IT holds the Italian translations.
LANGUAGES = {"en": "EN", "it": "IT"}
LANG = "en"

IT = {
    "Catalog": "Catalogo",
    "Extract": "Estrai",
    "Details": "Dettaglio",
    "+  New listing": "+  Nuovo annuncio",
    "Archive": "Archivio",
    "Made by {author}  ·  {site} ↗": "Creato da {author}  ·  {site} ↗",
    "Save a listing": "Estrai un annuncio",
    "Paste the link of one of your Vinted listings: photos, texts, price and details\n"
    "are kept here, ready for when you put the item up for sale again.":
        "Incolla il link di un tuo annuncio Vinted: foto, testi, prezzo e dettagli\n"
        "restano salvati qui, pronti quando vuoi rimettere in vendita l'articolo.",
    "Paste": "Incolla",
    "Ready.": "Pronto.",
    "Activity": "Attività",
    "Clear": "Pulisci",
    "←  Catalog": "←  Catalogo",
    "Delete": "Elimina",
    "Open folder": "Apri cartella",
    "Open on Vinted ↗": "Apri su Vinted ↗",
    "TITLE": "TITOLO",
    "Copy": "Copia",
    "Title copied": "Titolo copiato",
    "DESCRIPTION": "DESCRIZIONE",
    "Save changes": "Salva modifiche",
    "Description copied": "Descrizione copiata",
    "No item to show": "Nessun articolo da mostrare",
    "Copied to clipboard": "Copiato negli appunti",
    "No changes to save": "Nessuna modifica da salvare",
    "[+] Changes saved: {name}": "[+] Modifiche salvate: {name}",
    "Changes saved": "Modifiche salvate",
    "[-] Save error: {e}": "[-] Errore salvataggio: {e}",
    "Error": "Errore",
    "Could not save the changes:\n{e}": "Impossibile salvare le modifiche:\n{e}",
    "Move this listing to the trash?\n\n{name}": "Spostare nel cestino questo annuncio?\n\n{name}",
    "Permanently delete this listing?\n\n{name}":
        "Sei sicuro di voler eliminare definitivamente questo annuncio?\n\n{name}",
    "Confirm deletion": "Conferma eliminazione",
    "[!] Listing deleted: {name}": "[!] Annuncio eliminato: {name}",
    "Listing deleted": "Annuncio eliminato",
    "[-] Error while deleting: {e}": "[-] Errore durante l'eliminazione: {e}",
    "Could not delete the folder:\n{e}": "Impossibile eliminare la cartella:\n{e}",
    "[-] Could not open the preview: {e}": "[-] Impossibile aprire l'anteprima: {e}",
    "[-] Could not read info.txt: {e}": "[-] Errore lettura info.txt: {e}",
    "Price and details not available: extract the listing again to save them.":
        "Prezzo e dettagli non disponibili: estrai di nuovo l'annuncio per salvarli.",
    "Could not load the images: {e}": "Errore nel caricamento delle immagini: {e}",
    "Your saved listings: photos, texts and details ready for when you sell an item again.":
        "I tuoi annunci salvati: foto, testi e dettagli pronti quando rimetti in vendita un articolo.",
    "⌕  Search by title, brand, size…": "⌕  Cerca per titolo, marca, taglia…",
    "{n} photos": "{n} foto",
    "1 photo": "1 foto",
    "  {shown} of {total}  ": "  {shown} di {total}  ",
    "  {n} items  ": "  {n} articoli  ",
    "  1 item  ": "  1 articolo  ",
    "No item matches your search.": "Nessun articolo corrisponde alla ricerca.",
    "No saved listings yet.\n\n"
    "1.  Press \"+ New listing\" and paste the link of one of your Vinted listings\n"
    "2.  Relisto saves its photos, title, description, price and details\n"
    "3.  When you sell the item again, copy texts and photos from here":
        "Nessun annuncio salvato.\n\n"
        "1.  Premi \"+ Nuovo annuncio\" e incolla il link di un tuo annuncio Vinted\n"
        "2.  Relisto salva foto, titolo, descrizione, prezzo e dettagli\n"
        "3.  Quando rimetti in vendita l'articolo, copia testi e foto da qui",
    "No saved listings.": "Nessun annuncio salvato.",
    "[-] Error: please enter a URL.": "[-] Errore: inserisci un URL.",
    "[-] Error: this does not look like a Vinted link.": "[-] Errore: l'URL non sembra un link di Vinted.",
    "\n[*] Reading: {url}...": "\n[*] Lettura: {url}...",
    "Extracting…": "Estrazione…",
    "[+] Title: {title}": "[+] Titolo: {title}",
    "[-] No images found in the page.": "[-] Nessuna immagine trovata nella pagina.",
    "[+] Details: {info}": "[+] Dettagli: {info}",
    "[+] Found {n} images. Downloading...": "[+] Trovate {n} immagini. Download in corso...",
    "   [-] Image {i}: invalid response.": "   [-] Immagine {i}: risposta non valida.",
    "   [+] Image {i} saved.": "   [+] Immagine {i} salvata.",
    "   [-] Image {i} skipped: {err}": "   [-] Immagine {i} scartata: {err}",
    "   [-] Image {i} not downloaded: {e}": "   [-] Immagine {i} non scaricata: {e}",
    "\n[!!!] DONE: {saved}/{total} images saved. [!!!]":
        "\n[!!!] COMPLETATO: {saved}/{total} immagini salvate. [!!!]",
    "Listing saved · {n} photos": "Annuncio salvato · {n} foto",
    "[-] HTTP error: {code}": "[-] Errore HTTP: {code}",
    "[-] ERROR: {e}": "[-] ERRORE: {e}",
    "too small (probably an avatar/icon)": "troppo piccola (probabile avatar/icona)",
}


def tr(text, **kw):
    """Translate an English UI string into the current language."""
    if LANG == "it":
        text = IT.get(text, text)
    return text.format(**kw) if kw else text


def detect_language():
    """Italian if the system is set to Italian, English otherwise."""
    candidates = []
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["defaults", "read", "-g", "AppleLanguages"],
                                 capture_output=True, text=True, timeout=2).stdout
            m = re.search(r'"?([A-Za-z]{2})[-_]', out)
            if m:
                candidates.append(m.group(1))
        except Exception:
            pass
    candidates += [os.environ.get(k, "") for k in ("LC_ALL", "LC_MESSAGES", "LANG")]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except Exception:
        pass
    for c in candidates:
        if c:
            return "it" if c.lower().startswith("it") else "en"
    return "en"

UI_FONT = "Helvetica"
MONO_FONT = "Courier"

ctk.set_appearance_mode("Dark")


def pick_fonts(root):
    """Modern system fonts (SF Pro on Mac, Segoe UI on Windows)."""
    global UI_FONT, MONO_FONT
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    for name in ("SF Pro Text", "SF Pro", "SF Pro Display", "Helvetica Neue",
                 "Segoe UI Variable Text", "Segoe UI", "Inter", "Ubuntu", "Helvetica"):
        if name in families:
            UI_FONT = name
            break
    for name in ("SF Mono", "Menlo", "Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier"):
        if name in families:
            MONO_FONT = name
            break


def ui_font(size=13, weight="normal", **kw):
    return ctk.CTkFont(family=UI_FONT, size=size, weight=weight, **kw)


def mono_font(size=12):
    return ctk.CTkFont(family=MONO_FONT, size=size)


def load_settings():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def round_corners(img, radius, bg):
    """Rounded corners on a solid background (CTkLabel does not clip images)."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, img.size[0] - 1, img.size[1] - 1), radius=radius, fill=255
    )
    out = Image.new("RGB", img.size, bg)
    out.paste(img, (0, 0), mask)
    return out


class PageView:
    """Full-size pages with the same interface as CTkTabview (set/get/tab)."""

    def __init__(self, master, on_change=None):
        self.master = master
        self.pages = {}
        self.current = None
        self.on_change = on_change
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)

    def add(self, name):
        frame = ctk.CTkFrame(self.master, fg_color="transparent", corner_radius=0)
        self.pages[name] = frame
        return frame

    def tab(self, name):
        return self.pages[name]

    def get(self):
        return self.current

    def set(self, name):
        if name == self.current:
            return
        for n, frame in self.pages.items():
            if n != name:
                frame.grid_remove()
        self.pages[name].grid(row=0, column=0, sticky="nsew")
        self.current = name
        if self.on_change:
            self.on_change(name)


def ghost_button(master, text, command, width=0, height=32, **kw):
    opts = dict(
        text=text, command=command, height=height, fg_color=BG_FIELD,
        border_width=1, border_color=BORDER, text_color=TEXT_MAIN,
        hover_color=BTN_HOVER, corner_radius=10, font=ui_font(13),
    )
    if width:
        opts["width"] = width
    opts.update(kw)
    return ctk.CTkButton(master, **opts)


def primary_button(master, text, command, width=0, height=36, **kw):
    opts = dict(
        text=text, command=command, height=height, fg_color=ACCENT,
        text_color="#ffffff", hover_color=ACCENT_HOVER, corner_radius=10,
        font=ui_font(13, "bold"),
    )
    if width:
        opts["width"] = width
    opts.update(kw)
    return ctk.CTkButton(master, **opts)


NAV_LABELS = {"catalog": "Catalog", "extract": "Extract", "detail": "Details"}


class VintedApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        pick_fonts(self)

        self.title("Relisto")
        self.geometry("1280x820")
        self.configure(fg_color=BG_MAIN)
        self.minsize(980, 640)

        self.ui_logo = None
        self.small_logo = None
        try:
            icon_path = resource_path(os.path.join("assets", "logo.png"))
            if os.path.exists(icon_path):
                with Image.open(icon_path) as im:
                    pil_logo = im.copy()
                self.app_logo = ImageTk.PhotoImage(pil_logo)
                self.wm_iconphoto(True, self.app_logo)
                self.ui_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(72, 72))
                self.small_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(28, 28))
        except Exception as e:
            print(f"Could not load logo: {e}")

        self.settings = load_settings()
        global LANG
        LANG = self.settings.get("language") or detect_language()
        if LANG not in LANGUAGES:
            LANG = "en"
        self.current_folder_path = ""
        self._loaded_info = None          # (title, description) as read from disk
        self.thumbnail_cache = []
        self.folder_buttons = []
        self.folder_paths = []
        self.selected_folder_index = -1
        self._load_gen = 0                # to ignore thumbnails from stale reloads
        self._preview_win = None
        self.catalog_cards = []           # dict: path, card, img, title, search
        self.catalog_images = []
        self._catalog_cols = 0
        self._current_url = ""
        self._toast_job = None
        self._sidebar_anim = None
        self.sidebar_open = bool(self.settings.get("sidebar_open", True))

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_topbar()

        body = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        self.body = body

        self._build_sidebar(body)

        self.main_frame = ctk.CTkFrame(body, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        self.tabview = PageView(self.main_frame, on_change=self._on_page_change)
        self._build_catalog_tab(self.tabview.add("catalog"))
        self._build_extraction_page(self.tabview.add("extract"))
        self._build_detail_page(self.tabview.add("detail"))

        self.toast_label = ctk.CTkLabel(
            self, text="", font=ui_font(13, "bold"), fg_color=BG_FIELD,
            text_color=TEXT_MAIN, corner_radius=10, height=38
        )

        if not self.sidebar_open:
            self.sidebar_frame.grid_remove()
        self._update_sidebar_toggle()

        self.tabview.set("catalog")
        self._setup_scrolling()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.load_folders()

    # ------------------------------------------------------------------
    # Layout: top bar, sidebar, pages
    # ------------------------------------------------------------------
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, height=TOPBAR_H, fg_color=BG_SURF, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(3, weight=1)
        bar.grid_rowconfigure(0, weight=1)

        self.sidebar_toggle = ctk.CTkButton(
            bar, text="", width=36, height=34, fg_color="transparent",
            hover_color=BTN_HOVER, text_color=TEXT_MAIN, corner_radius=10,
            font=ui_font(16), command=self.toggle_sidebar
        )
        self.sidebar_toggle.grid(row=0, column=0, padx=(12, 6))

        brand = ctk.CTkFrame(bar, fg_color="transparent")
        brand.grid(row=0, column=1, padx=(4, 28))
        if self.small_logo:
            ctk.CTkLabel(brand, text="", image=self.small_logo).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(brand, text="Relisto", font=ui_font(16, "bold"),
                     text_color=TEXT_MAIN).pack(side="left")

        nav = ctk.CTkFrame(bar, fg_color=BG_MAIN, corner_radius=12)
        nav.grid(row=0, column=2)
        self.nav_buttons = {}
        for key, label in NAV_LABELS.items():
            b = ctk.CTkButton(
                nav, text=tr(label), width=96, height=32, corner_radius=9,
                font=ui_font(13, "bold"), fg_color="transparent",
                hover_color=BTN_HOVER, text_color=TEXT_MUTED,
                command=lambda k=key: self._nav_to(k)
            )
            b.pack(side="left", padx=3, pady=3)
            self.nav_buttons[key] = b

        self.lang_switch = ctk.CTkSegmentedButton(
            bar, values=list(LANGUAGES.values()), command=self._on_language_change,
            height=30, width=86, font=ui_font(12, "bold"), corner_radius=9,
            fg_color=BG_MAIN, selected_color=ACCENT_SOFT, selected_hover_color=ACCENT_SOFT,
            unselected_color=BG_MAIN, unselected_hover_color=BTN_HOVER,
            text_color=TEXT_MAIN
        )
        self.lang_switch.set(LANGUAGES[LANG])
        self.lang_switch.grid(row=0, column=4, padx=(0, 12))

        self.new_btn = primary_button(bar, tr("+  New listing"), self.go_to_extraction, height=34)
        self.new_btn.grid(row=0, column=5, padx=(0, 16))

        # separator line under the bar
        ctk.CTkFrame(self, height=1, fg_color=BORDER, corner_radius=0).grid(
            row=0, column=0, sticky="sew"
        )

    def _build_sidebar(self, body):
        self.sidebar_frame = ctk.CTkFrame(
            body, width=SIDEBAR_W, corner_radius=0, fg_color=BG_SURF
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsw")
        self.sidebar_frame.grid_propagate(False)
        self.sidebar_frame.grid_rowconfigure(1, weight=1)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # right border
        ctk.CTkFrame(self.sidebar_frame, width=1, fg_color=BORDER, corner_radius=0).place(
            relx=1.0, rely=0, relheight=1.0, anchor="ne"
        )

        head = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=(18, 12), pady=(18, 8))

        self.sidebar_title = ctk.CTkLabel(
            head, text=tr("Archive"), font=ui_font(15, "bold"), text_color=TEXT_MAIN
        )
        self.sidebar_title.pack(side="left")

        self.sidebar_count = ctk.CTkLabel(
            head, text="", font=ui_font(11, "bold"), text_color=TEXT_MUTED,
            fg_color=BG_FIELD, corner_radius=8, width=28, height=20
        )
        self.sidebar_count.pack(side="left", padx=(8, 0))

        self.refresh_btn = ctk.CTkButton(
            head, text="↻", width=30, height=30, fg_color="transparent",
            hover_color=BTN_HOVER, text_color=TEXT_MUTED, corner_radius=8,
            font=ui_font(16), command=self.load_folders
        )
        self.refresh_btn.pack(side="right")

        self.folder_container = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.folder_container.grid(row=1, column=0, padx=(8, 4), pady=(0, 10), sticky="nsew")

        self.folder_canvas = tk.Canvas(
            self.folder_container, bg=BG_SURF, highlightthickness=0, bd=0,
            yscrollincrement=1
        )
        self.folder_canvas.pack(side="left", fill="both", expand=True)

        self.folder_scrollbar = ctk.CTkScrollbar(
            self.folder_container, orientation="vertical", width=10,
            command=self.folder_canvas.yview, button_color=BORDER,
            button_hover_color=TEXT_MUTED
        )
        self.folder_scrollbar.pack(side="right", fill="y")
        self.folder_canvas.configure(yscrollcommand=self.folder_scrollbar.set)

        self.folder_list = ctk.CTkFrame(self.folder_canvas, fg_color=BG_SURF)
        self.folder_window = self.folder_canvas.create_window((0, 0), window=self.folder_list, anchor="nw")

        self.folder_list.bind("<Configure>", self._update_folder_scrollregion)
        self.folder_canvas.bind("<Configure>", self._resize_folder_list_width)

        # credits
        self.credits_label = ctk.CTkLabel(
            self.sidebar_frame, text=tr("Made by {author}  ·  {site} ↗", author=AUTHOR, site=AUTHOR_SITE_LABEL),
            font=ui_font(11), text_color=TEXT_MUTED, cursor="hand2"
        )
        self.credits_label.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 14))
        self.credits_label.bind("<Button-1>", lambda e: webbrowser.open(AUTHOR_URL))
        self.credits_label.bind("<Enter>", lambda e: self.credits_label.configure(text_color=ACCENT))
        self.credits_label.bind("<Leave>", lambda e: self.credits_label.configure(text_color=TEXT_MUTED))

    def _build_extraction_page(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(2, weight=1)
        page.grid_rowconfigure(1, weight=1)

        col = ctk.CTkFrame(page, fg_color="transparent", width=720)
        col.grid(row=0, column=1, rowspan=2, sticky="nsew", pady=(36, 24))
        col.grid_columnconfigure(0, weight=1, minsize=680)
        col.grid_rowconfigure(4, weight=1)

        hero = ctk.CTkFrame(col, fg_color="transparent")
        hero.grid(row=0, column=0, sticky="ew")
        if self.ui_logo:
            self.logo_label = ctk.CTkLabel(hero, text="", image=self.ui_logo)
            self.logo_label.pack(pady=(0, 10))
        self.title_label = ctk.CTkLabel(
            hero, text=tr("Save a listing"), font=ui_font(26, "bold"), text_color=TEXT_MAIN
        )
        self.title_label.pack()
        ctk.CTkLabel(
            hero, text=tr("Paste the link of one of your Vinted listings: photos, texts, price and details\n"
                          "are kept here, ready for when you put the item up for sale again."),
            font=ui_font(14), text_color=TEXT_MUTED, justify="center"
        ).pack(pady=(6, 22))

        card = ctk.CTkFrame(col, fg_color=BG_SURF, corner_radius=16, border_width=1, border_color=BORDER)
        card.grid(row=1, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            row, placeholder_text="https://www.vinted.it/items/…",
            height=44, font=ui_font(14), border_color=BORDER, border_width=1,
            fg_color=BG_FIELD, corner_radius=10, text_color=TEXT_MAIN
        )
        self.url_entry.grid(row=0, column=0, sticky="ew")

        self.paste_btn = ghost_button(row, tr("Paste"), self.paste_url, width=84, height=44)
        self.paste_btn.grid(row=0, column=1, padx=(8, 0))

        self.start_button = primary_button(
            row, tr("Extract"), self.start_processing, width=110, height=44,
            font=ui_font(14, "bold")
        )
        self.start_button.grid(row=0, column=2, padx=(8, 0))

        self.progress = ctk.CTkProgressBar(
            card, height=6, fg_color=BG_FIELD, progress_color=ACCENT, corner_radius=3
        )
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=16)

        self.status_label = ctk.CTkLabel(
            card, text=tr("Ready."), font=ui_font(12), text_color=TEXT_MUTED, anchor="w"
        )
        self.status_label.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 12))

        log_head = ctk.CTkFrame(col, fg_color="transparent")
        log_head.grid(row=3, column=0, sticky="ew", pady=(22, 6))
        self.console_label = ctk.CTkLabel(
            log_head, text=tr("Activity"), font=ui_font(14, "bold"), text_color=TEXT_MAIN
        )
        self.console_label.pack(side="left")
        ghost_button(log_head, tr("Clear"), self.clear_log, width=70, height=28,
                     font=ui_font(12)).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            col, height=200, state="disabled", font=mono_font(12), fg_color=LOG_BG,
            border_color=BORDER, border_width=1, corner_radius=14, text_color=TEXT_MAIN,
            wrap="word"
        )
        self.log_box.grid(row=4, column=0, sticky="nsew")

    def _build_detail_page(self, outer):
        # Scrollable page: canvas + inner frame
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)
        self.detail_container = ctk.CTkFrame(outer, fg_color="transparent")
        self.detail_container.grid(row=0, column=0, sticky="nsew")

        self.detail_canvas = tk.Canvas(
            self.detail_container, bg=BG_MAIN, highlightthickness=0, bd=0, yscrollincrement=1
        )
        self.detail_canvas.pack(side="left", fill="both", expand=True)
        self.detail_scrollbar = ctk.CTkScrollbar(
            self.detail_container, orientation="vertical", width=10,
            command=self.detail_canvas.yview, button_color=BORDER,
            button_hover_color=TEXT_MUTED
        )
        self.detail_scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=6)
        self.detail_canvas.configure(yscrollcommand=self.detail_scrollbar.set)

        page = ctk.CTkFrame(self.detail_canvas, fg_color=BG_MAIN, corner_radius=0)
        self.detail_inner = page
        self.detail_window = self.detail_canvas.create_window((0, 0), window=page, anchor="nw")
        self.detail_canvas.bind("<Configure>", self._update_detail_scroll)

        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(5, weight=1)
        pad = 28

        # --- action bar ---
        actions = ctk.CTkFrame(page, fg_color="transparent")
        actions.grid(row=0, column=0, sticky="ew", padx=pad, pady=(20, 14))

        ctk.CTkButton(
            actions, text=tr("←  Catalog"), width=110, height=32, fg_color="transparent",
            hover_color=BTN_HOVER, text_color=TEXT_MUTED, corner_radius=10,
            font=ui_font(13, "bold"), command=lambda: self.tabview.set("catalog")
        ).pack(side="left")

        self.btn_delete_folder = ghost_button(
            actions, tr("Delete"), self.delete_current_folder, width=86,
            text_color=DANGER, border_color="#4a2020", hover_color="#2a1515"
        )
        self.btn_delete_folder.pack(side="right")

        self.btn_open_folder = ghost_button(actions, tr("Open folder"), self.open_current_folder, width=110)
        self.btn_open_folder.pack(side="right", padx=(0, 8))

        self.btn_open_vinted = ghost_button(actions, tr("Open on Vinted ↗"), self.open_on_vinted, width=130)
        self._open_vinted_packed = False
        self._actions_frame = actions

        # --- photo gallery ---
        self.images_container = ctk.CTkFrame(
            page, fg_color=BG_SURF, border_color=BORDER, border_width=1, corner_radius=16
        )
        self.images_container.grid(row=1, column=0, sticky="ew", padx=pad)

        self.images_canvas = tk.Canvas(
            self.images_container, bg=BG_SURF, highlightthickness=0, bd=0,
            height=GALLERY_H, xscrollincrement=1
        )
        self.images_canvas.pack(side="top", fill="both", expand=True, padx=12, pady=(12, 4))

        self.images_scrollbar = ctk.CTkScrollbar(
            self.images_container, orientation="horizontal", height=10,
            button_color=BORDER, button_hover_color=TEXT_MUTED
        )
        self.images_scrollbar.pack(side="bottom", fill="x", padx=12, pady=(0, 8))

        self.images_scrollbar.configure(command=self.images_canvas.xview)
        self.images_canvas.configure(xscrollcommand=self.images_scrollbar.set)

        self.images_frame = ctk.CTkFrame(self.images_canvas, fg_color=BG_SURF)
        self.images_window = self.images_canvas.create_window((0, 0), window=self.images_frame, anchor="nw")
        self.images_frame.bind(
            "<Configure>",
            lambda e: self.images_canvas.configure(scrollregion=self.images_canvas.bbox("all"))
        )

        # --- title ---
        title_head = ctk.CTkFrame(page, fg_color="transparent")
        title_head.grid(row=2, column=0, sticky="ew", padx=pad, pady=(20, 6))
        self.lbl_view_title = ctk.CTkLabel(
            title_head, text=tr("TITLE"), font=ui_font(11, "bold"), text_color=TEXT_MUTED
        )
        self.lbl_view_title.pack(side="left")
        self.btn_copy_title = ghost_button(
            title_head, tr("Copy"), lambda: self.copy_to_clipboard(self.view_title.get(), tr("Title copied")),
            width=64, height=26, font=ui_font(12)
        )
        self.btn_copy_title.pack(side="right")

        self.view_title = ctk.CTkEntry(
            page, font=ui_font(18, "bold"), fg_color=BG_FIELD, height=46,
            border_color=BORDER, border_width=1, corner_radius=12, text_color=TEXT_MAIN
        )
        self.view_title.grid(row=3, column=0, sticky="ew", padx=pad)

        # --- price + details ---
        details_frame = ctk.CTkFrame(page, fg_color="transparent")
        details_frame.grid(row=4, column=0, sticky="ew", padx=pad, pady=(12, 0))
        self.view_price = ctk.CTkLabel(
            details_frame, text="", font=ui_font(22, "bold"), text_color=TEXT_MAIN
        )
        self.view_price.pack(side="left")
        # height=1: otherwise an empty CTkFrame takes 200x200 px
        self.view_chips = ctk.CTkFrame(details_frame, fg_color="transparent", width=1, height=1)
        self.view_details = ctk.CTkLabel(
            details_frame, text="", font=ui_font(13), text_color=TEXT_MUTED
        )

        # --- description ---
        desc_wrap = ctk.CTkFrame(page, fg_color="transparent")
        desc_wrap.grid(row=5, column=0, sticky="nsew", padx=pad, pady=(18, 24))
        desc_wrap.grid_columnconfigure(0, weight=1)
        desc_wrap.grid_rowconfigure(1, weight=1)

        desc_head = ctk.CTkFrame(desc_wrap, fg_color="transparent")
        desc_head.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.lbl_view_desc = ctk.CTkLabel(
            desc_head, text=tr("DESCRIPTION"), font=ui_font(11, "bold"), text_color=TEXT_MUTED
        )
        self.lbl_view_desc.pack(side="left")
        self.btn_save = primary_button(
            desc_head, tr("Save changes"), lambda: self.save_current_info(silent=False),
            width=130, height=28, font=ui_font(12, "bold")
        )
        self.btn_save.pack(side="right")
        self.btn_copy_desc = ghost_button(
            desc_head, tr("Copy"),
            lambda: self.copy_to_clipboard(self.view_desc.get("1.0", "end-1c"), tr("Description copied")),
            width=64, height=28, font=ui_font(12)
        )
        self.btn_copy_desc.pack(side="right", padx=(0, 8))

        self.view_desc = ctk.CTkTextbox(
            desc_wrap, height=220, font=ui_font(14), fg_color=BG_FIELD,
            border_color=BORDER, border_width=1, corner_radius=12, text_color=TEXT_MAIN,
            wrap="word"
        )
        self.view_desc.grid(row=1, column=0, sticky="nsew")

    def _update_detail_scroll(self, event=None):
        """Content fills the window when there is room, otherwise it scrolls."""
        cw = self.detail_canvas.winfo_width()
        ch = self.detail_canvas.winfo_height()
        if cw <= 1:
            return
        h = max(self.detail_inner.winfo_reqheight(), ch)
        self.detail_canvas.itemconfigure(self.detail_window, width=cw, height=h)
        self.detail_canvas.configure(scrollregion=(0, 0, cw, h))

    # ------------------------------------------------------------------
    # Navigation, sidebar, notifications
    # ------------------------------------------------------------------
    def _nav_to(self, key):
        if key == "detail" and not self.current_folder_path:
            if self.folder_paths:
                idx = self.selected_folder_index if self.selected_folder_index >= 0 else 0
                self.show_folder_details(self.folder_paths[idx])
            else:
                self.toast(tr("No item to show"))
            return
        self.tabview.set(key)

    def _on_page_change(self, name):
        for key, btn in self.nav_buttons.items():
            if key == name:
                btn.configure(fg_color=ACCENT_SOFT, text_color="#ffffff", hover_color=ACCENT_SOFT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_MUTED, hover_color=BTN_HOVER)

    def _on_language_change(self, value):
        lang = next((k for k, v in LANGUAGES.items() if v == value), "en")
        if lang == LANG:
            return
        self.settings["language"] = lang
        save_settings(self.settings)
        self.save_current_info(silent=True)
        self.after(80, self._restart)

    def _restart(self):
        """Relaunch the app so every text is rebuilt in the new language."""
        self.destroy()
        if getattr(sys, "frozen", False):
            os.execv(sys.executable, [sys.executable])
        else:
            script = os.path.abspath(__file__)
            os.execv(sys.executable, [sys.executable, script])

    def go_to_extraction(self):
        self.tabview.set("extract")
        self.after(50, self.url_entry.focus_set)

    def _update_sidebar_toggle(self):
        self.sidebar_toggle.configure(text="⟨" if self.sidebar_open else "☰")

    def toggle_sidebar(self, event=None):
        if self._sidebar_anim is not None:
            return "break"
        self.sidebar_open = not self.sidebar_open
        self.settings["sidebar_open"] = self.sidebar_open
        save_settings(self.settings)
        self._update_sidebar_toggle()

        # Instant open/close: in Tk every animation step redraws the whole
        # window (~100 ms), so an animation would stutter.
        if self.sidebar_open:
            self.sidebar_frame.grid()
        else:
            self.sidebar_frame.grid_remove()
        return "break"

    def toast(self, message, kind="info"):
        color = {"ok": SUCCESS, "error": DANGER}.get(kind, TEXT_MAIN)
        self.toast_label.configure(text=f"   {message}   ", text_color=color)
        self.toast_label.place(relx=0.5, rely=1.0, y=-24, anchor="s")
        self.toast_label.lift()
        if self._toast_job:
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(2200, self._hide_toast)

    def _hide_toast(self):
        self._toast_job = None
        self.toast_label.place_forget()

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _is_descendant(widget, ancestor):
        while widget is not None:
            if widget is ancestor:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _focus_in(self, *targets):
        try:
            focused = self.focus_get()
        except Exception:
            return False
        if focused is None or isinstance(focused, str):
            return False
        return any(self._is_descendant(focused, t) for t in targets)

    def _on_close(self):
        self.save_current_info(silent=True)
        self.destroy()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------
    def _bind_keys(self):
        self.bind_all("<Up>", self._select_previous_folder, add="+")
        self.bind_all("<Down>", self._select_next_folder, add="+")
        self.bind_all("<Return>", self.on_enter_pressed, add="+")
        self.bind_all("<KP_Enter>", self.on_enter_pressed, add="+")
        self.bind_all("<Control-s>", lambda e: self.save_current_info(silent=False), add="+")
        self.bind_all("<Command-s>", lambda e: self.save_current_info(silent=False), add="+")
        self.bind_all("<Command-b>", self.toggle_sidebar, add="+")
        self.bind_all("<Control-b>", self.toggle_sidebar, add="+")
        self.bind_all("<Command-n>", lambda e: self.go_to_extraction(), add="+")
        self.bind_all("<Control-n>", lambda e: self.go_to_extraction(), add="+")

    def on_enter_pressed(self, event=None):
        if self._focus_in(self.url_entry):
            self.start_processing()
            return "break"

        if self._focus_in(self.catalog_search):
            self._open_first_catalog_match()
            return "break"

        # In the detail fields Enter must work normally (new line)
        if self._focus_in(self.view_title, self.view_desc):
            return None

        if self.folder_buttons and 0 <= self.selected_folder_index < len(self.folder_buttons):
            self.folder_buttons[self.selected_folder_index].invoke()
            return "break"
        return None

    def _focus_is_in_text_input(self):
        return self._focus_in(self.url_entry, self.view_title, self.view_desc, self.catalog_search)

    def _select_previous_folder(self, event=None):
        if self._focus_is_in_text_input():
            return None
        if not self.folder_buttons:
            return "break"
        self._set_selected_folder(0 if self.selected_folder_index == -1 else self.selected_folder_index - 1)
        return "break"

    def _select_next_folder(self, event=None):
        if self._focus_is_in_text_input():
            return None
        if not self.folder_buttons:
            return "break"
        self._set_selected_folder(0 if self.selected_folder_index == -1 else self.selected_folder_index + 1)
        return "break"

    # ------------------------------------------------------------------
    # Unified scrolling (mouse, trackpad, wheel)
    # ------------------------------------------------------------------
    def _setup_scrolling(self):
        self._wheel_acc = {"x": 0.0, "y": 0.0}
        for seq in ("<MouseWheel>", "<Shift-MouseWheel>",
                    "<Button-4>", "<Button-5>", "<Button-6>", "<Button-7>"):
            self.bind_all(seq, self._on_wheel, add="+")
        # Tk 9 on macOS: two-finger trackpad scrolling arrives as
        # <TouchpadScroll> (pixel deltas, dx/dy packed into %D)
        try:
            self.bind_all("<TouchpadScroll>", self._on_touchpad_scroll, add="+")
        except tk.TclError:
            pass  # Tk 8.x: no such event, the trackpad uses <MouseWheel>

    def _find_scroll_targets(self, widget):
        """Scrollable areas under the pointer, innermost first."""
        targets = []
        while widget is not None:
            if widget is self.view_desc:
                try:
                    first, last = self.view_desc._textbox.yview()
                except Exception:
                    first, last = 0.0, 1.0
                if first > 0.0 or last < 1.0:
                    return None  # a long description scrolls by itself
            elif widget is self.folder_container:
                targets.append((self.folder_canvas, "y"))
            elif widget is self.images_container:
                targets.append((self.images_canvas, "x"))
            elif widget is self.catalog_container:
                targets.append((self.catalog_canvas, "y"))
            elif widget is self.detail_container:
                targets.append((self.detail_canvas, "y"))
            widget = getattr(widget, "master", None)
        return targets or None

    def _pick_scroll_target(self, targets, horizontal):
        want = "x" if horizontal else "y"
        for canvas, orient in targets:
            if orient == want and self._can_scroll(canvas, orient):
                return canvas, orient
        # vertical gesture over a horizontal strip with no page to scroll
        if not horizontal:
            for canvas, orient in targets:
                if orient == "x" and self._can_scroll(canvas, orient):
                    return canvas, orient
        return None

    def _wheel_delta_px(self, event):
        num = getattr(event, "num", None)
        if num in (4, 5, 6, 7):  # Linux
            return -WHEEL_NOTCH_PX if num in (4, 6) else WHEEL_NOTCH_PX

        delta = getattr(event, "delta", 0)
        if not delta:
            return 0.0
        if platform.system() == "Darwin" and tk.TkVersion < 9.0:
            return -delta * MAC_PX_PER_DELTA
        return -delta / 120.0 * WHEEL_NOTCH_PX

    def _on_wheel(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return None

        targets = self._find_scroll_targets(widget)
        if targets is None:
            return None

        is_horizontal = bool(event.state & 0x0001) or getattr(event, "num", None) in (6, 7)
        target = self._pick_scroll_target(targets, is_horizontal)
        if target is None:
            return "break"
        canvas, orient = target

        px = self._wheel_delta_px(event)
        if px == 0:
            return "break"

        acc = self._wheel_acc[orient] + px
        whole = int(acc)
        self._wheel_acc[orient] = acc - whole

        if whole:
            if orient == "y":
                canvas.yview_scroll(whole, "units")
            else:
                canvas.xview_scroll(whole, "units")
        return "break"

    def _on_touchpad_scroll(self, event):
        try:
            widget = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return None

        targets = self._find_scroll_targets(widget)
        if targets is None:
            return None

        dxdy = int(getattr(event, "delta", 0) or 0)
        dx = dxdy >> 16
        low = dxdy & 0xFFFF
        dy = low if low < 0x8000 else low - 0x10000

        horizontal = abs(dx) > abs(dy)
        target = self._pick_scroll_target(targets, horizontal)
        if target is None:
            return "break"
        canvas, orient = target
        px = -(dx if horizontal else dy)

        if px:
            if orient == "y":
                canvas.yview_scroll(px, "units")
            else:
                canvas.xview_scroll(px, "units")
        return "break"

    @staticmethod
    def _can_scroll(canvas, orient):
        try:
            first, last = canvas.yview() if orient == "y" else canvas.xview()
        except Exception:
            return True
        return not (first <= 0.0 and last >= 1.0)

    def _update_folder_scrollregion(self, event=None):
        self.folder_canvas.configure(scrollregion=self.folder_canvas.bbox("all"))

    def _resize_folder_list_width(self, event):
        if self._sidebar_anim is not None:
            return
        self.folder_canvas.itemconfigure(self.folder_window, width=event.width)

    # ------------------------------------------------------------------
    # List selection
    # ------------------------------------------------------------------
    def _set_selected_folder(self, index, open_item=False):
        if not self.folder_buttons:
            self.selected_folder_index = -1
            return

        index = max(0, min(index, len(self.folder_buttons) - 1))
        self.selected_folder_index = index

        for i, btn in enumerate(self.folder_buttons):
            if i == index:
                btn.configure(fg_color=SELECTED_BG, border_width=0, text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", border_width=0, text_color=TEXT_MAIN)

        selected_btn = self.folder_buttons[index]
        selected_btn.focus_set()
        self._scroll_selected_button_into_view(selected_btn)

        if open_item:
            selected_btn.invoke()

    def _scroll_selected_button_into_view(self, button):
        self.update_idletasks()
        try:
            btn_y = button.winfo_y()
            btn_h = button.winfo_height()
            content_h = max(self.folder_list.winfo_height(), 1)
            canvas_h = self.folder_canvas.winfo_height()
            top_visible = self.folder_canvas.canvasy(0)
            bottom_visible = top_visible + canvas_h

            if btn_y < top_visible:
                self.folder_canvas.yview_moveto(max(0, min(1, btn_y / content_h)))
            elif btn_y + btn_h > bottom_visible:
                self.folder_canvas.yview_moveto(max(0, min(1, (btn_y + btn_h - canvas_h) / content_h)))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Clipboard, folder, delete, save
    # ------------------------------------------------------------------
    def copy_to_clipboard(self, text, message=None):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.toast(message or tr("Copied to clipboard"), "ok")

    def paste_url(self):
        try:
            text = self.clipboard_get().strip()
        except Exception:
            return
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, text)
        self.url_entry.focus_set()

    def open_current_folder(self):
        if self.current_folder_path and os.path.exists(self.current_folder_path):
            folder_path = os.path.abspath(self.current_folder_path)
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.call(["open", folder_path])
            else:
                subprocess.call(["xdg-open", folder_path])

    def open_on_vinted(self):
        if self._current_url:
            webbrowser.open(self._current_url)

    def save_current_info(self, silent=True):
        """Save title and description to info.txt if they changed."""
        path = self.current_folder_path
        if not path or not os.path.isdir(path):
            return
        try:
            title = self.view_title.get().strip()
            desc = self.view_desc.get("1.0", "end-1c").strip()
        except Exception:
            return

        if self._loaded_info == (title, desc):
            if not silent:
                self.toast(tr("No changes to save"))
            return
        try:
            write_info(path, title, desc)
            self._loaded_info = (title, desc)
            self.log(tr("[+] Changes saved: {name}", name=os.path.basename(path)))
            if not silent:
                self.toast(tr("Changes saved"), "ok")
            self._refresh_card_title(path, title)
        except Exception as e:
            self.log(tr("[-] Save error: {e}", e=e))
            if not silent:
                messagebox.showerror(tr("Error"), tr("Could not save the changes:\n{e}", e=e))

    def delete_current_folder(self):
        if not self.current_folder_path or not os.path.exists(self.current_folder_path):
            return

        folder_name = os.path.basename(self.current_folder_path)
        if send2trash:
            msg = tr("Move this listing to the trash?\n\n{name}", name=folder_name)
        else:
            msg = tr("Permanently delete this listing?\n\n{name}", name=folder_name)

        if not messagebox.askyesno(tr("Confirm deletion"), msg):
            return

        try:
            # release image references before deleting
            for widget in self.images_frame.winfo_children():
                widget.destroy()
            self.update_idletasks()

            if send2trash:
                send2trash(os.path.abspath(self.current_folder_path))
            else:
                shutil.rmtree(self.current_folder_path)
            self.log(tr("[!] Listing deleted: {name}", name=folder_name))

            self.current_folder_path = ""
            self._loaded_info = None
            self.view_title.delete(0, "end")
            self.view_desc.delete("1.0", "end")

            self.load_folders()
            self.tabview.set("catalog")
            self.toast(tr("Listing deleted"), "ok")

        except Exception as e:
            self.log(tr("[-] Error while deleting: {e}", e=e))
            messagebox.showerror(tr("Error"), tr("Could not delete the folder:\n{e}", e=e))

    # ------------------------------------------------------------------
    # Enlarged preview
    # ------------------------------------------------------------------
    def open_preview(self, img_path):
        try:
            if self._preview_win is not None and self._preview_win.winfo_exists():
                self._preview_win.destroy()
        except Exception:
            pass

        try:
            with Image.open(img_path) as im:
                pil = im.convert("RGB")
        except Exception as e:
            self.log(tr("[-] Could not open the preview: {e}", e=e))
            return

        max_w = int(self.winfo_screenwidth() * 0.8)
        max_h = int(self.winfo_screenheight() * 0.8)
        scale = min(max_w / pil.width, max_h / pil.height, 1.0)
        size = (max(1, int(pil.width * scale)), max(1, int(pil.height * scale)))

        win = ctk.CTkToplevel(self)
        win.title(os.path.basename(img_path))
        win.configure(fg_color=BG_MAIN)
        win.resizable(False, False)
        self._preview_win = win

        ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
        lbl = ctk.CTkLabel(win, text="", image=ctk_img)
        lbl.image = ctk_img  # keep a reference (garbage collector)
        lbl.pack(padx=10, pady=10)

        for widget in (win, lbl):
            widget.bind("<Button-1>", lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())
        win.after(150, win.focus_force)

    # ------------------------------------------------------------------
    # Detail page
    # ------------------------------------------------------------------
    def show_folder_details(self, folder_path):
        # auto-save the listing you were editing
        if folder_path != self.current_folder_path:
            self.save_current_info(silent=True)

        self.current_folder_path = folder_path
        self.tabview.set("detail")

        self.view_title.delete(0, "end")
        self.view_desc.delete("1.0", "end")

        for widget in self.images_frame.winfo_children():
            widget.destroy()
        self.images_canvas.xview_moveto(0)

        try:
            title, desc = read_info(folder_path)
        except Exception as e:
            self.log(tr("[-] Could not read info.txt: {e}", e=e))
            title, desc = "", ""

        self.view_title.insert(0, title)
        self.view_desc.insert("1.0", desc)
        self._loaded_info = (title.strip(), desc.strip())

        details = read_details(folder_path)
        price = format_price(details)
        self.view_price.configure(text=price)
        for w in self.view_chips.winfo_children():
            w.destroy()
        for value in (details.get(k, "") for k in ("brand", "size", "condition", "color")):
            if value:
                ctk.CTkLabel(
                    self.view_chips, text=f"  {value}  ", font=ui_font(12, "bold"),
                    text_color=TEXT_MAIN, fg_color=BG_FIELD, corner_radius=8, height=26
                ).pack(side="left", padx=(0, 6))
        self.view_chips.pack_forget()
        self.view_details.pack_forget()
        if self.view_chips.winfo_children():
            self.view_chips.pack(side="left", padx=(14 if price else 0, 0))
        if not details:
            self.view_details.configure(
                text=tr("Price and details not available: extract the listing again to save them.")
            )
            self.view_details.pack(side="left")

        self._current_url = details.get("url", "")
        if self._current_url and not self._open_vinted_packed:
            self.btn_open_vinted.pack(side="right", padx=(0, 8))
            self._open_vinted_packed = True
        elif not self._current_url and self._open_vinted_packed:
            self.btn_open_vinted.pack_forget()
            self._open_vinted_packed = False

        photo_h = GALLERY_H
        try:
            for img_file in list_photos(folder_path):
                img_path = os.path.join(folder_path, img_file)

                # with + copy: the file is closed right away (no locks on Windows)
                with Image.open(img_path) as im:
                    im = ImageOps.exif_transpose(im)
                    w_size = max(1, int(im.width * photo_h / im.height))
                    pil_img = im.convert("RGB").resize((w_size * 2, photo_h * 2), Image.Resampling.LANCZOS)
                pil_img = round_corners(pil_img, 20, BG_SURF)

                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w_size, photo_h))

                img_label = ctk.CTkLabel(self.images_frame, image=ctk_img, text="", cursor="hand2")
                img_label.pack(side="left", padx=(0, 10))
                img_label.bind("<Button-1>", lambda e, p=img_path: self.open_preview(p))

        except Exception as e:
            self.log(tr("Could not load the images: {e}", e=e))

        self.update_idletasks()
        self.detail_canvas.yview_moveto(0)
        self._update_detail_scroll()

    def _refresh_card_title(self, path, title):
        for item in self.catalog_cards:
            if item["path"] == path and item.get("title_label") is not None:
                short = title if len(title) <= 48 else title[:46].rstrip() + "…"
                item["title_label"].configure(text=short)
                item["title"] = title
                break

    # ------------------------------------------------------------------
    # Catalog (Vinted-style card grid)
    # ------------------------------------------------------------------
    def _build_catalog_tab(self, tab):
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(22, 0))

        ctk.CTkLabel(
            tab, text=tr("Your saved listings: photos, texts and details ready for when you sell an item again."),
            font=ui_font(13), text_color=TEXT_MUTED, anchor="w"
        ).pack(fill="x", padx=29, pady=(2, 14))

        ctk.CTkLabel(
            header, text=tr("Catalog"), font=ui_font(26, "bold"), text_color=TEXT_MAIN
        ).pack(side="left")

        self.catalog_count = ctk.CTkLabel(
            header, text="", font=ui_font(12, "bold"), text_color=TEXT_MUTED,
            fg_color=BG_FIELD, corner_radius=9, height=24
        )
        self.catalog_count.pack(side="left", padx=(12, 0), pady=(6, 0))

        self.catalog_search = ctk.CTkEntry(
            header, placeholder_text=tr("⌕  Search by title, brand, size…"), width=300, height=38,
            font=ui_font(13), fg_color=BG_FIELD,
            border_color=BORDER, border_width=1, corner_radius=19, text_color=TEXT_MAIN
        )
        self.catalog_search.pack(side="right")
        self.catalog_search.bind("<KeyRelease>", lambda e: self._layout_catalog(force=True))

        self.catalog_container = ctk.CTkFrame(tab, fg_color="transparent")
        self.catalog_container.pack(fill="both", expand=True, padx=(18, 8), pady=(0, 12))

        self.catalog_canvas = tk.Canvas(
            self.catalog_container, bg=BG_MAIN, highlightthickness=0, bd=0,
            yscrollincrement=1
        )
        self.catalog_canvas.pack(side="left", fill="both", expand=True)

        self.catalog_scrollbar = ctk.CTkScrollbar(
            self.catalog_container, orientation="vertical", width=10,
            command=self.catalog_canvas.yview, button_color=BORDER,
            button_hover_color=TEXT_MUTED
        )
        self.catalog_scrollbar.pack(side="right", fill="y")
        self.catalog_canvas.configure(yscrollcommand=self.catalog_scrollbar.set)

        self.catalog_grid = ctk.CTkFrame(self.catalog_canvas, fg_color=BG_MAIN)
        self.catalog_window = self.catalog_canvas.create_window(
            (0, 0), window=self.catalog_grid, anchor="nw"
        )

        self.catalog_empty = ctk.CTkLabel(
            self.catalog_grid, text="", text_color=TEXT_MUTED, justify="left",
            font=ui_font(size=14)
        )

        self.catalog_grid.bind(
            "<Configure>",
            lambda e: self.catalog_canvas.configure(scrollregion=self.catalog_canvas.bbox("all"))
        )
        self.catalog_canvas.bind("<Configure>", self._on_catalog_resize)

    def _on_catalog_resize(self, event):
        # the grid stays still while the sidebar animates
        if self._sidebar_anim is not None:
            return
        self.catalog_canvas.itemconfigure(self.catalog_window, width=event.width)
        self._layout_catalog()

    def _clear_catalog(self):
        for item in self.catalog_cards:
            item["card"].destroy()
        self.catalog_cards = []
        self.catalog_images = []
        self._catalog_cols = 0

    def _build_catalog(self, paths):
        title_font = ui_font(size=13)
        meta_font = ui_font(size=12)
        price_font = ui_font(size=14, weight="bold")

        for path in paths:
            try:
                title, _ = read_info(path)
            except Exception:
                title = ""
            title = title or display_name_from_folder(os.path.basename(path))
            n_photos = len(list_photos(path))
            details = read_details(path)
            summary = details_summary(details)
            price = format_price(details)

            card = ctk.CTkFrame(
                self.catalog_grid, width=CARD_W, fg_color=CARD_BG,
                corner_radius=CARD_RADIUS, border_width=1, border_color=BORDER
            )

            img = ctk.CTkLabel(
                card, text="", width=CARD_W - 2, height=CARD_IMG_H,
                fg_color=BG_FIELD, corner_radius=CARD_RADIUS
            )
            img.pack(padx=1, pady=(1, 0))

            short = title if len(title) <= 48 else title[:46].rstrip() + "…"
            lbl_title = ctk.CTkLabel(
                card, text=short, font=title_font, text_color=TEXT_MAIN,
                wraplength=CARD_W - 24, justify="left", anchor="w", height=38
            )
            lbl_title.pack(fill="x", padx=12, pady=(8, 0))

            meta_text = summary or (tr("{n} photos", n=n_photos) if n_photos != 1 else tr("1 photo"))
            if len(meta_text) > 30:
                meta_text = meta_text[:28].rstrip() + "…"
            lbl_meta = ctk.CTkLabel(
                card, text=meta_text, font=meta_font,
                text_color=TEXT_MUTED, anchor="w", height=18
            )
            lbl_meta.pack(fill="x", padx=12, pady=(2, 0 if price else 10))
            widgets = [card, img, lbl_title, lbl_meta]

            if price:
                lbl_price = ctk.CTkLabel(
                    card, text=price, font=price_font,
                    text_color=TEXT_MAIN, anchor="w", height=22
                )
                lbl_price.pack(fill="x", padx=12, pady=(4, 10))
                widgets.append(lbl_price)

            search = " ".join([title, summary, details.get("color", "")]).lower()
            item = {"path": path, "card": card, "img": img,
                    "title": title, "search": search, "title_label": lbl_title}
            self.catalog_cards.append(item)

            for w in widgets:
                self._bind_card_events(w, item)

        self._layout_catalog(force=True)
        self.catalog_canvas.yview_moveto(0)

    def _bind_card_events(self, widget, item):
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda e, p=item["path"]: self.show_folder_details(p), add="+")
        widget.bind("<Enter>", lambda e: item["card"].configure(border_color=ACCENT), add="+")
        widget.bind("<Leave>", lambda e: self.after(15, self._card_leave_check, item), add="+")

    def _card_leave_check(self, item):
        card = item["card"]
        try:
            x, y = self.winfo_pointerxy()
            under = self.winfo_containing(x, y)
            if not self._is_descendant(under, card):
                card.configure(border_color=BORDER)
        except Exception:
            pass

    def _visible_catalog_cards(self):
        query = self.catalog_search.get().strip().lower()
        if not query:
            return self.catalog_cards
        words = query.split()
        return [c for c in self.catalog_cards if all(w in c["search"] for w in words)]

    def _layout_catalog(self, force=False):
        width = self.catalog_canvas.winfo_width()
        if width <= 1:
            return
        cols = max(1, (width - CARD_GAP) // (CARD_W + CARD_GAP))
        if cols == self._catalog_cols and not force:
            return
        self._catalog_cols = cols

        for item in self.catalog_cards:
            item["card"].grid_forget()
        self.catalog_empty.grid_forget()

        visible = self._visible_catalog_cards()
        total = len(self.catalog_cards)
        if total and len(visible) != total:
            self.catalog_count.configure(text=tr("  {shown} of {total}  ", shown=len(visible), total=total))
        else:
            self.catalog_count.configure(text=tr("  {n} items  ", n=total) if total != 1 else tr("  1 item  "))

        for c in range(max(cols, 1) + 1):
            self.catalog_grid.grid_columnconfigure(c, weight=0, minsize=0)
        # leftover space split on both sides: centred grid
        self.catalog_grid.grid_columnconfigure(0, weight=1)
        self.catalog_grid.grid_columnconfigure(cols + 1, weight=1)

        if not visible:
            self.catalog_empty.configure(
                text=tr("No item matches your search.") if total
                else tr("No saved listings yet.\n\n"
                        "1.  Press \"+ New listing\" and paste the link of one of your Vinted listings\n"
                        "2.  Relisto saves its photos, title, description, price and details\n"
                        "3.  When you sell the item again, copy texts and photos from here")
            )
            self.catalog_empty.grid(row=0, column=0, columnspan=cols + 2, pady=40)
        else:
            for i, item in enumerate(visible):
                r, c = divmod(i, cols)
                item["card"].grid(
                    row=r, column=c + 1, padx=CARD_GAP // 2, pady=CARD_GAP // 2, sticky="ns"
                )

        self.update_idletasks()
        self.catalog_canvas.configure(scrollregion=self.catalog_canvas.bbox("all"))

    def _open_first_catalog_match(self):
        visible = self._visible_catalog_cards()
        if visible:
            self.show_folder_details(visible[0]["path"])

    def _apply_card_image(self, gen, path, pil_img):
        if gen != self._load_gen:
            return
        for item in self.catalog_cards:
            if item["path"] == path:
                try:
                    ctk_img = ctk.CTkImage(
                        light_image=pil_img, dark_image=pil_img, size=(CARD_W - 2, CARD_IMG_H)
                    )
                    self.catalog_images.append(ctk_img)
                    item["img"].configure(image=ctk_img, fg_color="transparent")
                except Exception:
                    pass
                break

    # ------------------------------------------------------------------
    # Listing list (thumbnails loaded in the background)
    # ------------------------------------------------------------------
    def load_folders(self):
        self._load_gen += 1
        gen = self._load_gen

        for widget in self.folder_list.winfo_children():
            widget.destroy()

        self.thumbnail_cache.clear()
        self._clear_catalog()
        self.folder_buttons = []
        self.folder_paths = []
        self.selected_folder_index = -1

        try:
            names = [n for n in os.listdir(LISTINGS_DIR)
                     if os.path.isdir(os.path.join(LISTINGS_DIR, n)) and n.startswith("Output_")]
            paths = [os.path.join(LISTINGS_DIR, n) for n in names]
            paths.sort(key=lambda p: os.path.getctime(p), reverse=True)
        except Exception as e:
            print(f"Could not read folders: {e}")
            paths = []

        self._build_catalog(paths)
        self.sidebar_count.configure(text=f" {len(paths)} ")

        if not paths:
            ctk.CTkLabel(self.folder_list, text=tr("No saved listings."), text_color=TEXT_MUTED).pack(pady=20)
            self.update_idletasks()
            self._update_folder_scrollregion()
            return

        for idx, path in enumerate(paths):
            display_name = display_name_from_folder(os.path.basename(path))
            if len(display_name) > 24:
                display_name = display_name[:22].rstrip() + "…"

            btn = ctk.CTkButton(
                self.folder_list, text=f"  {display_name}", compound="left", anchor="w",
                fg_color="transparent", text_color=TEXT_MAIN, hover_color=BTN_HOVER,
                height=54, font=ui_font(13), corner_radius=10, border_spacing=6,
                command=lambda p=path: self.show_folder_details(p)
            )
            btn.pack(fill="x", pady=1, padx=(4, 6))
            self.folder_buttons.append(btn)
            self.folder_paths.append(path)

            btn.bind("<Button-1>", lambda e, i=idx: self._set_selected_folder(i), add="+")
            btn.bind("<FocusIn>", lambda e, i=idx: self._set_selected_folder(i), add="+")

        self.update_idletasks()
        self._update_folder_scrollregion()
        self._set_selected_folder(0)

        # Thumbnails arrive later, without blocking the window
        threading.Thread(target=self._thumb_worker, args=(gen, list(paths)), daemon=True).start()

    def _thumb_worker(self, gen, paths):
        for idx, folder in enumerate(paths):
            if gen != self._load_gen:
                return
            try:
                photos = list_photos(folder)
                if not photos:
                    continue
                first = os.path.join(folder, photos[0])
                with Image.open(first) as im:
                    im = ImageOps.exif_transpose(im)
                    thumb = ImageOps.fit(im.convert("RGB"), (100, 100), method=Image.Resampling.LANCZOS)
                # 2x for Retina screens
                card_img = make_card_image(first, (CARD_W * 2, CARD_IMG_H * 2), CARD_RADIUS * 2, CARD_BG)
                self.after(0, self._apply_thumb, gen, idx, thumb)
                self.after(0, self._apply_card_image, gen, folder, card_img)
            except Exception:
                continue

    def _apply_thumb(self, gen, idx, pil_img):
        if gen != self._load_gen or idx >= len(self.folder_buttons):
            return
        try:
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(42, 42))
            self.thumbnail_cache.append(ctk_img)
            self.folder_buttons[idx].configure(image=ctk_img)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Log and progress
    # ------------------------------------------------------------------
    def log(self, message):
        self.after(0, self._log_safe, message)

    def _log_safe(self, message):
        line = message.strip()
        if line and not message.startswith("   "):
            status = re.sub(r"^\[[^\]]*\]\s*", "", line).strip(" [!]")
            self.status_label.configure(
                text=status or line,
                text_color=DANGER if line.startswith("[-]") else TEXT_MUTED
            )
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_progress(self, value):
        self.after(0, lambda: self.progress.set(max(0.0, min(1.0, value))))

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def start_processing(self):
        raw = self.url_entry.get().strip()
        if not raw:
            self.log(tr("[-] Error: please enter a URL."))
            return

        url = normalize_vinted_url(raw)
        if not url:
            self.log(tr("[-] Error: this does not look like a Vinted link."))
            return

        self.log(tr("\n[*] Reading: {url}...", url=url[:60]))
        self.url_entry.delete(0, "end")

        self.start_button.configure(state="disabled", text=tr("Extracting…"))
        self.refresh_btn.configure(state="disabled")
        self.progress.set(0)

        threading.Thread(target=self.scrape_and_process, args=(url,), daemon=True).start()

    def scrape_and_process(self, url):
        try:
            session = make_session()
            response = session.get(url, timeout=20)
            response.raise_for_status()
            self.set_progress(0.1)

            title, description = parse_page_meta(response.text)
            self.log(tr("[+] Title: {title}", title=title))

            # --- find images ---
            raw_urls = re.findall(
                r'(https://images[0-9a-zA-Z-.]*\.vinted\.net/(?:t|s)/([a-zA-Z0-9_-]+)/[^"\'\s\\]+)',
                response.text
            )

            url_groups = {}
            invalid_keywords = ["avatar", "users", "member", "profile", "brand"]
            excluded_ids = find_profile_photo_ids(response.text)

            for full_url, photo_id in raw_urls:
                clean_url = full_url.replace('\\u002F', '/')
                if photo_id in excluded_ids:
                    continue
                if any(kw in clean_url.lower() for kw in invalid_keywords):
                    continue
                url_groups.setdefault(photo_id, []).append(clean_url)

            img_urls = []
            for photo_id, urls in url_groups.items():
                best_url = next((u for u in urls if '?' not in u), urls[0])
                img_urls.append(best_url)
            img_urls = img_urls[:MAX_IMAGES]

            if not img_urls:
                self.log(tr("[-] No images found in the page."))
                return

            # --- folder: item ID + title, so listings never overwrite each other ---
            item_id = extract_item_id(url)
            prefix = f"Output_{item_id}_" if item_id else "Output_"
            folder_path = os.path.join(LISTINGS_DIR, f"{prefix}{clean_filename(title)}")
            os.makedirs(folder_path, exist_ok=True)

            # if the listing already existed, start over with the photos
            for old in list_photos(folder_path):
                try:
                    os.remove(os.path.join(folder_path, old))
                except Exception:
                    pass

            write_info(folder_path, title, description)

            details = parse_item_details(response.text)
            details["url"] = url
            write_details(folder_path, details)
            info_line = " · ".join(x for x in (format_price(details), details_summary(details)) if x)
            if info_line:
                self.log(tr("[+] Details: {info}", info=info_line))

            self.log(tr("[+] Found {n} images. Downloading...", n=len(img_urls)))
            self.set_progress(0.2)

            img_headers = {"Referer": url}
            saved = 0

            for idx, img_url in enumerate(img_urls):
                img_path = os.path.join(folder_path, f"photo_{saved + 1}.jpg")
                try:
                    r = session.get(img_url, headers=img_headers, timeout=20)
                    r.raise_for_status()
                    if 'image' not in r.headers.get('Content-Type', '').lower():
                        self.log(tr("   [-] Image {i}: invalid response.", i=idx + 1))
                        continue

                    with open(img_path, 'wb') as handler:
                        handler.write(r.content)

                    ok, err = validate_image(img_path)
                    if ok:
                        saved += 1
                        self.log(tr("   [+] Image {i} saved.", i=idx + 1))
                    else:
                        self.log(tr("   [-] Image {i} skipped: {err}", i=idx + 1, err=err))
                        os.remove(img_path)

                except Exception as e:
                    self.log(tr("   [-] Image {i} not downloaded: {e}", i=idx + 1, e=e))
                    if os.path.exists(img_path):
                        try:
                            os.remove(img_path)
                        except Exception:
                            pass

                self.set_progress(0.2 + 0.8 * (idx + 1) / len(img_urls))

            self.log(tr("\n[!!!] DONE: {saved}/{total} images saved. [!!!]", saved=saved, total=len(img_urls)))
            self.after(0, lambda: self.toast(tr("Listing saved · {n} photos", n=saved), "ok"))
            self.after(0, self.load_folders)

        except requests.HTTPError as e:
            self.log(tr("[-] HTTP error: {code}", code=e.response.status_code if e.response is not None else e))
        except Exception as e:
            self.log(tr("[-] ERROR: {e}", e=e))
        finally:
            self.after(0, lambda: self.start_button.configure(state="normal", text=tr("Extract")))
            self.after(0, lambda: self.refresh_btn.configure(state="normal"))


if __name__ == "__main__":
    app = VintedApp()
    app.mainloop()