#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Google News RSS Builder – PRO (FR / EN / DUAL) + scoring pondéré + export CSV

Fonctions:
- Query + recency + after/before + site:
- Sélecteur langue: FR | EN | FR+EN (dual feed)
- Fetch RSS -> merge + dédoublonnage + tri local par fraîcheur
- Scoring auto FR/EN (détection heuristique, optionnel langdetect)
- Lexiques pondérés + expressions (bigrams)
- Filtres POS/NEG (checkbox)
- Terminal minimal: [YYYY-MM-DD HH:MM] [POS/NEG/NEU score] [FR/EN] Source – Titre [i]
- [i] cliquable ouvre l’URL
- Barre statut: nb news + ambiance globale
- SAVE CSV: exporte les items (inclut URL brute)

Dépendances:
  pip install requests feedparser
Optionnel:
  pip install langdetect
"""

import re
import csv
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import webbrowser
import requests
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from hashlib import sha1

try:
    import feedparser  # pip install feedparser
except Exception:
    feedparser = None

# Optionnel
try:
    from langdetect import detect as _ld_detect  # pip install langdetect
except Exception:
    _ld_detect = None


# -----------------------------
# CONFIG
# -----------------------------
BASE_URL = "https://news.google.com/rss/search"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

RECENCY_CHOICES = ["1d", "7d", "1m", "3m", "6m", "1y"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD

# Editions (hl/gl/ceid) selon langue
EDITION_FR = {"hl": "fr", "gl": "FR", "ceid": "FR:fr"}
EDITION_EN = {"hl": "en", "gl": "US", "ceid": "US:en"}

LANG_CHOICES = ["FR", "EN", "FR+EN"]


# -----------------------------
# LEXIQUES SENTIMENT (pondérés) + expressions
# -----------------------------
POS_WORDS_FR_W = {
    "hausse": 3, "bond": 3, "bondit": 3, "rebond": 2, "rebondit": 2,
    "surperforme": 3, "surperformance": 3,
    "record": 2, "solide": 1, "fort": 1, "forte": 1,
    "croissance": 2, "augmente": 2,
    "dépasse": 3, "depasse": 3,
    "succès": 2, "succes": 2,
    "rassure": 2, "rassurant": 2,
    "améliore": 2, "ameliore": 2,
    "relance": 1, "reprise": 1,
    "upgrade": 3, "rehausse": 3, "réhausse": 3,
    "bullish": 2,
    "accord": 2,
    "gagne": 2, "gain": 2, "gagnant": 2,
}

NEG_WORDS_FR_W = {
    "baisse": 3, "chute": 4, "plonge": 4, "recul": 2,
    "effondrement": 5, "s'effondre": 5,
    "dégringole": 4, "degringole": 4,
    "alerte": 2, "inquiétude": 2, "inquietude": 2,
    "crise": 3, "faible": 2, "faibles": 2,
    "déçoit": 3, "decoit": 3,
    "warning": 4, "downgrade": 4,
    "abaisse": 3, "réduit": 3, "reduire": 3, "réduction": 2,
    "perte": 3, "pertes": 3,
    "licenciement": 3, "licenciements": 3,
    "enquête": 3, "enquete": 3,
    "procès": 3, "proces": 3,
    "fraude": 4, "amende": 3, "sanction": 3,
    "risque": 1, "risques": 1,
    "bearish": 2,
    "dégradation": 3, "degradation": 3,
    "tension": 2, "incertitude": 2,
}

# finance-intent: petit bonus (ne doit pas basculer le sentiment)
FIN_WORDS_FR_W = {
    "résultats": 1, "resultats": 1,
    "prévisions": 1, "previsions": 1,
    "guidance": 1, "outlook": 1,
    "marge": 1, "chiffre": 1,
    "bénéfice": 1, "benefice": 1,
    "trimestre": 1, "t1": 1, "t2": 1, "t3": 1, "t4": 1,
    "publication": 1,
    "dividende": 1, "rachat": 1
}

POS_WORDS_EN_W = {
    "rise": 2, "rises": 2, "rising": 1,
    "surge": 3, "surges": 3,
    "jump": 3, "jumps": 3,
    "soar": 4, "soars": 4,
    "rally": 3, "rallies": 3,
    "record": 2,
    "beats": 4, "beat": 4,
    "upgrade": 4, "outperform": 3, "bullish": 2,
    "gain": 2, "gains": 2,
    "wins": 2, "winning": 2,
    "breakthrough": 2,
    "raised": 3, "raises": 3, "raise": 2,
}

NEG_WORDS_EN_W = {
    "fall": 3, "falls": 3, "falling": 2,
    "drop": 3, "drops": 3,
    "plunge": 4, "plunges": 4,
    "slump": 3, "slumps": 3,
    "miss": 4, "misses": 4, "missed": 4,
    "weak": 2,
    "warning": 4, "downgrade": 4,
    "cut": 3, "cuts": 3, "slashed": 4, "lowered": 3, "lowers": 3,
    "lawsuit": 4, "probe": 3, "investigation": 3,
    "fraud": 4, "fine": 3, "penalty": 3,
    "risk": 1, "risks": 1,
    "bearish": 2,
    "uncertainty": 2,
    "concern": 2, "concerns": 2,
    "crisis": 3,
    "recall": 4, "breach": 4, "hack": 4,
}

FIN_WORDS_EN_W = {
    "earnings": 1, "results": 1, "guidance": 1, "forecast": 1, "outlook": 1,
    "margin": 1, "revenue": 1, "profit": 1,
    "quarter": 1, "q1": 1, "q2": 1, "q3": 1, "q4": 1,
    "dividend": 1, "buyback": 1,
    "shares": 1, "stock": 1,
    "sec": 1, "filing": 1,
}

PHRASES_FR_W = {
    "dépasse les attentes": +5,
    "depasse les attentes": +5,
    "au-dessus des attentes": +5,
    "au dessus des attentes": +5,
    "relève ses prévisions": +5,
    "releve ses previsions": +5,
    "hausse ses prévisions": +5,
    "hausse ses previsions": +5,
    "relève ses objectifs": +4,
    "releve ses objectifs": +4,
    "hausse du dividende": +4,
    "augmentation du dividende": +4,
    "rachat d'actions": +4,
    "programme de rachat": +4,
    "résultats record": +4,
    "resultats record": +4,
    "marge record": +4,
    "remporte un contrat": +3,
    "accord majeur": +3,

    "en dessous des attentes": -5,
    "au-dessous des attentes": -5,
    "au dessous des attentes": -5,
    "abaisse ses prévisions": -5,
    "abaisse ses previsions": -5,
    "réduit ses prévisions": -5,
    "reduit ses previsions": -5,
    "abaisse ses objectifs": -4,
    "réduit ses objectifs": -4,
    "reduit ses objectifs": -4,
    "sous enquête": -4,
    "sous enquete": -4,
    "perquisition": -4,
    "plainte": -3,
    "action collective": -4,
    "rappel de produit": -4,
    "cyberattaque": -4,
    "fuite de données": -4,
    "fuite de donnees": -4,
    "mise en garde": -3,
}

PHRASES_EN_W = {
    "beats estimates": +5,
    "beats expectations": +5,
    "tops estimates": +5,
    "raises guidance": +5,
    "raises forecast": +5,
    "raises outlook": +4,
    "record revenue": +4,
    "record profit": +4,
    "dividend hike": +4,
    "raises dividend": +4,
    "buyback announced": +4,
    "share buyback": +4,
    "wins contract": +3,

    "misses estimates": -5,
    "misses expectations": -5,
    "cuts guidance": -5,
    "lowers guidance": -5,
    "slashed forecast": -5,
    "sec probe": -4,
    "doj probe": -4,
    "antitrust probe": -4,
    "class action": -4,
    "lawsuit filed": -4,
    "price target cut": -4,
    "product recall": -4,
    "data breach": -4,
    "downgraded to": -4,
    "profit warning": -5,
}


# -----------------------------
# Helpers
# -----------------------------
def safe_strip(s: str) -> str:
    return (s or "").strip()


def validate_date_or_empty(s: str) -> bool:
    s = safe_strip(s)
    return (s == "") or bool(DATE_RE.match(s))


def normalize_domain(dom: str) -> str:
    dom = safe_strip(dom)
    dom = dom.replace("https://", "").replace("http://", "").strip("/")
    return dom


def build_query(user_query: str, recency: str, date_after: str, date_before: str, source_domain: str) -> str:
    q = safe_strip(user_query)
    if not q:
        return ""

    parts = [q]

    rec = safe_strip(recency)
    if rec in RECENCY_CHOICES:
        parts.append(f"when:{rec}")

    a = safe_strip(date_after)
    b = safe_strip(date_before)
    if a:
        parts.append(f"after:{a}")
    if b:
        parts.append(f"before:{b}")

    dom = normalize_domain(source_domain)
    if dom:
        parts.append(f"site:{dom}")

    return " ".join(parts)


def build_rss_url(q: str, hl: str, gl: str, ceid: str) -> str:
    params = {"q": q, "hl": hl, "gl": gl, "ceid": ceid}
    return f"{BASE_URL}?{urlencode(params)}"


def parse_entry_datetime(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        st = getattr(entry, attr, None)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except Exception:
                pass

    for attr in ("published", "updated"):
        s = getattr(entry, attr, None)
        if s:
            try:
                dt = parsedate_to_datetime(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass

    return datetime.now(timezone.utc)


def tokenize(text: str):
    text = (text or "").lower()
    return re.findall(r"[a-zàâçéèêëîïôùûüÿñæœ']+", text)


def detect_lang_simple(text: str) -> str:
    t = (text or "").lower()

    en_markers = [" the ", " shares", " earnings", " guidance", " outlook", " revenue", " quarter", " stock", " sec "]
    fr_markers = [" le ", " la ", " les ", " hausse", " baisse", " résultats", " resultats", " prévisions", " previsions", " action"]

    en_hits = sum(1 for m in en_markers if m in t)
    fr_hits = sum(1 for m in fr_markers if m in t)

    if en_hits > fr_hits:
        return "en"
    if fr_hits > en_hits:
        return "fr"

    if _ld_detect is not None:
        try:
            ld = _ld_detect(text)
            if ld.startswith("en"):
                return "en"
            if ld.startswith("fr"):
                return "fr"
        except Exception:
            pass

    return "fr"


def _apply_phrases(text_lc: str, phrases_w: dict) -> int:
    sc = 0
    for phr, w in phrases_w.items():
        if phr in text_lc:
            sc += w
    return sc


def score_text_fr(title: str, source: str = "") -> int:
    text = f"{title} {source}".strip()
    text_lc = text.lower()
    tokens = tokenize(text)

    score = 0
    score += _apply_phrases(text_lc, PHRASES_FR_W)

    for t in tokens:
        score += POS_WORDS_FR_W.get(t, 0)
        score -= NEG_WORDS_FR_W.get(t, 0)  # NEG weights are positive -> subtract
        score += FIN_WORDS_FR_W.get(t, 0)

    return score


def score_text_en(title: str, source: str = "") -> int:
    text = f"{title} {source}".strip()
    text_lc = text.lower()
    tokens = tokenize(text)

    score = 0
    score += _apply_phrases(text_lc, PHRASES_EN_W)

    for t in tokens:
        score += POS_WORDS_EN_W.get(t, 0)
        score -= NEG_WORDS_EN_W.get(t, 0)
        score += FIN_WORDS_EN_W.get(t, 0)

    return score


def score_text_auto(title: str, source: str = "") -> tuple[int, str]:
    lang = detect_lang_simple(f"{title} {source}")
    if lang == "en":
        return score_text_en(title, source), "en"
    return score_text_fr(title, source), "fr"


def label_from_score(score: int) -> str:
    if score > 0:
        return "POS"
    if score < 0:
        return "NEG"
    return "NEU"


def dedup_key(title: str, link: str) -> str:
    base = (link or title or "").strip().lower()
    return sha1(base.encode("utf-8", errors="ignore")).hexdigest()


# -----------------------------
# App
# -----------------------------
class GoogleRssProApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Google News RSS – PRO (FR/EN/DUAL + tri + POS/NEG + CSV)")
        self.root.geometry("1260x760")

        self.last_url = ""
        self.last_url_fr = ""
        self.last_url_en = ""
        self.last_query = ""

        self._tag_counter = 0

        # ===== Top config =====
        top = ttk.Frame(root, padding=10)
        top.pack(side="top", fill="x")

        ttk.Label(top, text="Query / Symbol:").grid(row=0, column=0, sticky="w")
        self.var_query = tk.StringVar(value="AVGO OR Broadcom")
        self.ent_query = ttk.Entry(top, textvariable=self.var_query, width=62)
        self.ent_query.grid(row=0, column=1, sticky="we", padx=(6, 12))

        ttk.Label(top, text="Récence:").grid(row=0, column=2, sticky="w")
        self.var_recency = tk.StringVar(value="1d")
        self.cmb_recency = ttk.Combobox(top, textvariable=self.var_recency, values=RECENCY_CHOICES,
                                        width=6, state="readonly")
        self.cmb_recency.grid(row=0, column=3, sticky="w", padx=(6, 12))

        ttk.Label(top, text="Langue:").grid(row=0, column=4, sticky="w")
        self.var_lang_mode = tk.StringVar(value="FR+EN")
        self.cmb_lang = ttk.Combobox(top, textvariable=self.var_lang_mode, values=LANG_CHOICES,
                                     width=7, state="readonly")
        self.cmb_lang.grid(row=0, column=5, sticky="w", padx=(6, 12))

        ttk.Label(top, text="After (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.var_after = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.var_after, width=16).grid(row=1, column=1, sticky="w",
                                                                    padx=(6, 12), pady=(8, 0))

        ttk.Label(top, text="Before (YYYY-MM-DD):").grid(row=1, column=2, sticky="w", pady=(8, 0))
        self.var_before = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.var_before, width=16).grid(row=1, column=3, sticky="w",
                                                                     padx=(6, 12), pady=(8, 0))

        ttk.Label(top, text="Source (domain):").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.var_site = tk.StringVar(value="")
        ttk.Entry(top, textvariable=self.var_site, width=24).grid(row=2, column=1, sticky="w",
                                                                   padx=(6, 12), pady=(8, 0))

        filters = ttk.Frame(top)
        filters.grid(row=2, column=2, columnspan=4, sticky="w", pady=(8, 0))

        self.var_show_pos = tk.BooleanVar(value=True)
        self.var_show_neg = tk.BooleanVar(value=True)
        ttk.Checkbutton(filters, text="POS", variable=self.var_show_pos, command=self.refresh_view).pack(side="left", padx=(0, 10))
        ttk.Checkbutton(filters, text="NEG", variable=self.var_show_neg, command=self.refresh_view).pack(side="left")

        # Buttons
        btns = ttk.Frame(top)
        btns.grid(row=0, column=6, rowspan=3, padx=(12, 0), sticky="ns")

        ttk.Button(btns, text="▶ Fetch", command=self.on_fetch).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="💾 SAVE CSV", command=self.on_save_csv).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="📋 Copier URL(s)", command=self.on_copy_url).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="🌐 Ouvrir", command=self.on_open_browser).pack(fill="x", pady=(0, 6))
        ttk.Button(btns, text="🧹 Clear", command=self.clear_terminal).pack(fill="x")

        top.columnconfigure(1, weight=1)

        # ===== Terminal =====
        mid = ttk.Frame(root, padding=(10, 0, 10, 0))
        mid.pack(side="top", fill="both", expand=True)

        self.terminal = ScrolledText(mid, wrap="word", font=("Consolas", 10))
        self.terminal.pack(fill="both", expand=True)

        self.terminal.tag_configure("pos", foreground="#0b3d0b")
        self.terminal.tag_configure("neg", foreground="#5a0b0b")
        self.terminal.tag_configure("neu", foreground="#333333")

        # ===== Status bar =====
        bottom = ttk.Frame(root, padding=(10, 6, 10, 10))
        bottom.pack(side="bottom", fill="x")

        self.status_var = tk.StringVar(value="News traitées: 0 | Ambiance: [NEUTRE]")
        ttk.Label(bottom, textvariable=self.status_var, anchor="w").pack(fill="x")

        self.items = []  # {dt,title,source,link,score,label,lang}

        self.log("Prêt. Mode langue: FR / EN / FR+EN.\n")
        if feedparser is None:
            self.log("⚠️ feedparser manquant. Installe: pip install feedparser\n")
        if _ld_detect is None:
            self.log("ℹ️ Détection langue: heuristique (langdetect optionnel: pip install langdetect)\n")

    def log(self, msg: str, tag: str = None):
        if tag:
            self.terminal.insert("end", msg, tag)
        else:
            self.terminal.insert("end", msg)
        self.terminal.see("end")

    def clear_terminal(self):
        self.terminal.delete("1.0", "end")

    def build_and_validate(self):
        if not validate_date_or_empty(self.var_after.get()):
            raise ValueError("After doit être vide ou au format YYYY-MM-DD (ex: 2025-12-01).")
        if not validate_date_or_empty(self.var_before.get()):
            raise ValueError("Before doit être vide ou au format YYYY-MM-DD (ex: 2025-12-19).")

        q = build_query(
            user_query=self.var_query.get(),
            recency=self.var_recency.get(),
            date_after=self.var_after.get(),
            date_before=self.var_before.get(),
            source_domain=self.var_site.get(),
        )
        if not q:
            raise ValueError("La requête est vide.")

        mode = self.var_lang_mode.get().strip()
        if mode not in LANG_CHOICES:
            mode = "FR+EN"

        urls = []
        self.last_url_fr = ""
        self.last_url_en = ""
        self.last_url = ""
        self.last_query = q

        if mode in ("FR", "FR+EN"):
            ufr = build_rss_url(q, **EDITION_FR)
            urls.append(("FR", ufr))
            self.last_url_fr = ufr

        if mode in ("EN", "FR+EN"):
            uen = build_rss_url(q, **EDITION_EN)
            urls.append(("EN", uen))
            self.last_url_en = uen

        if len(urls) == 1:
            self.last_url = urls[0][1]

        return q, urls

    def on_copy_url(self):
        try:
            _q, urls = self.build_and_validate()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return

        if not urls:
            return

        txt = urls[0][1] if len(urls) == 1 else " | ".join([f"{lab}:{url}" for lab, url in urls])
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.update_status(extra="URL(s) copiée(s)")

    def on_open_browser(self):
        try:
            _q, urls = self.build_and_validate()
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        for _lab, url in urls:
            webbrowser.open(url)

    def compute_overall_label(self) -> str:
        if not self.items:
            return "[NEUTRE]"
        avg = sum(it["score"] for it in self.items) / max(1, len(self.items))
        if avg > 0.25:
            return "[POS]"
        if avg < -0.25:
            return "[NEG]"
        return "[NEUTRE]"

    def update_status(self, extra: str = ""):
        base = f"News traitées: {len(self.items)} | Ambiance: {self.compute_overall_label()}"
        self.status_var.set(f"{extra} | {base}" if extra else base)

    def refresh_view(self):
        self.clear_terminal()

        show_pos = self.var_show_pos.get()
        show_neg = self.var_show_neg.get()

        filtered = []
        for it in self.items:
            if it["label"] == "POS" and not show_pos:
                continue
            if it["label"] == "NEG" and not show_neg:
                continue
            filtered.append(it)

        for it in filtered:
            self.print_item(it)

        self.update_status()

    def _add_clickable_info(self, link: str):
        self._tag_counter += 1
        tag = f"i_link_{self._tag_counter}"
        start = self.terminal.index("end-1c")
        self.terminal.insert("end", "[i]")
        end = self.terminal.index("end-1c")

        self.terminal.tag_add(tag, start, end)
        self.terminal.tag_configure(tag, foreground="#1a73e8", underline=True)
        self.terminal.tag_bind(tag, "<Button-1>", lambda _e, u=link: webbrowser.open(u))
        self.terminal.insert("end", " ")

    def print_item(self, it: dict):
        dt_local = it["dt"].astimezone()
        ts = dt_local.strftime("%Y-%m-%d %H:%M")
        prefix = f"[{ts}] [{it['label']} {it['score']:+d}]"

        tag = "neu"
        if it["label"] == "POS":
            tag = "pos"
        elif it["label"] == "NEG":
            tag = "neg"

        src = it["source"] or "Source?"
        title = it["title"] or "(sans titre)"
        lang = it.get("lang", "?").upper()

        self.log(f"{prefix} [{lang}] ", tag)
        self.log(f"{src} – {title} ", tag)
        self._add_clickable_info(it["link"])
        self.log("\n")

    def _fetch_one(self, url: str):
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        feed = feedparser.parse(r.text)
        return getattr(feed, "entries", []) or []

    def on_fetch(self):
        def worker():
            if feedparser is None:
                self.root.after(0, lambda: messagebox.showerror("Erreur", "feedparser manquant. Fais: pip install feedparser"))
                return

            try:
                _q, urls = self.build_and_validate()
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erreur", str(e)))
                return

            all_entries = []
            try:
                for _label, url in urls:
                    all_entries.extend(self._fetch_one(url))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erreur HTTP", str(e)))
                return

            seen = set()
            new_items = []
            for e in all_entries:
                title = safe_strip(getattr(e, "title", ""))
                link = safe_strip(getattr(e, "link", ""))

                src = ""
                try:
                    if hasattr(e, "source") and hasattr(e.source, "title"):
                        src = safe_strip(str(e.source.title))
                except Exception:
                    src = ""

                dt = parse_entry_datetime(e)

                score, lang = score_text_auto(title, src)
                lab = label_from_score(score)

                k = dedup_key(title, link)
                if k in seen:
                    continue
                seen.add(k)

                new_items.append({
                    "dt": dt,
                    "title": title,
                    "source": src,
                    "link": link,
                    "score": score,
                    "label": lab,
                    "lang": lang,
                })

            new_items.sort(key=lambda x: x["dt"], reverse=True)
            self.items = new_items
            self.root.after(0, self.refresh_view)

        threading.Thread(target=worker, daemon=True).start()

    def on_save_csv(self):
        if not self.items:
            messagebox.showinfo("SAVE CSV", "Aucun résultat à sauvegarder. Lance Fetch d’abord.")
            return

        default_name = "google_news_rss_export.csv"
        path = filedialog.asksaveasfilename(
            title="Enregistrer CSV",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return

        # CSV: simple, utile pour IA / ingestion
        # dt_utc, dt_local, lang, label, score, source, title, url, query
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["dt_utc", "dt_local", "lang", "label", "score", "source", "title", "url", "query"])
                for it in self.items:
                    dt_utc = it["dt"].astimezone(timezone.utc)
                    dt_local = it["dt"].astimezone()
                    w.writerow([
                        dt_utc.strftime("%Y-%m-%d %H:%M:%S%z"),
                        dt_local.strftime("%Y-%m-%d %H:%M:%S%z"),
                        it.get("lang", ""),
                        it.get("label", ""),
                        it.get("score", 0),
                        it.get("source", ""),
                        it.get("title", ""),
                        it.get("link", ""),
                        self.last_query,
                    ])
            self.update_status(extra=f"CSV sauvegardé: {path}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'écrire le CSV:\n{e}")


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    app = GoogleRssProApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
