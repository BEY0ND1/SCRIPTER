"""
SCRIPTER — a Final Draft–style screenwriting program in pure Python/tkinter.
Free & open source. Donations: https://ko-fi.com/beyondak (♥ Donate button).

HOW TO RUN IN IDLE:
  1. Open IDLE
  2. File > Open... > choose this file (scripter.py)
  3. Press F5 (Run > Run Module)

No installs needed — uses only the Python standard library.

THE FINAL DRAFT WORKFLOW:
  Enter        -> next logical element (Scene Heading -> Action, Character -> Dialogue,
                  Dialogue -> Character ...)
  Tab          -> on an empty line: cycle the element type
                  on a line with text: jump (Action -> Character, Dialogue -> Parenthetical ...)
  Shift+Tab    -> cycle element type backwards
  Ctrl+1..7    -> set element directly (Scene, Action, Character, Parenthetical,
                  Dialogue, Transition, Shot)   [Cmd on macOS]
  Backspace at line start -> merge with the line above
  SmartType    -> as you type, suggestions appear for INT./EXT., known character
                  names, known locations, times of day, and transitions.
                  Up/Down to choose, Enter to accept, Esc to dismiss.

Files:  saves to .screenplay (JSON), opens .screenplay and Final Draft .fdx,
        exports .fdx (opens in real Final Draft) and formatted .txt.
"""

import json
import math
import re
import webbrowser
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont

# ─────────────────────────────────────────────── support the project ──
# Scripter is free, open-source software. If you publish or fork it,
# paste YOUR donation page below — Ko-fi, GitHub Sponsors, Buy Me a
# Coffee, PayPal.me, Liberapay ... any URL works. The "♥ Donate" button
# and Help menu will open it in the user's browser.
DONATION_URL = "https://ko-fi.com/beyondak"
PROJECT_URL = ""         # e.g. "https://github.com/yourname/scripter"

# ---------------------------------------------------------------- layout maths
DPI = 96                       # screen pixels per "inch" of page


def IN(inches):
    return int(round(inches * DPI))


PAGE_W = IN(8.5)               # US Letter
LEFT_MARGIN = IN(1.5)          # industry standard 1.5" left
RIGHT_MARGIN = IN(1.0)
LINES_PER_PAGE = 55            # the classic "one page ≈ one minute"

TYPES = ["scene", "action", "character", "parenthetical",
         "dialogue", "transition", "shot"]

# label, extra left indent (in), printable width (in), uppercase?,
# chars-per-line for pagination, blank lines before, right-aligned?
META = {
    "scene":         dict(label="Scene Heading", indent=0.0, width=6.0,
                          upper=True,  cpl=60, before=2, right=False),
    "action":        dict(label="Action",        indent=0.0, width=6.0,
                          upper=False, cpl=60, before=1, right=False),
    "character":     dict(label="Character",     indent=2.2, width=3.3,
                          upper=True,  cpl=33, before=1, right=False),
    "parenthetical": dict(label="Parenthetical", indent=1.6, width=2.0,
                          upper=False, cpl=19, before=0, right=False),
    "dialogue":      dict(label="Dialogue",      indent=1.0, width=3.5,
                          upper=False, cpl=35, before=0, right=False),
    "transition":    dict(label="Transition",    indent=0.0, width=6.0,
                          upper=True,  cpl=60, before=1, right=True),
    "shot":          dict(label="Shot",          indent=0.0, width=6.0,
                          upper=True,  cpl=60, before=1, right=False),
}

# Final Draft's default element flow
ENTER_NEXT = {"scene": "action", "action": "action", "character": "dialogue",
              "parenthetical": "dialogue", "dialogue": "character",
              "transition": "scene", "shot": "action"}

TAB_NEXT = {"scene": "action", "action": "character", "character": "transition",
            "parenthetical": "dialogue", "dialogue": "parenthetical",
            "transition": "scene", "shot": "action"}

TAB_CYCLE = {"scene": "action", "action": "character", "character": "transition",
             "transition": "scene", "parenthetical": "dialogue",
             "dialogue": "parenthetical", "shot": "scene"}
CYCLE_BACK = {v: k for k, v in TAB_CYCLE.items()}

SCENE_PREFIXES = ["INT. ", "EXT. ", "INT./EXT. ", "I/E. "]
TIMES_OF_DAY = ["DAY", "NIGHT", "MORNING", "EVENING", "AFTERNOON", "DAWN",
                "DUSK", "CONTINUOUS", "LATER", "MOMENTS LATER", "SAME"]
TRANSITIONS = ["CUT TO:", "DISSOLVE TO:", "SMASH CUT TO:", "MATCH CUT TO:",
               "FADE IN:", "FADE OUT.", "FADE TO BLACK.", "JUMP CUT TO:",
               "WIPE TO:", "INTERCUT WITH:"]

