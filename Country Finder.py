"""
Install:
    python3 -m pip install pillow requests
"""
import io
import json
import threading
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont

try:
    import requests  # type: ignore
except Exception:
    requests = None

from PIL import Image, ImageTk  # type: ignore


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class Country:
    name_common: str
    name_official: str
    capital: str
    region: str
    subregion: str
    population: int
    area: float
    languages: str
    currencies: str
    borders: str
    flag_url: str

    @staticmethod
    def _safe_get(d, path, default=""):
        cur = d
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return default
        return cur

    @staticmethod
    def from_api(raw: Dict[str, Any]) -> "Country":
        name_common = Country._safe_get(raw, ("name", "common"), "Unknown")
        name_official = Country._safe_get(raw, ("name", "official"), "Unknown")
        capitals = raw.get("capital") or []
        capital = capitals[0] if isinstance(capitals, list) and capitals else "N/A"
        region = raw.get("region", "N/A") or "N/A"
        subregion = raw.get("subregion", "N/A") or "N/A"
        population = int(raw.get("population") or 0)
        area = float(raw.get("area") or 0.0)
        langs = raw.get("languages") or {}
        languages = ", ".join(langs.values()) if isinstance(langs, dict) and langs else "N/A"
        curr = raw.get("currencies") or {}
        if isinstance(curr, dict) and curr:
            parts = []
            for code, info in curr.items():
                if isinstance(info, dict):
                    nm = info.get("name", "")
                    sym = info.get("symbol", "")
                    if nm and sym:
                        parts.append(f"{nm} ({code}, {sym})")
                    elif nm:
                        parts.append(f"{nm} ({code})")
                    else:
                        parts.append(str(code))
                else:
                    parts.append(str(code))
            currencies = ", ".join(parts) if parts else "N/A"
        else:
            currencies = "N/A"
        borders_list = raw.get("borders") or []
        borders = ", ".join(borders_list) if isinstance(borders_list, list) and borders_list else "None"
        flags = raw.get("flags") or {}
        flag_url = ""
        if isinstance(flags, dict):
            flag_url = flags.get("png") or flags.get("svg") or ""
        return Country(
            name_common=name_common, name_official=name_official, capital=capital,
            region=region, subregion=subregion, population=population, area=area,
            languages=languages, currencies=currencies, borders=borders, flag_url=flag_url,
        )


# ── API Layer ─────────────────────────────────────────────────────────────────

class CountryAPI:
    BASE_URL = "https://restcountries.com/v3.1"
    TIMEOUT = 14
    FIELDS = "name,capital,region,subregion,population,area,languages,currencies,borders,flags"

    def __init__(self):
        self.cache: Dict[str, List[Dict[str, Any]]] = {}

    def _build_url(self, endpoint: str) -> str:
        url = f"{self.BASE_URL}{endpoint}"
        return f"{url}&fields={self.FIELDS}" if "?" in url else f"{url}?fields={self.FIELDS}"

    def safe_request(self, endpoint: str) -> List[Dict[str, Any]]:
        key = endpoint.strip().lower()
        if key in self.cache:
            return self.cache[key]
        url = self._build_url(endpoint)
        try:
            if requests is not None:
                resp = requests.get(url, timeout=self.TIMEOUT, headers={"User-Agent": "CountryExplorer/1.0"})
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
                data = resp.json()
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "CountryExplorer/1.0"})
                with urllib.request.urlopen(req, timeout=self.TIMEOUT) as r:
                    data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            raise RuntimeError(
                "Failed to load data from Rest Countries API.\n\n"
                "Fix checklist:\n1) Check internet\n2) pip install requests pillow\n3) Try again\n\n"
                f"Error: {e}"
            ) from e
        if not isinstance(data, list):
            return []
        self.cache[key] = data
        return data

    def get_by_name(self, name: str, full_text: bool = False) -> List[Country]:
        name = name.strip()
        if not name:
            return []
        suffix = "?fullText=true" if full_text else ""
        return [Country.from_api(x) for x in self.safe_request(f"/name/{urllib.parse.quote(name)}{suffix}")]

    def get_by_capital(self, capital: str) -> List[Country]:
        capital = capital.strip()
        if not capital:
            return []
        return [Country.from_api(x) for x in self.safe_request(f"/capital/{urllib.parse.quote(capital)}")]

    def get_by_region(self, region: str) -> List[Country]:
        region = region.strip()
        if not region:
            return []
        return [Country.from_api(x) for x in self.safe_request(f"/region/{urllib.parse.quote(region)}")]

    def get_all(self) -> List[Country]:
        return [Country.from_api(x) for x in self.safe_request("/all")]


# ── Scrollable Frame ──────────────────────────────────────────────────────────

class ScrollableFrame(ttk.Frame):
    def __init__(self, parent, bg: str):
        super().__init__(parent)
        self.bg = bg
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.inner_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vsb.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.inner_id, width=e.width))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self.canvas.bind_all("<Button-4>", lambda _e: self.canvas.yview_scroll(-2, "units"))
        self.canvas.bind_all("<Button-5>", lambda _e: self.canvas.yview_scroll(2, "units"))


# ── Main App ──────────────────────────────────────────────────────────────────

class CountryExplorerApp(tk.Tk):
    REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania", "Antarctic"]
    REGIONS_WITH_ALL = ["All"] + REGIONS

    def __init__(self):
        super().__init__()
        self.title("Country Explorer")
        self.minsize(1380, 860)

        self.api = CountryAPI()
        self.current: List[Country] = []
        self.all_countries: List[Country] = []
        self.flag_cache: Dict[str, ImageTk.PhotoImage] = {}
        self.country_lookup_cache: Dict[str, Country] = {}
        self.status_var = tk.StringVar(value="Ready")

        self.all_filter = tk.StringVar(value="")
        self.all_sort = tk.StringVar(value="Name (A-Z)")
        self.all_region = tk.StringVar(value="All")
        self.compare_a = tk.StringVar(value="")
        self.compare_b = tk.StringVar(value="")

        self._theme()
        self._build_pages()
        self._show_page("splash")
        self.bind("<Return>", self._on_enter)

    # ── THEME ──────────────────────────────────────────────────────────────────

    def _theme(self):
        self.C = {
            "bg":           "#0f172a",
            "bg2":          "#1e293b",
            "bg3":          "#334155",
            "text":         "#f1f5f9",
            "muted":        "#94a3b8",
            "subtle":       "#64748b",
            "accent":       "#14b8a6",
            "accent_dark":  "#0d9488",
            "accent_glow":  "#5eead4",
            "panel":        "#162032",
            "panel2":       "#1a2840",
            "border":       "#2d3f58",
            "border_light": "#3d5173",
            "select_bg":    "#14b8a6",
            "select_fg":    "#0f172a",
            "card":         "#1e293b",
            "card2":        "#243347",
        }

        self.configure(bg=self.C["bg"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.F_HERO  = tkfont.Font(family="Georgia",      size=42, weight="bold")
        self.F_TITLE = tkfont.Font(family="Georgia",      size=26, weight="bold")
        self.F_H1    = tkfont.Font(family="Trebuchet MS", size=17, weight="bold")
        self.F_H2    = tkfont.Font(family="Trebuchet MS", size=12, weight="bold")
        self.F_BODY  = tkfont.Font(family="Trebuchet MS", size=11)
        self.F_LABEL = tkfont.Font(family="Trebuchet MS", size=10)
        self.F_MONO  = tkfont.Font(family="Courier New",  size=10)

        C = self.C
        style.configure("TFrame",        background=C["bg"])
        style.configure("Panel.TFrame",  background=C["panel"])
        style.configure("Panel2.TFrame", background=C["panel2"])
        style.configure("Card.TFrame",   background=C["card"])
        style.configure("Card2.TFrame",  background=C["card2"])

        style.configure("TLabel",          background=C["bg"],    foreground=C["text"],  font=self.F_BODY)
        style.configure("Muted.TLabel",    background=C["bg"],    foreground=C["muted"], font=self.F_BODY)
        style.configure("Panel.TLabel",    background=C["panel"], foreground=C["text"],  font=self.F_BODY)
        style.configure("MutedPanel.TLabel", background=C["panel"], foreground=C["muted"], font=self.F_BODY)
        style.configure("Card.TLabel",     background=C["card"],  foreground=C["text"],  font=self.F_BODY)
        style.configure("MutedCard.TLabel",background=C["card"],  foreground=C["muted"], font=self.F_BODY)

        style.configure("Primary.TButton",
            background=C["accent"], foreground=C["bg"],
            padding=(16, 11), borderwidth=0, font=self.F_H2)
        style.map("Primary.TButton", background=[("active", C["accent_dark"])])

        style.configure("Nav.TButton",
            background=C["bg3"], foreground=C["text"],
            padding=(12, 9), borderwidth=0, font=self.F_LABEL)
        style.map("Nav.TButton", background=[("active", C["border_light"])])

        style.configure("SideNav.TButton",
            background=C["panel2"], foreground=C["text"],
            padding=(12, 10), borderwidth=0, font=self.F_BODY)
        style.map("SideNav.TButton",
            background=[("active", C["bg3"])],
            foreground=[("active", C["accent_glow"])])

        style.configure("SidePrimary.TButton",
            background=C["accent"], foreground=C["bg"],
            padding=(14, 11), borderwidth=0, font=self.F_H2)
        style.map("SidePrimary.TButton", background=[("active", C["accent_dark"])])

        style.configure("Ghost.TButton",
            background=C["bg2"], foreground=C["muted"],
            padding=(13, 10), borderwidth=1, font=self.F_LABEL)
        style.map("Ghost.TButton",
            background=[("active", C["bg3"])],
            foreground=[("active", C["text"])])

        style.configure("SmallGhost.TButton",
            background=C["bg2"], foreground=C["muted"],
            padding=(9, 7), borderwidth=1, font=self.F_LABEL)
        style.map("SmallGhost.TButton",
            background=[("active", C["bg3"])],
            foreground=[("active", C["text"])])

        style.configure("TCombobox",
            fieldbackground=C["bg2"], background=C["bg3"],
            foreground=C["text"], selectbackground=C["accent"],
            selectforeground=C["bg"], padding=6)
        style.map("TCombobox",
            fieldbackground=[("readonly", C["bg2"])],
            foreground=[("readonly", C["text"])])

        style.configure("TEntry",
            fieldbackground=C["bg2"], foreground=C["text"],
            insertcolor=C["accent"], padding=6)

        style.configure("Treeview",
            background=C["card"], foreground=C["text"],
            fieldbackground=C["card"], rowheight=28, font=self.F_BODY)
        style.configure("Treeview.Heading",
            background=C["bg3"], foreground=C["accent_glow"], font=self.F_H2)
        style.map("Treeview",
            background=[("selected", C["accent"])],
            foreground=[("selected", C["bg"])])

        style.configure("Horizontal.TProgressbar",
            troughcolor=C["bg3"], background=C["accent"])
        style.configure("TSeparator", background=C["border"])
        style.configure("Vertical.TScrollbar",
            background=C["bg3"], troughcolor=C["bg2"], arrowcolor=C["muted"])
        style.configure("TCheckbutton",
            background=C["card2"], foreground=C["text"], font=self.F_BODY)
        style.map("TCheckbutton", background=[("active", C["card2"])])
        style.configure("TPanedwindow", background=C["border"])

    # ── PAGES ──────────────────────────────────────────────────────────────────

    def _build_pages(self):
        self.container = ttk.Frame(self, style="TFrame")
        self.container.pack(fill="both", expand=True)
        self.pages: Dict[str, ttk.Frame] = {
            "splash":  ttk.Frame(self.container, style="TFrame"),
            "main":    ttk.Frame(self.container, style="TFrame"),
            "all":     ttk.Frame(self.container, style="TFrame"),
            "compare": ttk.Frame(self.container, style="TFrame"),
        }
        self._build_splash(self.pages["splash"])
        self._build_main(self.pages["main"])
        self._build_all(self.pages["all"])
        self._build_compare(self.pages["compare"])
        for p in self.pages.values():
            p.pack_forget()

    def _show_page(self, name: str):
        for k, f in self.pages.items():
            if k == name:
                f.pack(fill="both", expand=True)
            else:
                f.pack_forget()
        self.set_status("Ready")

    # ── SPLASH ─────────────────────────────────────────────────────────────────

    def _build_splash(self, parent: ttk.Frame):
        C = self.C
        tk.Frame(parent, bg=C["accent"], height=4).pack(fill="x")

        hdr = tk.Frame(parent, bg=C["bg2"], highlightbackground=C["border"], highlightthickness=1)
        hdr.pack(fill="x")
        tk.Label(hdr, text="CODELAB A1  •  Data Driven App",
                 bg=C["bg2"], fg=C["muted"], font=self.F_LABEL).pack(side="left", padx=20, pady=11)
        tk.Label(hdr, text="Rest Countries API",
                 bg=C["bg2"], fg=C["accent"], font=self.F_LABEL).pack(side="right", padx=20, pady=11)

        body = tk.Frame(parent, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=32, pady=26)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)

        left = tk.Frame(body, bg=C["bg"])
        right = tk.Frame(body, bg=C["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 28))
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(left, text="COUNTRY", bg=C["bg"], fg=C["text"],
                 font=self.F_HERO, justify="left").pack(anchor="w", pady=(20, 0))
        tk.Label(left, text="EXPLORER", bg=C["bg"], fg=C["accent"],
                 font=self.F_HERO, justify="left").pack(anchor="w", pady=(0, 10))
        tk.Label(left,
                 text="Explore real-time country data with a clean, fast interface.\n"
                      "Search  •  Filter  •  Compare  •  Browse all flags.",
                 bg=C["bg"], fg=C["muted"], font=self.F_BODY, justify="left"
                 ).pack(anchor="w", pady=(0, 22))

        cta = tk.Frame(left, bg=C["bg"])
        cta.pack(anchor="w", pady=(0, 22))
        ttk.Button(cta, text="Start Exploring", style="Primary.TButton",
                   command=self._start_app).pack(side="left")
        ttk.Button(cta, text="Quick Demo (Load Asia)", style="Ghost.TButton",
                   command=self._quick_demo).pack(side="left", padx=14)

        bullets = tk.Frame(left, bg=C["bg"])
        bullets.pack(anchor="w")
        for t in [
            "Threaded loading — no UI freeze",
            "Comparison page with full table layout",
            "All-countries flag grid with filters & sorting",
            "Deep navy / teal theme",
        ]:
            row = tk.Frame(bullets, bg=C["bg"])
            row.pack(anchor="w", pady=5)
            tk.Label(row, text="◆ ", bg=C["bg"], fg=C["accent"],
                     font=tkfont.Font(size=9)).pack(side="left")
            tk.Label(row, text=t, bg=C["bg"], fg=C["text"],
                     font=self.F_BODY).pack(side="left")

        def card(p, title, desc, icon=""):
            c = tk.Frame(p, bg=C["card2"], highlightbackground=C["border"], highlightthickness=1)
            h = tk.Frame(c, bg=C["card2"])
            h.pack(fill="x", padx=16, pady=(14, 4))
            if icon:
                tk.Label(h, text=icon, bg=C["card2"], fg=C["accent"],
                         font=self.F_H1).pack(side="left", padx=(0, 8))
            tk.Label(h, text=title, bg=C["card2"], fg=C["accent_glow"],
                     font=self.F_H2).pack(side="left")
            tk.Label(c, text=desc, bg=C["card2"], fg=C["muted"],
                     font=self.F_BODY, justify="left", wraplength=360
                     ).pack(anchor="w", padx=16, pady=(0, 14))
            return c

        tk.Label(right, text="Features", bg=C["bg"],
                 fg=C["subtle"], font=self.F_H2).pack(anchor="w", pady=(20, 8))
        card(right, "Search & Filter",
             "Find countries by name or capital, or filter by region.", "⌕").pack(fill="x", pady=(0, 10))
        card(right, "Compare (Table View)",
             "Compare two countries side-by-side with flags and a structured table.", "⇄").pack(fill="x", pady=(0, 10))
        card(right, "All Countries Grid",
             "Browse all ~250 countries in a scrollable flag grid with sorting.", "⊞").pack(fill="x")

        footer = tk.Frame(parent, bg=C["panel"], highlightbackground=C["border"], highlightthickness=1)
        footer.pack(fill="x")
        tk.Label(footer, text="  ⌨  Tip: Press Enter to run the current action on the main page.",
                 bg=C["panel"], fg=C["muted"], font=self.F_LABEL
                 ).pack(side="left", padx=14, pady=10)

    def _start_app(self):
        self._show_page("main")
        self._switch_mode("name")

    def _quick_demo(self):
        self._show_page("main")
        self._switch_mode("region")
        self.region_var.set("Asia")
        self.on_filter_region()

    # ── MAIN PAGE ──────────────────────────────────────────────────────────────

    def _build_main(self, parent: ttk.Frame):
        C = self.C
        root = tk.Frame(parent, bg=C["bg"])
        root.pack(fill="both", expand=True)

        tk.Frame(root, bg=C["accent"], height=3).pack(fill="x")

        self.topbar = tk.Frame(root, bg=C["bg2"], highlightbackground=C["border"], highlightthickness=1)
        self.topbar.pack(fill="x")
        tk.Label(self.topbar, text="COUNTRY EXPLORER",
                 bg=C["bg2"], fg=C["accent"], font=self.F_H1).pack(side="left", padx=20, pady=12)
        self.top_page = tk.Label(self.topbar, text="Search by Name",
                                 bg=C["bg2"], fg=C["muted"], font=self.F_BODY)
        self.top_page.pack(side="left", padx=(6, 0), pady=12)

        qa = tk.Frame(self.topbar, bg=C["bg2"])
        qa.pack(side="right", padx=16, pady=8)
        for (lbl, cmd) in [("Compare",       self.open_compare_page),
                            ("All Countries", self.open_all_countries),
                            ("Reset",         self.clear_all),
                            ("Home",          lambda: self._show_page("splash"))]:
            ttk.Button(qa, text=lbl, style="SmallGhost.TButton", command=cmd).pack(side="left", padx=4)

        body = tk.Frame(root, bg=C["bg"])
        body.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = tk.Frame(body, bg=C["panel"], width=280)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        inner_side = tk.Frame(self.sidebar, bg=C["panel"])
        inner_side.pack(fill="both", expand=True, padx=14, pady=16)

        tk.Label(inner_side, text="NAVIGATION",
                 bg=C["panel"], fg=C["accent"], font=self.F_H2).pack(anchor="w", pady=(0, 12))

        self.mode = tk.StringVar(value="name")

        for (lbl, mode) in [("⌕  Search by Name",    "name"),
                             ("⌕  Search by Capital", "capital"),
                             ("◈  Filter by Region",  "region")]:
            m = mode
            ttk.Button(inner_side, text=lbl, style="SideNav.TButton",
                       command=lambda m=m: self._switch_mode(m)).pack(fill="x", pady=4)

        ttk.Button(inner_side, text="⇄  Open Compare Page",
                   style="SideNav.TButton",
                   command=self.open_compare_page).pack(fill="x", pady=4)

        tk.Frame(inner_side, bg=C["border"], height=1).pack(fill="x", pady=12)
        ttk.Button(inner_side, text="⊞  All Countries (Flags)",
                   style="SidePrimary.TButton",
                   command=self.open_all_countries).pack(fill="x", pady=(0, 8))
        ttk.Button(inner_side, text="↺  Clear / Reset",
                   style="SideNav.TButton",
                   command=self.clear_all).pack(fill="x")
        tk.Frame(inner_side, bg=C["border"], height=1).pack(fill="x", pady=12)

        self.progress = ttk.Progressbar(inner_side, mode="indeterminate", length=220)
        self.progress.pack(fill="x")
        ttk.Label(inner_side, textvariable=self.status_var,
                  style="MutedPanel.TLabel").pack(anchor="w", pady=(8, 0))

        # Content
        self.content = tk.Frame(body, bg=C["bg"])
        self.content.pack(side="right", fill="both", expand=True, padx=18, pady=14)

        self.search_panel = tk.Frame(self.content, bg=C["card2"],
                                     highlightbackground=C["border"], highlightthickness=1)
        self.search_panel.pack(fill="x", pady=(0, 12))
        inner_sp = tk.Frame(self.search_panel, bg=C["card2"])
        inner_sp.pack(fill="x", padx=14, pady=10)
        self._build_search_sections(inner_sp)

        split = ttk.PanedWindow(self.content, orient="horizontal")
        split.pack(fill="both", expand=True)
        lp = ttk.Frame(split, style="TFrame")
        rp = ttk.Frame(split, style="TFrame")
        split.add(lp, weight=3)
        split.add(rp, weight=2)

        self._build_results_area(lp)
        self._build_details_area(rp)
        self._switch_mode("name")

    def _build_search_sections(self, parent):
        C = self.C
        bg = C["card2"]
        self.name_q     = tk.StringVar()
        self.cap_q      = tk.StringVar()
        self.region_var = tk.StringVar(value="Asia")
        self.exact_var  = tk.BooleanVar(value=False)

        self.section_name    = tk.Frame(parent, bg=bg)
        self.section_capital = tk.Frame(parent, bg=bg)
        self.section_region  = tk.Frame(parent, bg=bg)

        # Name
        tk.Label(self.section_name, text="Country name:", bg=bg,
                 fg=C["muted"], font=self.F_H2).grid(row=0, column=0, sticky="w")
        self.name_entry = ttk.Entry(self.section_name, textvariable=self.name_q, width=36)
        self.name_entry.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Checkbutton(self.section_name, text="Exact match",
                        variable=self.exact_var).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Button(self.section_name, text="Search", style="Primary.TButton",
                   command=self.on_search_name).grid(row=1, column=2, padx=(12, 0), pady=(6, 0))
        ttk.Button(self.section_name, text="Clear", style="Ghost.TButton",
                   command=self.clear_all).grid(row=1, column=3, padx=(8, 0), pady=(6, 0))
        self.section_name.columnconfigure(0, weight=1)

        # Capital
        tk.Label(self.section_capital, text="Capital city:", bg=bg,
                 fg=C["muted"], font=self.F_H2).grid(row=0, column=0, sticky="w")
        self.cap_entry = ttk.Entry(self.section_capital, textvariable=self.cap_q, width=36)
        self.cap_entry.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(self.section_capital, text="Search", style="Primary.TButton",
                   command=self.on_search_capital).grid(row=1, column=1, padx=(12, 0), pady=(6, 0))
        ttk.Button(self.section_capital, text="Clear", style="Ghost.TButton",
                   command=self.clear_all).grid(row=1, column=2, padx=(8, 0), pady=(6, 0))
        self.section_capital.columnconfigure(0, weight=1)

        # Region
        tk.Label(self.section_region, text="Region:", bg=bg,
                 fg=C["muted"], font=self.F_H2).grid(row=0, column=0, sticky="w")
        self.region_combo = ttk.Combobox(self.section_region, textvariable=self.region_var,
                                         values=self.REGIONS, state="readonly", width=34)
        self.region_combo.grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(self.section_region, text="Load Region", style="Primary.TButton",
                   command=self.on_filter_region).grid(row=1, column=1, padx=(12, 0), pady=(6, 0))
        ttk.Button(self.section_region, text="Clear", style="Ghost.TButton",
                   command=self.clear_all).grid(row=1, column=2, padx=(8, 0), pady=(6, 0))
        self.section_region.columnconfigure(0, weight=1)

    def _build_results_area(self, parent: ttk.Frame):
        C = self.C
        card = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=(0, 6))

        hdr = tk.Frame(card, bg=C["card"])
        hdr.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(hdr, text="Results", bg=C["card"], fg=C["accent_glow"], font=self.F_H2).pack(side="left")
        tk.Label(hdr, text="  Sort:", bg=C["card"], fg=C["muted"], font=self.F_LABEL).pack(side="left")
        self.sort_var = tk.StringVar(value="Name (A-Z)")
        self.sort_combo = ttk.Combobox(hdr, textvariable=self.sort_var,
                                       values=["Name (A-Z)", "Name (Z-A)", "Population", "Area"],
                                       state="readonly", width=16)
        self.sort_combo.pack(side="left", padx=(6, 0))
        self.sort_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_results())

        wrap = tk.Frame(card, bg=C["card"])
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        sb = ttk.Scrollbar(wrap, orient="vertical")
        self.results_list = tk.Listbox(
            wrap, bg=C["bg2"], fg=C["text"],
            selectbackground=C["select_bg"], selectforeground=C["select_fg"],
            highlightthickness=0, borderwidth=0, activestyle="none", font=self.F_BODY)
        self.results_list.config(yscrollcommand=sb.set)
        sb.config(command=self.results_list.yview)
        self.results_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.results_list.bind("<<ListboxSelect>>", self.on_select_country)
        self.results_list.bind("<Double-Button-1>", lambda _e: self._send_selected_to_compare())

    def _build_details_area(self, parent: ttk.Frame):
        C = self.C
        card = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        card.pack(fill="both", expand=True, padx=(6, 0))

        inner = tk.Frame(card, bg=C["card"])
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        tk.Label(inner, text="Details", bg=C["card"], fg=C["accent_glow"], font=self.F_H2).pack(anchor="w")

        flagbox = tk.Frame(inner, bg=C["bg3"], highlightbackground=C["border"], highlightthickness=1)
        flagbox.pack(fill="x", pady=(8, 10))
        self.flag_label = tk.Label(flagbox, text="(flag)", bg=C["bg3"], fg=C["muted"])
        self.flag_label.pack(padx=10, pady=10)

        text_wrap = tk.Frame(inner, bg=C["card"])
        text_wrap.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(text_wrap, orient="vertical")
        self.detail_text = tk.Text(
            text_wrap, wrap="word", bg=C["bg2"], fg=C["text"],
            insertbackground=C["accent"], highlightthickness=0, borderwidth=0,
            font=self.F_BODY, height=18, yscrollcommand=sb.set)
        sb.config(command=self.detail_text.yview)
        self.detail_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._set_details_text("Select a country from the Results list to view details.")
        self.detail_text.config(state="disabled")

        tk.Label(inner, text="Tip: Double-click a result to send it to Compare.",
                 bg=C["card"], fg=C["subtle"], font=self.F_LABEL).pack(anchor="w", pady=(8, 0))

    # ── ALL COUNTRIES PAGE ─────────────────────────────────────────────────────

    def _build_all(self, parent: ttk.Frame):
        C = self.C
        tk.Frame(parent, bg=C["accent"], height=3).pack(fill="x")

        wrap = tk.Frame(parent, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=16)

        hdr = tk.Frame(wrap, bg=C["bg"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="All Countries", bg=C["bg"], fg=C["text"], font=self.F_TITLE).pack(side="left")
        ttk.Button(hdr, text="<- Back to App", style="Ghost.TButton",
                   command=lambda: self._show_page("main")).pack(side="right")

        bar = tk.Frame(wrap, bg=C["card2"], highlightbackground=C["border"], highlightthickness=1)
        bar.pack(fill="x", pady=(14, 12))
        ib = tk.Frame(bar, bg=C["card2"])
        ib.pack(fill="x", padx=12, pady=10)

        tk.Label(ib, text="Filter:", bg=C["card2"], fg=C["muted"], font=self.F_LABEL).grid(row=0, column=0, sticky="w")
        self.all_filter_entry = ttk.Entry(ib, textvariable=self.all_filter, width=26)
        self.all_filter_entry.grid(row=0, column=1, sticky="w", padx=(8, 20))

        tk.Label(ib, text="Region:", bg=C["card2"], fg=C["muted"], font=self.F_LABEL).grid(row=0, column=2, sticky="w")
        self.all_region_combo = ttk.Combobox(ib, textvariable=self.all_region,
                                             values=self.REGIONS_WITH_ALL, state="readonly", width=16)
        self.all_region_combo.grid(row=0, column=3, sticky="w", padx=(8, 20))

        tk.Label(ib, text="Sort:", bg=C["card2"], fg=C["muted"], font=self.F_LABEL).grid(row=0, column=4, sticky="w")
        self.all_sort_combo = ttk.Combobox(
            ib, textvariable=self.all_sort,
            values=["Name (A-Z)", "Name (Z-A)",
                    "Population (High-Low)", "Population (Low-High)",
                    "Area (High-Low)", "Area (Low-High)"],
            state="readonly", width=22)
        self.all_sort_combo.grid(row=0, column=5, sticky="w", padx=(8, 20))

        ttk.Button(ib, text="Refresh", style="Primary.TButton",
                   command=self.render_all_grid).grid(row=0, column=6)
        ttk.Button(ib, text="Clear", style="Ghost.TButton",
                   command=self._clear_all_filters).grid(row=0, column=7, padx=(10, 0))
        ib.grid_columnconfigure(8, weight=1)

        self.all_scroll = ScrollableFrame(wrap, bg=C["bg"])
        self.all_scroll.pack(fill="both", expand=True)

        self._all_filter_after: Optional[str] = None

        def on_change(*_):
            if self._all_filter_after:
                self.after_cancel(self._all_filter_after)
            self._all_filter_after = self.after(140, self.render_all_grid)

        self.all_filter.trace_add("write", on_change)
        self.all_region.trace_add("write", on_change)
        self.all_sort.trace_add("write", on_change)

    def _clear_all_filters(self):
        self.all_filter.set("")
        self.all_region.set("All")
        self.all_sort.set("Name (A-Z)")

    # ── COMPARE PAGE ───────────────────────────────────────────────────────────

    def _build_compare(self, parent: ttk.Frame):
        C = self.C
        tk.Frame(parent, bg=C["accent"], height=3).pack(fill="x")

        wrap = tk.Frame(parent, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=20, pady=16)

        hdr = tk.Frame(wrap, bg=C["bg"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="Compare Countries", bg=C["bg"], fg=C["text"], font=self.F_TITLE).pack(side="left")
        ttk.Button(hdr, text="<- Back to App", style="Ghost.TButton",
                   command=lambda: self._show_page("main")).pack(side="right")

        bar = tk.Frame(wrap, bg=C["card2"], highlightbackground=C["border"], highlightthickness=1)
        bar.pack(fill="x", pady=(14, 12))
        ib = tk.Frame(bar, bg=C["card2"])
        ib.pack(fill="x", padx=12, pady=10)

        tk.Label(ib, text="Country A:", bg=C["card2"], fg=C["muted"], font=self.F_H2).grid(row=0, column=0, sticky="w")
        self.compare_a_combo = ttk.Combobox(ib, textvariable=self.compare_a, values=[], width=30)
        self.compare_a_combo.grid(row=0, column=1, sticky="w", padx=(8, 20))

        tk.Label(ib, text="Country B:", bg=C["card2"], fg=C["muted"], font=self.F_H2).grid(row=0, column=2, sticky="w")
        self.compare_b_combo = ttk.Combobox(ib, textvariable=self.compare_b, values=[], width=30)
        self.compare_b_combo.grid(row=0, column=3, sticky="w", padx=(8, 20))

        ttk.Button(ib, text="Compare", style="Primary.TButton",
                   command=self.on_compare_page_compare).grid(row=0, column=4)
        ttk.Button(ib, text="Swap", style="Ghost.TButton",
                   command=self._compare_swap).grid(row=0, column=5, padx=(10, 0))
        ib.grid_columnconfigure(6, weight=1)

        flags = tk.Frame(wrap, bg=C["bg"])
        flags.pack(fill="x", pady=(0, 12))

        self.cmp_flagA_box = tk.Frame(flags, bg=C["bg3"], highlightbackground=C["border"], highlightthickness=1)
        self.cmp_flagA_box.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.cmp_flagA = tk.Label(self.cmp_flagA_box, text="Flag A", bg=C["bg3"], fg=C["muted"])
        self.cmp_flagA.pack(padx=10, pady=10)

        self.cmp_flagB_box = tk.Frame(flags, bg=C["bg3"], highlightbackground=C["border"], highlightthickness=1)
        self.cmp_flagB_box.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.cmp_flagB = tk.Label(self.cmp_flagB_box, text="Flag B", bg=C["bg3"], fg=C["muted"])
        self.cmp_flagB.pack(padx=10, pady=10)

        split = ttk.PanedWindow(wrap, orient="vertical")
        split.pack(fill="both", expand=True)

        top    = tk.Frame(split, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        bottom = tk.Frame(split, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        split.add(top, weight=3)
        split.add(bottom, weight=2)

        ti = tk.Frame(top, bg=C["card"])
        ti.pack(fill="both", expand=True, padx=12, pady=10)
        tk.Label(ti, text="Comparison Table", bg=C["card"], fg=C["accent_glow"], font=self.F_H2).pack(anchor="w")

        tv_wrap = tk.Frame(ti, bg=C["card"])
        tv_wrap.pack(fill="both", expand=True, pady=(8, 0))
        self.cmp_table = ttk.Treeview(tv_wrap, columns=("metric", "a", "b"), show="headings", height=10)
        self.cmp_table.heading("metric", text="Metric")
        self.cmp_table.heading("a", text="Country A")
        self.cmp_table.heading("b", text="Country B")
        self.cmp_table.column("metric", width=220, anchor="w")
        self.cmp_table.column("a", width=420, anchor="w")
        self.cmp_table.column("b", width=420, anchor="w")
        tv_sb = ttk.Scrollbar(tv_wrap, orient="vertical", command=self.cmp_table.yview)
        self.cmp_table.configure(yscrollcommand=tv_sb.set)
        self.cmp_table.pack(side="left", fill="both", expand=True)
        tv_sb.pack(side="right", fill="y")

        bi = tk.Frame(bottom, bg=C["card"])
        bi.pack(fill="both", expand=True, padx=12, pady=10)
        tk.Label(bi, text="Notes / Winners", bg=C["card"], fg=C["accent_glow"], font=self.F_H2).pack(anchor="w")

        note_wrap = tk.Frame(bi, bg=C["card"])
        note_wrap.pack(fill="both", expand=True, pady=(8, 0))
        note_sb = ttk.Scrollbar(note_wrap, orient="vertical")
        self.cmp_notes = tk.Text(
            note_wrap, wrap="word", bg=C["bg2"], fg=C["text"],
            insertbackground=C["accent"], highlightthickness=0, borderwidth=0,
            font=self.F_BODY, yscrollcommand=note_sb.set)
        note_sb.config(command=self.cmp_notes.yview)
        self.cmp_notes.pack(side="left", fill="both", expand=True)
        note_sb.pack(side="right", fill="y")
        self._cmp_set_notes("Pick Country A and Country B, then click Compare.\n")

        self.compare_a_combo.bind("<<ComboboxSelected>>", lambda _e: self._compare_update_flags_preview())
        self.compare_b_combo.bind("<<ComboboxSelected>>", lambda _e: self._compare_update_flags_preview())

    # ── MODE SWITCH ────────────────────────────────────────────────────────────

    def _hide_sections(self):
        for s in [self.section_name, self.section_capital, self.section_region]:
            s.pack_forget()

    def _switch_mode(self, mode: str):
        self.mode.set(mode)
        labels = {"name": "Search by Name", "capital": "Search by Capital", "region": "Filter by Region"}
        self.top_page.config(text=labels.get(mode, ""))
        self._hide_sections()
        if mode == "name":
            self.section_name.pack(fill="x")
            self.name_entry.focus_set()
        elif mode == "capital":
            self.section_capital.pack(fill="x")
            self.cap_entry.focus_set()
        elif mode == "region":
            self.section_region.pack(fill="x")
        self.set_status("Ready")

    # ── THREAD HELPERS ─────────────────────────────────────────────────────────

    def _run_fetch(self, label: str, fn, *args):
        def worker():
            try:
                data = fn(*args)
                self.after(0, lambda: self._fetch_ok(label, data))
            except Exception as e:
                self.after(0, lambda: self._fetch_err(label, str(e)))
        self.set_status(f"{label} • Loading...")
        self.progress.start(12)
        threading.Thread(target=worker, daemon=True).start()

    def _fetch_ok(self, label: str, data: List[Country]):
        self.progress.stop()
        if not data:
            self.current = []
            self.results_list.delete(0, tk.END)
            self._clear_details()
            self.set_status(f"{label} • No results")
            messagebox.showwarning("No Results", "No matching results were found.")
            return
        for c in data:
            self.country_lookup_cache[c.name_common.lower()] = c
        self.current = data
        self._refresh_results()
        self._clear_details()
        self.set_status(f"{label} • Loaded {len(data)}")
        if self.results_list.size() > 0:
            self.results_list.selection_set(0)
            self.results_list.event_generate("<<ListboxSelect>>")
        self._refresh_compare_choices()

    def _fetch_err(self, label: str, err: str):
        self.progress.stop()
        self.set_status(f"{label} • Error")
        messagebox.showerror("Error", f"{label} failed.\n\n{err}")

    # ── ACTIONS ────────────────────────────────────────────────────────────────

    def on_search_name(self):
        q = self.name_q.get().strip()
        if not q:
            messagebox.showerror("Input Required", "Please enter a country name.")
            return
        self._run_fetch("Search", self.api.get_by_name, q, self.exact_var.get())

    def on_search_capital(self):
        q = self.cap_q.get().strip()
        if not q:
            messagebox.showerror("Input Required", "Please enter a capital city.")
            return
        self._run_fetch("Capital", self.api.get_by_capital, q)

    def on_filter_region(self):
        region = self.region_var.get().strip()
        if not region:
            messagebox.showerror("Input Required", "Select a region.")
            return
        self._run_fetch("Region", self.api.get_by_region, region)

    # ── RESULTS + DETAILS ──────────────────────────────────────────────────────

    def _sorted_current(self) -> List[Country]:
        mode = self.sort_var.get()
        if mode == "Name (Z-A)":
            return sorted(self.current, key=lambda x: x.name_common.lower(), reverse=True)
        if mode == "Population":
            return sorted(self.current, key=lambda x: x.population, reverse=True)
        if mode == "Area":
            return sorted(self.current, key=lambda x: x.area, reverse=True)
        return sorted(self.current, key=lambda x: x.name_common.lower())

    def _refresh_results(self):
        self.results_list.delete(0, tk.END)
        for c in self._sorted_current():
            self.results_list.insert(tk.END, c.name_common)

    def _find_in_current(self, name: str) -> Optional[Country]:
        for c in self.current:
            if c.name_common == name:
                return c
        return None

    def on_select_country(self, _e):
        sel = self.results_list.curselection()
        if not sel:
            return
        c = self._find_in_current(self.results_list.get(sel[0]))
        if c:
            self._show_country(c)

    def _clear_details(self):
        self.flag_label.config(image="", text="(flag)")
        self._set_details_text("Select a country from the Results list to view details.")

    def _set_details_text(self, text: str):
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("end", text)
        self.detail_text.config(state="disabled")

    def _show_country(self, c: Country):
        details = (
            f"Name: {c.name_common}\n"
            f"Official: {c.name_official}\n"
            f"Capital: {c.capital}\n"
            f"Region / Subregion: {c.region} / {c.subregion}\n"
            f"Population: {c.population:,}\n"
            f"Area: {c.area:,.2f} km2\n"
        )
        details += f"Density: {(c.population / c.area):,.2f} per km2\n" if c.area > 0 else "Density: N/A\n"
        details += f"\nLanguages: {c.languages}\n\nCurrencies: {c.currencies}\n\nBorders: {c.borders}\n"
        self._set_details_text(details)
        self.set_status(f"Showing: {c.name_common}")
        if c.flag_url:
            self._load_flag(c.flag_url, self.flag_label, (320, 200))
        else:
            self.flag_label.config(image="", text="No flag")

    # ── FLAGS ──────────────────────────────────────────────────────────────────

    def _load_flag(self, url: str, label: tk.Label, size: Tuple[int, int]):
        key = f"{url}|{size[0]}x{size[1]}"
        if key in self.flag_cache:
            photo = self.flag_cache[key]
            label.config(image=photo, text="")
            label.image = photo
            return
        label.config(image="", text="Loading...")

        def worker():
            try:
                if requests is not None:
                    resp = requests.get(url, timeout=12, headers={"User-Agent": "CountryExplorer/1.0"})
                    resp.raise_for_status()
                    data = resp.content
                else:
                    req = urllib.request.Request(url, headers={"User-Agent": "CountryExplorer/1.0"})
                    with urllib.request.urlopen(req, timeout=12) as r:
                        data = r.read()
                img = Image.open(io.BytesIO(data))
                img.thumbnail(size)
                photo = ImageTk.PhotoImage(img)
                def apply():
                    self.flag_cache[key] = photo
                    label.config(image=photo, text="")
                    label.image = photo
                self.after(0, apply)
            except Exception:
                self.after(0, lambda: label.config(image="", text="No flag"))

        threading.Thread(target=worker, daemon=True).start()

    # ── ALL COUNTRIES ──────────────────────────────────────────────────────────

    def open_all_countries(self):
        if self.all_countries:
            self._show_page("all")
            self.all_filter_entry.focus_set()
            self.render_all_grid()
            return

        def worker():
            try:
                data = self.api.get_all()
                self.after(0, lambda: self._all_ok(data))
            except Exception as e:
                self.after(0, lambda: self._all_err(str(e)))

        self.set_status("All Countries • Loading...")
        self.progress.start(12)
        threading.Thread(target=worker, daemon=True).start()

    def _all_ok(self, data: List[Country]):
        self.progress.stop()
        self.all_countries = sorted(data, key=lambda c: c.name_common.lower())
        for c in self.all_countries:
            self.country_lookup_cache[c.name_common.lower()] = c
        self._refresh_compare_choices()
        self.set_status(f"All Countries • Loaded {len(self.all_countries)}")
        self._show_page("all")
        self.render_all_grid()

    def _all_err(self, err: str):
        self.progress.stop()
        self.set_status("All Countries • Error")
        messagebox.showerror("Error", f"Failed to load all countries.\n\n{err}")

    def _apply_all_filters_and_sort(self) -> List[Country]:
        data = list(self.all_countries)
        q = self.all_filter.get().strip().lower()
        if q:
            data = [c for c in data if q in c.name_common.lower()]
        r = self.all_region.get().strip()
        if r and r != "All":
            data = [c for c in data if (c.region or "").strip().lower() == r.lower()]
        s = self.all_sort.get()
        if "Z-A" in s or "Z-Z" in s:
            data.sort(key=lambda c: c.name_common.lower(), reverse=True)
        elif "Population (High" in s:
            data.sort(key=lambda c: c.population, reverse=True)
        elif "Population (Low" in s:
            data.sort(key=lambda c: c.population)
        elif "Area (High" in s:
            data.sort(key=lambda c: c.area, reverse=True)
        elif "Area (Low" in s:
            data.sort(key=lambda c: c.area)
        else:
            data.sort(key=lambda c: c.name_common.lower())
        return data

    def render_all_grid(self):
        if not hasattr(self, "all_scroll"):
            return
        for w in self.all_scroll.inner.winfo_children():
            w.destroy()
        data = self._apply_all_filters_and_sort()
        parent_w = max(self.all_scroll.winfo_width(), 1100)
        tile_w = 280
        cols = max(2, min(6, parent_w // tile_w))
        for i, c in enumerate(data, start=1):
            r = (i - 1) // cols
            col = (i - 1) % cols
            tile = self._country_tile(self.all_scroll.inner, c, rank=i)
            tile.grid(row=r, column=col, padx=10, pady=10, sticky="nsew")
        for col in range(cols):
            self.all_scroll.inner.grid_columnconfigure(col, weight=1)

    def _country_tile(self, parent: tk.Frame, c: Country, rank: int) -> tk.Frame:
        C = self.C
        tile = tk.Frame(parent, bg=C["card2"], highlightbackground=C["border"], highlightthickness=1)
        tile.configure(cursor="hand2")

        top = tk.Frame(tile, bg=C["card2"])
        top.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(top, text=f"#{rank}", bg=C["card2"], fg=C["accent"], font=self.F_H2).pack(side="left")

        flag_lbl = tk.Label(tile, text="Loading...", bg=C["bg3"], fg=C["muted"])
        flag_lbl.pack(padx=10, pady=(6, 6), fill="x")

        name_lbl = tk.Label(tile, text=c.name_common, bg=C["card2"], fg=C["text"],
                            font=self.F_H2, wraplength=240, justify="center")
        name_lbl.pack(padx=10, pady=(0, 4))

        mini = tk.Label(tile, text=f"Pop: {c.population:,}  |  {c.area:,.0f} km2",
                        bg=C["card2"], fg=C["muted"], font=self.F_LABEL)
        mini.pack(padx=10, pady=(0, 10))

        def on_click(_e=None):
            self._show_page("main")
            self.current = [c]
            self._refresh_results()
            if self.results_list.size() > 0:
                self.results_list.selection_set(0)
            self._show_country(c)
            self.set_status(f"Selected: {c.name_common}")
            self._send_country_to_compare(c)

        for w in (tile, flag_lbl, name_lbl, mini, top):
            w.bind("<Button-1>", on_click)

        if c.flag_url:
            self._load_flag(c.flag_url, flag_lbl, (190, 125))
        else:
            flag_lbl.config(text="No flag")

        return tile

    # ── COMPARE PAGE LOGIC ─────────────────────────────────────────────────────

    def open_compare_page(self):
        self._refresh_compare_choices()
        self._compare_update_flags_preview()
        self._show_page("compare")

    def _refresh_compare_choices(self):
        names = [c.name_common for c in self.all_countries] if self.all_countries \
            else [c.name_common for c in self.current]
        if hasattr(self, "compare_a_combo") and hasattr(self, "compare_b_combo"):
            self.compare_a_combo["values"] = names
            self.compare_b_combo["values"] = names
        if names and not self.compare_a.get():
            self.compare_a.set(names[0])
        if len(names) > 1 and (not self.compare_b.get() or self.compare_b.get() == names[0]):
            self.compare_b.set(names[1])

    def _compare_swap(self):
        a, b = self.compare_a.get(), self.compare_b.get()
        self.compare_a.set(b)
        self.compare_b.set(a)
        self._compare_update_flags_preview()

    def _get_country_by_name_anywhere(self, name: str) -> Optional[Country]:
        if not name:
            return None
        n = name.strip().lower()
        if n in self.country_lookup_cache:
            return self.country_lookup_cache[n]
        for c in self.current:
            if c.name_common.lower() == n:
                self.country_lookup_cache[n] = c
                return c
        return None

    def _compare_update_flags_preview(self):
        a, b = self.compare_a.get().strip(), self.compare_b.get().strip()
        self.cmp_flagA.config(image="", text="Flag A")
        self.cmp_flagB.config(image="", text="Flag B")
        ca = self._get_country_by_name_anywhere(a)
        cb = self._get_country_by_name_anywhere(b)
        if ca and ca.flag_url:
            self._load_flag(ca.flag_url, self.cmp_flagA, (260, 170))
        if cb and cb.flag_url:
            self._load_flag(cb.flag_url, self.cmp_flagB, (260, 170))

    def on_compare_page_compare(self):
        a, b = self.compare_a.get().strip(), self.compare_b.get().strip()
        if not a or not b:
            messagebox.showerror("Selection Required", "Pick two countries.")
            return
        if a == b:
            messagebox.showerror("Invalid", "Pick two different countries.")
            return
        self._cmp_set_notes("Comparing... please wait.\n")
        self._cmp_clear_table()

        def worker():
            try:
                ca = self._get_country_by_name_anywhere(a)
                cb = self._get_country_by_name_anywhere(b)
                if ca is None:
                    res = self.api.get_by_name(a, True) or self.api.get_by_name(a, False)
                    ca = res[0] if res else None
                if cb is None:
                    res = self.api.get_by_name(b, True) or self.api.get_by_name(b, False)
                    cb = res[0] if res else None
                if ca is None or cb is None:
                    raise RuntimeError("Could not find one or both countries.")
                self.country_lookup_cache[ca.name_common.lower()] = ca
                self.country_lookup_cache[cb.name_common.lower()] = cb
                self.after(0, lambda: self._compare_render(ca, cb))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Compare Error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _cmp_clear_table(self):
        if hasattr(self, "cmp_table"):
            for row in self.cmp_table.get_children():
                self.cmp_table.delete(row)

    def _cmp_set_notes(self, text: str):
        if not hasattr(self, "cmp_notes"):
            return
        self.cmp_notes.config(state="normal")
        self.cmp_notes.delete("1.0", tk.END)
        self.cmp_notes.insert("end", text)
        self.cmp_notes.config(state="disabled")

    def _compare_render(self, ca: Country, cb: Country):
        self.cmp_flagA.config(image="", text="Flag A")
        self.cmp_flagB.config(image="", text="Flag B")
        if ca.flag_url:
            self._load_flag(ca.flag_url, self.cmp_flagA, (260, 170))
        if cb.flag_url:
            self._load_flag(cb.flag_url, self.cmp_flagB, (260, 170))

        rows = [
            ("Name",         ca.name_common,      cb.name_common),
            ("Official",     ca.name_official,     cb.name_official),
            ("Capital",      ca.capital,           cb.capital),
            ("Region",       ca.region,            cb.region),
            ("Subregion",    ca.subregion,         cb.subregion),
            ("Population",   f"{ca.population:,}", f"{cb.population:,}"),
            ("Area (km2)",   f"{ca.area:,.2f}",    f"{cb.area:,.2f}"),
            ("Density/km2",  self._fmt_density(ca),self._fmt_density(cb)),
            ("Languages",    ca.languages,         cb.languages),
            ("Currencies",   ca.currencies,        cb.currencies),
            ("Borders",      ca.borders,           cb.borders),
        ]
        self._cmp_clear_table()
        for metric, a_val, b_val in rows:
            self.cmp_table.insert("", "end", values=(metric, a_val, b_val))

        notes = [
            f"{ca.name_common}  vs  {cb.name_common}\n",
            "-" * 60 + "\n",
            self._winner_line("Population", ca.name_common, ca.population, cb.name_common, cb.population),
            self._winner_line("Area",       ca.name_common, ca.area,       cb.name_common, cb.area),
            self._winner_line("Density",    ca.name_common, self._density_num(ca), cb.name_common, self._density_num(cb)),
            "\nTip: Use All Countries page to pick any country quickly.\n",
        ]
        self._cmp_set_notes("".join(notes))
        self.set_status("Compare • Done")

    def _density_num(self, c: Country) -> float:
        return c.population / c.area if c.area and c.area > 0 else 0.0

    def _fmt_density(self, c: Country) -> str:
        return f"{(c.population / c.area):,.2f}" if c.area and c.area > 0 else "N/A"

    def _winner_line(self, label: str, an: str, av: float, bn: str, bv: float) -> str:
        if av > bv:
            return f"Winner ({label}): {an}\n"
        if bv > av:
            return f"Winner ({label}): {bn}\n"
        return f"Winner ({label}): TIE\n"

    def _send_selected_to_compare(self):
        sel = self.results_list.curselection()
        if not sel:
            return
        c = self._find_in_current(self.results_list.get(sel[0]))
        if c:
            self._send_country_to_compare(c)
            self.open_compare_page()

    def _send_country_to_compare(self, c: Country):
        if not self.compare_a.get():
            self.compare_a.set(c.name_common)
        elif not self.compare_b.get():
            self.compare_b.set(c.name_common)
        else:
            self.compare_b.set(c.name_common)
        self._refresh_compare_choices()

    # ── UTILITY ────────────────────────────────────────────────────────────────

    def clear_all(self):
        self.name_q.set("")
        self.cap_q.set("")
        self.exact_var.set(False)
        self.current = []
        self.results_list.delete(0, tk.END)
        self._clear_details()
        self.compare_a.set("")
        self.compare_b.set("")
        self._cmp_set_notes("Pick Country A and Country B, then click Compare.\n")
        self._cmp_clear_table()
        self.set_status("Ready")

    def set_status(self, text: str):
        self.status_var.set(text)

    def _on_enter(self, _e):
        if not self.pages["main"].winfo_ismapped():
            return
        mode = self.mode.get()
        if mode == "name":
            self.on_search_name()
        elif mode == "capital":
            self.on_search_capital()
        elif mode == "region":
            self.on_filter_region()


if __name__ == "__main__":
    app = CountryExplorerApp()
    app.mainloop()