FDX_NAME = {"scene": "Scene Heading", "action": "Action",
            "character": "Character", "parenthetical": "Parenthetical",
            "dialogue": "Dialogue", "transition": "Transition", "shot": "Shot"}
FDX_BACK = {v: k for k, v in FDX_NAME.items()}

STARTER = [
    ("scene", "INT. WRITER'S ROOM - NIGHT"),
    ("action", "A blank page glows on a screen. A cursor blinks, patient "
               "and merciless. Somewhere, coffee goes cold."),
    ("character", "WRITER"),
    ("parenthetical", "(to no one)"),
    ("dialogue", "Okay. Page one."),
    ("transition", "CUT TO:"),
]

# theme
BG = "#2B2E33"; CHROME = "#1F2126"; PANEL = "#24262B"
EDGE = "#3a3d44"; INK = "#F0EDE6"; DIM = "#8a8f98"; ACCENT = "#C8442D"
PAPER = "#FDFCF8"; TEXT_INK = "#1a1a1a"


# ================================================================= application
class Scripter(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Scripter")
        self.configure(bg=BG)
        self.geometry("1280x860")
        self.minsize(900, 600)

        self.doc_title = "UNTITLED SCREENPLAY"
        self.author = "Your Name"
        self.path = None
        self.dirty = False
        self.types = []            # element type of each line (index = line-1)
        self._combo_guard = False
        self._popup = None         # SmartType window
        self._popup_items = []
        self._popup_sel = 0
        self._rebuild_job = None

        self._build_fonts()
        self._build_menu()
        self._build_ui()
        self._configure_tags()
        self._bind_keys()

        self.load_elements(STARTER)
        self.set_dirty(False)
        self.text.focus_set()
        self.protocol("WM_DELETE_WINDOW", self.on_quit)

    # ------------------------------------------------------------- fonts / ui
    def _build_fonts(self):
        fams = set(tkfont.families())
        family = next((f for f in ("Courier Prime", "Courier New", "Courier")
                       if f in fams), "Courier")
        self.mono = tkfont.Font(family=family, size=12)
        self.mono_b = tkfont.Font(family=family, size=12, weight="bold")
        self.line_h = self.mono.metrics("linespace")
        ui_family = next((f for f in ("Segoe UI", "Helvetica Neue", "Helvetica",
                                      "Arial") if f in fams), "TkDefaultFont")
        self.ui = tkfont.Font(family=ui_family, size=10)
        self.ui_small = tkfont.Font(family=ui_family, size=9)

    def _build_menu(self):
        m = tk.Menu(self)
        accel = "Cmd" if self.tk.call("tk", "windowingsystem") == "aqua" else "Ctrl"

        fm = tk.Menu(m, tearoff=0)
        fm.add_command(label="New", accelerator=f"{accel}+N", command=self.on_new)
        fm.add_command(label="Open…  (.screenplay / .fdx)",
                       accelerator=f"{accel}+O", command=self.on_open)
        fm.add_separator()
        fm.add_command(label="Save", accelerator=f"{accel}+S", command=self.on_save)
        fm.add_command(label="Save As…", command=lambda: self.on_save(save_as=True))
        fm.add_separator()
        fm.add_command(label="Title Page…", command=self.edit_title_page)
        fm.add_separator()
        fm.add_command(label="Export Final Draft (.fdx)…", command=self.export_fdx)
        fm.add_command(label="Export formatted text (.txt)…", command=self.export_txt)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.on_quit)
        m.add_cascade(label="File", menu=fm)

        em = tk.Menu(m, tearoff=0)
        em.add_command(label="Undo", accelerator=f"{accel}+Z",
                       command=lambda: self._safe_edit("undo"))
        em.add_command(label="Redo", accelerator=f"{accel}+Y",
                       command=lambda: self._safe_edit("redo"))
        m.add_cascade(label="Edit", menu=em)

        tm = tk.Menu(m, tearoff=0)
        for i, t in enumerate(TYPES, 1):
            tm.add_command(label=META[t]["label"], accelerator=f"{accel}+{i}",
                           command=lambda tt=t: self.set_line_type(self.cur_line(), tt))
        m.add_cascade(label="Element", menu=tm)

        hm = tk.Menu(m, tearoff=0)
        hm.add_command(label="Keyboard shortcuts", accelerator="F1",
                       command=self.show_help)
        hm.add_separator()
        hm.add_command(label="Support Scripter  ♥", command=self.show_donate)
        hm.add_command(label="Project page / source code",
                       command=self.open_project_page)
        hm.add_separator()
        hm.add_command(label="About Scripter", command=self.show_about)
        m.add_cascade(label="Help", menu=hm)
        self.config(menu=m)

    def _build_ui(self):
        # toolbar -------------------------------------------------------------
        bar = tk.Frame(self, bg=CHROME, height=42)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        logo = tk.Label(bar, text=" S ", bg=ACCENT, fg="white",
                        font=self.mono_b)
        logo.pack(side="left", padx=(10, 6), pady=8)
        self.title_var = tk.StringVar(value=self.doc_title)
        title_entry = tk.Entry(bar, textvariable=self.title_var, bg=CHROME,
                               fg=INK, insertbackground=INK, relief="flat",
                               font=self.ui, width=28)
        title_entry.pack(side="left", pady=8)
        self.title_var.trace_add("write", self._title_changed)

        tk.Label(bar, text="Element:", bg=CHROME, fg=DIM,
                 font=self.ui_small).pack(side="left", padx=(18, 4))
        self.combo_var = tk.StringVar()
        self.combo = ttk.Combobox(bar, textvariable=self.combo_var, width=16,
                                  state="readonly",
                                  values=[META[t]["label"] for t in TYPES])
        self.combo.pack(side="left", pady=8)
        self.combo.bind("<<ComboboxSelected>>", self._combo_changed)

        donate = tk.Label(bar, text="♥ Donate", bg=CHROME, fg=ACCENT,
                          cursor="hand2", font=self.ui)
        donate.pack(side="right", padx=(4, 12))
        donate.bind("<Button-1>", lambda e: self.show_donate())
        donate.bind("<Enter>", lambda e: donate.config(fg="#E06A52"))
        donate.bind("<Leave>", lambda e: donate.config(fg=ACCENT))

        self.stats_lbl = tk.Label(bar, text="", bg=CHROME, fg=DIM,
                                  font=self.ui_small)
        self.stats_lbl.pack(side="right", padx=12)

        # body ---------------------------------------------------------------
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # scene navigator
        nav = tk.Frame(body, bg=PANEL, width=240)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        tk.Label(nav, text="SCENES", bg=PANEL, fg=DIM, anchor="w",
                 font=self.ui_small).pack(fill="x", padx=12, pady=(12, 4))
        self.scene_list = tk.Listbox(nav, bg=PANEL, fg="#b9bdc4", bd=0,
                                     highlightthickness=0, activestyle="none",
                                     selectbackground="#3a3e46",
                                     selectforeground=INK, font=self.ui_small)
        self.scene_list.pack(fill="both", expand=True, padx=4, pady=(0, 8))
        self.scene_list.bind("<<ListboxSelect>>", self._scene_clicked)
        self.scene_lines = []

        # the page
        page_holder = tk.Frame(body, bg=BG)
        page_holder.pack(side="left", fill="both", expand=True)

        canvas_pad = tk.Frame(page_holder, bg=BG)
        canvas_pad.pack(fill="both", expand=True)

        self.page = tk.Frame(canvas_pad, bg=PAPER, width=PAGE_W,
                             highlightthickness=1, highlightbackground="#111")
        self.page.pack(side="top", fill="y", expand=True, pady=14)
        self.page.pack_propagate(False)

        sb = tk.Scrollbar(self.page, orient="vertical")
        sb.pack(side="right", fill="y")
        self.text = tk.Text(self.page, wrap="word", undo=True,
                            autoseparators=True, maxundo=-1,
                            bg=PAPER, fg=TEXT_INK, insertbackground=TEXT_INK,
                            bd=0, highlightthickness=0, font=self.mono,
                            padx=0, pady=IN(1.0),
                            yscrollcommand=sb.set)
        self.text.pack(fill="both", expand=True)
        sb.config(command=self.text.yview)

        # status bar ----------------------------------------------------------
        status = tk.Frame(self, bg=CHROME, height=26)
        status.pack(side="bottom", fill="x")
        status.pack_propagate(False)
        self.status_lbl = tk.Label(
            status, bg=CHROME, fg=DIM, font=self.ui_small,
            text="Tab changes element · Enter advances · "
                 f"{'Cmd' if self.tk.call('tk','windowingsystem')=='aqua' else 'Ctrl'}"
                 "+1–7 sets type · F1 for all shortcuts")
        self.status_lbl.pack(side="left", padx=12)
        self.page_lbl = tk.Label(status, bg=CHROME, fg=INK, font=self.ui_small)
        self.page_lbl.pack(side="right", padx=12)

    def _configure_tags(self):
        for t, m in META.items():
            lm = LEFT_MARGIN + IN(m["indent"])
            rm = PAGE_W - lm - IN(m["width"])
            rm = max(rm, RIGHT_MARGIN)
            self.text.tag_configure(
                t, lmargin1=lm, lmargin2=lm, rmargin=rm,
                spacing1=m["before"] * self.line_h,
                justify="right" if m["right"] else "left")

    # ------------------------------------------------------------ keybindings
    def _bind_keys(self):
        t = self.text
        t.bind("<Return>", self.on_return)
        t.bind("<KP_Enter>", self.on_return)
        t.bind("<Tab>", lambda e: self.on_tab(False))
        t.bind("<Shift-Tab>", lambda e: self.on_tab(True))
        try:
            t.bind("<ISO_Left_Tab>", lambda e: self.on_tab(True))  # linux
        except tk.TclError:
            pass
        t.bind("<BackSpace>", self.on_backspace)
        t.bind("<Delete>", self.on_delete)
        t.bind("<KeyRelease>", self.on_key_release)
        t.bind("<ButtonRelease-1>", lambda e: (self.hide_popup(),
                                               self.refresh_chrome()))
        t.bind("<Down>", self.on_arrow_down)
        t.bind("<Up>", self.on_arrow_up)
        t.bind("<Escape>", lambda e: self.hide_popup())

        for mod in ("Control", "Command"):
            for i, ty in enumerate(TYPES, 1):
                try:
                    self.bind_all(f"<{mod}-Key-{i}>",
                                  lambda e, tt=ty: (self.set_line_type(
                                      self.cur_line(), tt), "break")[1])
                except tk.TclError:
                    pass
            try:
                self.bind_all(f"<{mod}-s>", lambda e: (self.on_save(), "break")[1])
                self.bind_all(f"<{mod}-o>", lambda e: (self.on_open(), "break")[1])
                self.bind_all(f"<{mod}-n>", lambda e: (self.on_new(), "break")[1])
            except tk.TclError:
                pass
        self.bind_all("<F1>", lambda e: self.show_help())

    # ------------------------------------------------------------- primitives
    def cur_line(self):
        return int(self.text.index("insert").split(".")[0])

    def n_lines(self):
        return int(self.text.index("end-1c").split(".")[0])

    def line_text(self, n):
        return self.text.get(f"{n}.0", f"{n}.end")

    def sync_types(self):
        n = self.n_lines()
        while len(self.types) < n:
            self.types.append("action")
        del self.types[n:]

    def retag(self, n):
        if n < 1 or n > self.n_lines():
            return
        self.sync_types()
        for t in TYPES:
            self.text.tag_remove(t, f"{n}.0", f"{n}.end+1c")
        self.text.tag_add(self.types[n - 1], f"{n}.0", f"{n}.end+1c")

    def retag_all(self):
        self.sync_types()
        for t in TYPES:
            self.text.tag_remove(t, "1.0", "end")
        for n in range(1, self.n_lines() + 1):
            self.text.tag_add(self.types[n - 1], f"{n}.0", f"{n}.end+1c")

    def replace_line(self, n, new_text, keep_col=True):
        col = int(self.text.index("insert").split(".")[1]) if keep_col else None
        self.text.delete(f"{n}.0", f"{n}.end")
        self.text.insert(f"{n}.0", new_text)
        if col is not None:
            col = min(col, len(new_text))
            self.text.mark_set("insert", f"{n}.{col}")
        self.retag(n)

    # ---------------------------------------------------------- element logic
    def set_line_type(self, n, new_type):
        self.sync_types()
        if n < 1 or n > len(self.types):
            return
        old = self.types[n - 1]
        txt = self.line_text(n)
        if old == "parenthetical" and new_type != "parenthetical":
            txt = txt.strip()
            if txt.startswith("(") and txt.endswith(")"):
                txt = txt[1:-1]
        if new_type == "parenthetical":
            core = txt.strip().strip("()")
            txt = f"({core})" if core else "()"
        if META[new_type]["upper"]:
            txt = txt.upper()
        self.types[n - 1] = new_type
        self.replace_line(n, txt)
        if new_type == "parenthetical" and txt == "()":
            self.text.mark_set("insert", f"{n}.1")
        self.hide_popup()
        self.refresh_chrome()
        self.set_dirty(True)

    def new_line_after(self, n, new_type):
        self.text.mark_set("insert", f"{n}.end")
        self.text.insert("insert", "\n")
        self.types.insert(n, new_type)          # entry for line n+1
        if new_type == "parenthetical":
            self.text.insert("insert", "()")
            self.text.mark_set("insert", f"{n + 1}.1")
        self.retag(n)
        self.retag(n + 1)
        self.text.see("insert")
        self.hide_popup()
        self.refresh_chrome()
        self.set_dirty(True)

    # ----------------------------------------------------------- key handlers
    def on_return(self, event=None):
        if self._popup:
            self.accept_suggestion()
            return "break"
        self.sync_types()
        n = self.cur_line()
        t = self.types[n - 1]
        at_end = self.text.compare("insert", "==", f"{n}.end")
        if at_end:
            self.new_line_after(n, ENTER_NEXT[t])
        else:                                   # split: tail keeps same type
            self.text.insert("insert", "\n")
            self.types.insert(n, t)
            self.retag(n)
            self.retag(n + 1)
            self.set_dirty(True)
        return "break"

    def on_tab(self, shift):
        if self._popup:
            self.accept_suggestion()
            return "break"
        self.sync_types()
        n = self.cur_line()
        t = self.types[n - 1]
        stripped = self.line_text(n).strip()
        if stripped in ("", "()"):
            nxt = CYCLE_BACK.get(t, t) if shift else TAB_CYCLE[t]
            self.set_line_type(n, nxt)
        else:
            self.new_line_after(n, TAB_NEXT[t])
        return "break"

    def on_backspace(self, event=None):
        n = self.cur_line()
        at_start = self.text.compare("insert", "==", f"{n}.0")
        sel = self.text.tag_ranges("sel")
        if at_start and not sel and n > 1:
            self.sync_types()
            join_at = self.text.index(f"{n - 1}.end")
            self.text.delete(f"{n - 1}.end")    # remove the newline
            self.types.pop(n - 1)               # drop merged line's entry
            self.text.mark_set("insert", join_at)
            self.retag(n - 1)
            self.refresh_chrome()
            self.set_dirty(True)
            return "break"
        return None                              # default behaviour

    def on_delete(self, event=None):
        n = self.cur_line()
        at_end = self.text.compare("insert", "==", f"{n}.end")
        sel = self.text.tag_ranges("sel")
        if at_end and not sel and n < self.n_lines():
            self.sync_types()
            self.text.delete("insert")           # the newline
            self.types.pop(n)                    # line n+1's entry
            self.retag(n)
            self.refresh_chrome()
            self.set_dirty(True)
            return "break"
        return None

    def on_arrow_down(self, event=None):
        if self._popup:
            self._popup_sel = (self._popup_sel + 1) % len(self._popup_items)
            self._popup_paint()
            return "break"
        return None

    def on_arrow_up(self, event=None):
        if self._popup:
            self._popup_sel = (self._popup_sel - 1) % len(self._popup_items)
            self._popup_paint()
            return "break"
        return None

    def on_key_release(self, event=None):
        if event and event.keysym in ("Up", "Down", "Left", "Right", "Return",
                                      "Tab", "Escape", "Shift_L", "Shift_R",
                                      "Control_L", "Control_R", "Alt_L",
                                      "Alt_R", "Meta_L", "Meta_R"):
            self.refresh_chrome()
            return
        self.sync_types()
        n = self.cur_line()
        t = self.types[n - 1]
        txt = self.line_text(n)
        if META[t]["upper"] and txt != txt.upper():
            self.replace_line(n, txt.upper())
            txt = txt.upper()
        else:
            self.retag(n)
        if event and len(event.char) == 1 or (event and event.keysym
                                              in ("BackSpace", "Delete")):
            self.set_dirty(True)
        self.update_smarttype(n, t, txt)
        self.refresh_chrome()

    # -------------------------------------------------------------- SmartType
    def known_characters(self):
        out, seen = [], set()
        for i, t in enumerate(self.types):
            if t == "character":
                name = re.sub(r"\s*\(.*\)\s*$", "", self.line_text(i + 1)).strip()
                if name and name not in seen:
                    seen.add(name)
                    out.append(name)
        return out

    def known_locations(self):
        out, seen = [], set()
        for i, t in enumerate(self.types):
            if t == "scene":
                m = re.match(r"^(INT\.|EXT\.|INT\./EXT\.|I/E\.)\s*(.+?)"
                             r"(\s*-\s*.*)?$", self.line_text(i + 1), re.I)
                if m and m.group(2):
                    loc = m.group(2).strip()
                    if loc and loc not in seen:
                        seen.add(loc)
                        out.append(loc)
        return out

    def update_smarttype(self, n, t, txt):
        items = []
        if t == "character":
            q = txt.strip().upper()
            items = [c for c in self.known_characters()
                     if c.startswith(q) and c != q]
        elif t == "scene":
            up = txt.upper()
            if not any(up.startswith(p.strip()) for p in SCENE_PREFIXES):
                items = [p for p in SCENE_PREFIXES if p.startswith(up)]
            elif re.search(r"-\s*[A-Z ]*$", up):
                after = up.split("-")[-1].strip()
                items = [re.sub(r"-\s*[A-Z ]*$", "- " + d, up)
                         for d in TIMES_OF_DAY
                         if d.startswith(after) and d != after]
            else:
                prefix = next((p for p in SCENE_PREFIXES if up.startswith(p)), "")
                loc = up[len(prefix):]
                if loc:
                    items = [prefix + L.upper() + " - "
                             for L in self.known_locations()
                             if L.upper().startswith(loc) and L.upper() != loc]
        elif t == "transition":
            q = txt.strip().upper()
            items = [tr for tr in TRANSITIONS if tr.startswith(q) and tr != q]
        items = items[:6]
        if items:
            self.show_popup(items)
        else:
            self.hide_popup()

    def show_popup(self, items):
        self._popup_items = items
        self._popup_sel = 0
        if self._popup is None:
            self._popup = tk.Toplevel(self)
            self._popup.overrideredirect(True)
            self._popup.attributes("-topmost", True)
            self._lb = tk.Listbox(self._popup, bg=CHROME, fg="#b9bdc4",
                                  selectbackground=ACCENT,
                                  selectforeground="white", bd=1,
                                  relief="solid", highlightthickness=0,
                                  font=self.mono, activestyle="none")
            self._lb.pack()
            self._lb.bind("<ButtonRelease-1>", lambda e: self.accept_suggestion())
        bbox = self.text.bbox("insert")
        if bbox:
            x = self.text.winfo_rootx() + bbox[0]
            y = self.text.winfo_rooty() + bbox[1] + bbox[3] + 2
        else:
            x = self.text.winfo_rootx() + 100
            y = self.text.winfo_rooty() + 100
        self._popup.geometry(f"+{x}+{y}")
        self._popup_paint()

    def _popup_paint(self):
        self._lb.delete(0, "end")
        for it in self._popup_items:
            self._lb.insert("end", it)
        self._lb.config(height=len(self._popup_items),
                        width=max(22, max(len(i) for i in self._popup_items) + 2))
        self._lb.selection_clear(0, "end")
        self._lb.selection_set(self._popup_sel)
        self._lb.activate(self._popup_sel)

    def hide_popup(self):
        if self._popup is not None:
            self._popup.destroy()
            self._popup = None
        self._popup_items = []
        self._popup_sel = 0

    def accept_suggestion(self):
        if not self._popup_items:
            return
        value = self._popup_items[self._popup_sel]
        n = self.cur_line()
        self.replace_line(n, value, keep_col=False)
        self.text.mark_set("insert", f"{n}.end")
        self.hide_popup()
        self.refresh_chrome()
        self.set_dirty(True)

    # ----------------------------------------------------------- chrome state
    def refresh_chrome(self):
        self.sync_types()
        n = self.cur_line()
        t = self.types[n - 1] if self.types else "action"
        self._combo_guard = True
        self.combo_var.set(META[t]["label"])
        self._combo_guard = False
        # stats + pagination estimate
        total, cur_page_lines, cursor_seen = 0, 0, False
        for i in range(1, self.n_lines() + 1):
            ty = self.types[i - 1]
            m = META[ty]
            txt = self.line_text(i)
            wrapped = max(1, math.ceil(len(txt) / m["cpl"])) if txt else 1
            add = wrapped + (m["before"] if i > 1 else 0)
            total += add
            if i <= n:
                cur_page_lines = total
        pages = max(1, math.ceil(total / LINES_PER_PAGE))
        cur_page = max(1, math.ceil(cur_page_lines / LINES_PER_PAGE))
        words = len(re.findall(r"\S+", self.text.get("1.0", "end-1c")))
        scenes = sum(1 for ty in self.types if ty == "scene")
        self.stats_lbl.config(
            text=f"{pages} page{'s' * (pages != 1)} · "
                 f"{scenes} scene{'s' * (scenes != 1)} · {words} words")
        self.page_lbl.config(text=f"Page {cur_page} of {pages}   ·   "
                                  f"{META[t]['label']}")
        self._schedule_scene_rebuild()

    def _schedule_scene_rebuild(self):
        if self._rebuild_job:
            self.after_cancel(self._rebuild_job)
        self._rebuild_job = self.after(200, self.rebuild_scene_list)

    def rebuild_scene_list(self):
        self._rebuild_job = None
        self.scene_list.delete(0, "end")
        self.scene_lines = []
        k = 0
        for i, t in enumerate(self.types, 1):
            if t == "scene":
                k += 1
                label = self.line_text(i).strip() or "(empty heading)"
                self.scene_list.insert("end", f" {k}.  {label}")
                self.scene_lines.append(i)

    def _scene_clicked(self, event=None):
        sel = self.scene_list.curselection()
        if not sel:
            return
        line = self.scene_lines[sel[0]]
        self.text.mark_set("insert", f"{line}.end")
        self.text.see("insert")
        self.text.focus_set()
        self.refresh_chrome()

    def _combo_changed(self, event=None):
        if self._combo_guard:
            return
        label = self.combo_var.get()
        for t in TYPES:
            if META[t]["label"] == label:
                self.set_line_type(self.cur_line(), t)
                break
        self.text.focus_set()

    def _title_changed(self, *args):
        self.doc_title = self.title_var.get().upper()
        if self.title_var.get() != self.doc_title:
            self.title_var.set(self.doc_title)
        self.set_dirty(True)

    def set_dirty(self, val):
        self.dirty = val
        star = "● " if val else ""
        name = self.path.split("/")[-1].split("\\")[-1] if self.path else "Untitled"
        self.title(f"{star}{name} — Scripter")

    def _safe_edit(self, op):
        try:
            getattr(self.text, "edit_" + op)()
        except tk.TclError:
            pass
        self.sync_types()
        self.retag_all()
        self.refresh_chrome()

    # ------------------------------------------------------------ document IO
    def get_elements(self):
        self.sync_types()
        return [{"type": self.types[i - 1], "text": self.line_text(i)}
                for i in range(1, self.n_lines() + 1)]

    def load_elements(self, pairs):
        self.text.delete("1.0", "end")
        self.types = []
        for i, item in enumerate(pairs):
            t, txt = (item["type"], item["text"]) if isinstance(item, dict) else item
            if t not in META:
                t = "action"
            if i:
                self.text.insert("end", "\n")
            self.text.insert("end", txt)
            self.types.append(t)
        if not self.types:
            self.types = ["scene"]
        self.retag_all()
        self.text.mark_set("insert", "end-1c")
        self.text.edit_reset()
        self.refresh_chrome()
        self.rebuild_scene_list()

    def confirm_discard(self):
        if not self.dirty:
            return True
        ans = messagebox.askyesnocancel(
            "Unsaved changes", "Save your screenplay before continuing?")
        if ans is None:
            return False
        if ans:
            return self.on_save()
        return True

    def on_new(self):
        if not self.confirm_discard():
            return
        self.doc_title, self.author, self.path = "UNTITLED SCREENPLAY", "Your Name", None
        self.title_var.set(self.doc_title)
        self.load_elements([("scene", "")])
        self.set_dirty(False)

    def on_open(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open screenplay",
            filetypes=[("Screenplay files", "*.screenplay *.fdx"),
                       ("Scripter (.screenplay)", "*.screenplay"),
                       ("Final Draft (.fdx)", "*.fdx"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            if path.lower().endswith(".fdx"):
                self._open_fdx(path)
            else:
                self._open_json(path)
            self.path = path
            self.set_dirty(False)
        except Exception as exc:
            messagebox.showerror("Could not open file", str(exc))

    def _open_json(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.doc_title = data.get("title", "UNTITLED SCREENPLAY")
        self.author = data.get("author", "")
        self.title_var.set(self.doc_title)
        self.load_elements(data.get("elements", []))

    def _open_fdx(self, path):
        tree = ET.parse(path)
        root = tree.getroot()
        content = root.find("Content")
        pairs = []
        if content is not None:
            for para in content.findall("Paragraph"):
                t = FDX_BACK.get(para.get("Type", "Action"), "action")
                txt = "".join((node.text or "") for node in para.findall("Text"))
                pairs.append((t, txt))
        if not pairs:
            raise ValueError("No script content found in this FDX file.")
        self.load_elements(pairs)

    def on_save(self, save_as=False):
        path = self.path
        if save_as or not path or path.lower().endswith(".fdx"):
            path = filedialog.asksaveasfilename(
                title="Save screenplay", defaultextension=".screenplay",
                initialfile=self.doc_title.title().replace(" ", "") or "Untitled",
                filetypes=[("Scripter (.screenplay)", "*.screenplay")])
            if not path:
                return False
        data = {"title": self.doc_title, "author": self.author,
                "elements": self.get_elements()}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        self.path = path
        self.set_dirty(False)
        return True

    # ---------------------------------------------------------------- exports
    def export_fdx(self):
        path = filedialog.asksaveasfilename(
            title="Export Final Draft", defaultextension=".fdx",
            initialfile=(self.doc_title.title().replace(" ", "_") or "script"),
            filetypes=[("Final Draft", "*.fdx")])
        if not path:
            return
        paras = "\n".join(
            '    <Paragraph Type="{}">\n      <Text>{}</Text>\n    </Paragraph>'
            .format(FDX_NAME[e["type"]], xml_escape(e["text"]))
            for e in self.get_elements())
        doc = ('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
               '<FinalDraft DocumentType="Script" Template="No" Version="5">\n'
               '  <Content>\n' + paras + '\n  </Content>\n'
               '  <TitlePage>\n    <Content>\n'
               '      <Paragraph Alignment="Center"><Text>'
               + xml_escape(self.doc_title) + '</Text></Paragraph>\n'
               '      <Paragraph Alignment="Center"><Text>written by</Text>'
               '</Paragraph>\n'
               '      <Paragraph Alignment="Center"><Text>'
               + xml_escape(self.author) + '</Text></Paragraph>\n'
               '    </Content>\n  </TitlePage>\n</FinalDraft>\n')
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(doc)
        messagebox.showinfo("Exported",
                            "FDX written.\nThis file opens directly in Final Draft.")

    def export_txt(self):
        path = filedialog.asksaveasfilename(
            title="Export text", defaultextension=".txt",
            initialfile=(self.doc_title.title().replace(" ", "_") or "script"),
            filetypes=[("Text", "*.txt")])
        if not path:
            return
        out = []
        out.append(" " * 25 + self.doc_title)
        out.append("")
        out.append(" " * 25 + "written by")
        out.append(" " * 25 + (self.author or ""))
        out.append("\f")
        first = True
        for e in self.get_elements():
            m = META[e["type"]]
            if not first:
                out.extend([""] * m["before"])
            first = False
            pad = " " * int(round(m["indent"] * 10))
            if m["right"]:
                out.append(" " * max(0, 60 - len(e["text"])) + e["text"])
            else:
                width = max(10, m["cpl"])
                words = e["text"].split(" ")
                line = ""
                for w in words:
                    if line and len(line) + 1 + len(w) > width:
                        out.append(pad + line)
                        line = w
                    else:
                        line = (line + " " + w).strip()
                out.append(pad + line)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out))
        messagebox.showinfo("Exported", "Formatted text written.")

    # ---------------------------------------------------------------- dialogs
    def edit_title_page(self):
        win = tk.Toplevel(self)
        win.title("Title page")
        win.configure(bg=PANEL, padx=16, pady=16)
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Title", bg=PANEL, fg=DIM,
                 font=self.ui_small).grid(row=0, column=0, sticky="w")
        tv = tk.StringVar(value=self.doc_title)
        tk.Entry(win, textvariable=tv, width=38,
                 font=self.ui).grid(row=1, column=0, pady=(0, 10))
        tk.Label(win, text="Written by", bg=PANEL, fg=DIM,
                 font=self.ui_small).grid(row=2, column=0, sticky="w")
        av = tk.StringVar(value=self.author)
        tk.Entry(win, textvariable=av, width=38,
                 font=self.ui).grid(row=3, column=0, pady=(0, 12))

        def ok():
            self.doc_title = tv.get().upper() or "UNTITLED SCREENPLAY"
            self.author = av.get()
            self.title_var.set(self.doc_title)
            self.set_dirty(True)
            win.destroy()
        tk.Button(win, text="Done", command=ok, bg=ACCENT, fg="white",
                  relief="flat", padx=14).grid(row=4, column=0, sticky="e")
        win.bind("<Return>", lambda e: ok())

    def show_help(self):
        accel = "Cmd" if self.tk.call("tk", "windowingsystem") == "aqua" else "Ctrl"
        messagebox.showinfo(
            "Keyboard shortcuts",
            "Enter\tNext logical element\n"
            "\t(Scene → Action, Character → Dialogue,\n"
            "\t Dialogue → Character, Transition → Scene)\n\n"
            "Tab\tEmpty line: cycle element type\n"
            "\tWith text: jump (Action → Character,\n"
            "\tDialogue → Parenthetical ...)\n\n"
            "Shift+Tab\tCycle element backwards\n\n"
            f"{accel}+1–7\tScene · Action · Character · Parenthetical ·\n"
            "\tDialogue · Transition · Shot\n\n"
            "Backspace at line start\tMerge with previous element\n\n"
            "SmartType\tSuggestions appear while typing in Scene\n"
            "\tHeadings, Character names and Transitions.\n"
            "\t↑↓ choose · Enter accepts · Esc dismisses\n\n"
            f"{accel}+S / {accel}+O / {accel}+N\tSave / Open / New")

    def show_donate(self):
        if DONATION_URL:
            webbrowser.open(DONATION_URL)
            return
        messagebox.showinfo(
            "Support Scripter",
            "Scripter is free, open-source software.\n\n"
            "No donation link is configured in this copy yet.\n\n"
            "If you maintain this build: open scripter.py and paste your\n"
            "donation page (Ko-fi, GitHub Sponsors, Buy Me a Coffee,\n"
            "PayPal.me ...) into DONATION_URL near the top of the file.\n"
            "This button will then open it in the browser.")

    def open_project_page(self):
        if PROJECT_URL:
            webbrowser.open(PROJECT_URL)
            return
        messagebox.showinfo(
            "Project page",
            "No project page is configured in this copy yet.\n\n"
            "If you maintain this build: set PROJECT_URL near the top of\n"
            "scripter.py to your repository link (e.g. on GitHub).")

    def show_about(self):
        messagebox.showinfo(
            "Scripter",
            "Scripter — a Final Draft–style screenwriting program\n"
            "in pure Python/tkinter.\n\n"
            "Industry-standard formatting, SmartType autocomplete,\n"
            "scene navigator, page estimation, and FDX import/export.\n\n"
            "Saves: .screenplay (JSON)   Opens: .screenplay, .fdx\n"
            "Exports: .fdx (Final Draft), formatted .txt\n\n"
            "Free & open source. Help > Support Scripter ♥ to donate.")

    def on_quit(self):
        if self.confirm_discard():
            self.destroy()


if __name__ == "__main__":
    app = Scripter()
    app.mainloop()
