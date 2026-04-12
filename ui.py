"""
Tkinter-based windows for freewispr.
- FloatingIndicator : small always-on-top pill (recording / transcribing state)
- SnippetsWindow    : manage trigger → expansion pairs
- DictionaryWindow  : manage word corrections (Whisper mistakes)
- SettingsWindow    : hotkey, model, language, filler filter, auto-punctuate
"""
import tkinter as tk
from tkinter import ttk, messagebox

import snippets as snippet_module
import corrections as corr_module


BG = "#0f0f0f"
BG2 = "#1a1a1a"
ACC = "#7c5cfc"
ACC2 = "#5a3fd4"
FG = "#e8e8e8"
FG2 = "#888"
FONT = ("Segoe UI", 10)


def _style(root):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure("TButton", background=ACC, foreground=FG, font=FONT, relief="flat", padding=6)
    s.map("TButton", background=[("active", ACC2)])
    s.configure("Danger.TButton", background="#c0392b", foreground=FG, font=FONT, relief="flat", padding=6)
    s.map("Danger.TButton", background=[("active", "#96281b")])
    s.configure("TLabel", background=BG, foreground=FG, font=FONT)
    s.configure("Sub.TLabel", background=BG, foreground=FG2, font=("Segoe UI", 9))
    s.configure("TFrame", background=BG)
    s.configure("TEntry", fieldbackground=BG2, foreground=FG, font=FONT)
    s.configure("TCombobox", fieldbackground=BG2, foreground=FG, font=FONT)
    s.configure("TCheckbutton", background=BG, foreground=FG, font=FONT)
    s.map("TCheckbutton", background=[("active", BG)])
    s.configure("Treeview",
                background=BG2, foreground=FG,
                fieldbackground=BG2, font=FONT,
                rowheight=28, borderwidth=0, relief="flat")
    s.configure("Treeview.Heading",
                background=BG, foreground=FG2,
                font=("Segoe UI", 9), relief="flat")
    s.map("Treeview",
          background=[("selected", ACC)],
          foreground=[("selected", FG)])


# --------------------------------------------------------------------------- #
#  Floating indicator pill                                                     #
# --------------------------------------------------------------------------- #

class FloatingIndicator:
    _COLORS = {
        "listen":      "#7c5cfc",
        "transcribe":  "#f39c12",
        "done":        "#27ae60",
        "error":       "#e74c3c",
    }

    def __init__(self, root: tk.Tk):
        self._root = root
        self._win: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        self._dot: tk.Label | None = None
        self._blink_job = None
        self._state: str = "listen"

    def show(self, message: str, state: str = "listen"):
        self._state = state
        self._root.after(0, self._show, message, state)

    def hide(self, delay_ms: int = 800):
        self._root.after(delay_ms, self._hide)

    def _show(self, message: str, state: str):
        color = self._COLORS.get(state, ACC)

        if self._win is None:
            self._win = tk.Toplevel(self._root)
            self._win.overrideredirect(True)
            self._win.attributes("-topmost", True)
            self._win.attributes("-alpha", 0.93)
            self._win.configure(bg=BG2)

            outer = tk.Frame(self._win, bg=BG2, padx=14, pady=7)
            outer.pack()

            self._dot = tk.Label(outer, text="●", bg=BG2, fg=color,
                                 font=("Segoe UI", 9))
            self._dot.pack(side="left", padx=(0, 7))

            self._label = tk.Label(outer, text=message, bg=BG2, fg=FG,
                                   font=("Segoe UI", 10))
            self._label.pack(side="left")

            self._win.update_idletasks()
            sw = self._win.winfo_screenwidth()
            w = self._win.winfo_reqwidth()
            self._win.geometry(f"+{(sw - w) // 2}+18")
        else:
            if self._label:
                self._label.configure(text=message)
            if self._dot:
                self._dot.configure(fg=color)

        if self._blink_job:
            self._root.after_cancel(self._blink_job)
        self._blink(color)

    def _hide(self):
        if self._blink_job:
            self._root.after_cancel(self._blink_job)
            self._blink_job = None
        if self._win:
            self._win.destroy()
            self._win = None
            self._label = None
            self._dot = None

    def _blink(self, color: str):
        if self._win is None or self._dot is None:
            return
        current = self._dot.cget("fg")
        next_color = BG2 if current != BG2 else color
        self._dot.configure(fg=next_color)
        self._blink_job = self._root.after(550, self._blink, color)


# --------------------------------------------------------------------------- #
#  Shared helper: entry dialog for add/edit rows                              #
# --------------------------------------------------------------------------- #

class _PairDialog(tk.Toplevel):
    """Modal dialog with two fields: a short trigger/key and a longer value."""

    def __init__(self, parent, title, key_label, val_label,
                 key="", val="", on_save=None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        _style(self)

        self._on_save = on_save

        pad = {"padx": 20, "pady": 5}

        ttk.Label(self, text=key_label, style="Sub.TLabel").pack(anchor="w", padx=20, pady=(16, 2))
        self._key_var = tk.StringVar(value=key)
        ttk.Entry(self, textvariable=self._key_var, width=36).pack(anchor="w", **pad)

        ttk.Label(self, text=val_label, style="Sub.TLabel").pack(anchor="w", padx=20, pady=(10, 2))
        self._val = tk.Text(self, height=4, width=40,
                            bg=BG2, fg=FG, font=FONT,
                            insertbackground=FG, relief="flat",
                            borderwidth=1, highlightthickness=1,
                            highlightbackground=FG2, highlightcolor=ACC)
        self._val.pack(padx=20, pady=(0, 4))
        self._val.insert("1.0", val)

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=20, pady=(8, 16))
        ttk.Button(btn_row, text="Save", command=self._save).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="left")

        self.wait_window()

    def _save(self):
        key = self._key_var.get().strip().lower()
        val = self._val.get("1.0", "end-1c").strip()
        if not key:
            messagebox.showwarning("freewispr", "Trigger / word cannot be empty.", parent=self)
            return
        if not val:
            messagebox.showwarning("freewispr", "Expansion / correction cannot be empty.", parent=self)
            return
        if self._on_save:
            self._on_save(key, val)
        self.destroy()


# --------------------------------------------------------------------------- #
#  Snippets window                                                             #
# --------------------------------------------------------------------------- #

class SnippetsWindow:
    """
    Manage snippet library.
    Say a trigger word exactly → it gets replaced with the full expansion.
    E.g. "my address" → "123 Main St, City, State 12345"
    """

    def __init__(self):
        self.root = tk.Toplevel()
        self.root.title("freewispr — Snippets")
        self.root.geometry("640x420")
        self.root.configure(bg=BG)
        _style(self.root)
        self._build()
        self._load()

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(16, 4))
        ttk.Label(hdr, text="Snippets", font=("Segoe UI", 13, "bold")).pack(side="left")

        ttk.Label(
            self.root,
            text="Say a trigger word exactly while dictating — it expands to the full text.",
            style="Sub.TLabel",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # Treeview
        cols = ("trigger", "expansion")
        self._tree = ttk.Treeview(self.root, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.heading("trigger",   text="Trigger")
        self._tree.heading("expansion", text="Expansion")
        self._tree.column("trigger",   width=160, minwidth=100, stretch=False)
        self._tree.column("expansion", width=420, minwidth=200)
        self._tree.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        sb = ttk.Scrollbar(self.root, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)

        # Buttons
        btn_row = ttk.Frame(self.root)
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(btn_row, text="Add",    command=self._add).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Edit",   command=self._edit).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Delete", command=self._delete,
                   style="Danger.TButton").pack(side="left")

    def _load(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        for trigger, expansion in snippet_module.load().items():
            preview = expansion[:80] + "…" if len(expansion) > 80 else expansion
            self._tree.insert("", "end", values=(trigger, preview))

    def _add(self):
        _PairDialog(
            self.root,
            title="Add Snippet",
            key_label='Trigger (e.g. "my address", "sig", "thanks"):',
            val_label="Expands to:",
            on_save=self._save_pair,
        )

    def _edit(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("freewispr", "Select a snippet to edit.", parent=self.root)
            return
        trigger = self._tree.item(sel[0])["values"][0]
        snips = snippet_module.load()
        _PairDialog(
            self.root,
            title="Edit Snippet",
            key_label='Trigger:',
            val_label="Expands to:",
            key=trigger,
            val=snips.get(trigger, ""),
            on_save=lambda new_key, new_val, old=trigger: self._update_pair(old, new_key, new_val),
        )

    def _delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("freewispr", "Select a snippet to delete.", parent=self.root)
            return
        trigger = self._tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("freewispr", f'Delete snippet "{trigger}"?', parent=self.root):
            return
        snips = snippet_module.load()
        snips.pop(trigger, None)
        snippet_module.save(snips)
        self._load()

    def _save_pair(self, key: str, val: str):
        snips = snippet_module.load()
        snips[key] = val
        snippet_module.save(snips)
        self._load()

    def _update_pair(self, old_key: str, new_key: str, new_val: str):
        snips = snippet_module.load()
        snips.pop(old_key, None)
        snips[new_key] = new_val
        snippet_module.save(snips)
        self._load()


# --------------------------------------------------------------------------- #
#  Personal dictionary window                                                  #
# --------------------------------------------------------------------------- #

class DictionaryWindow:
    """
    Manage personal word corrections.
    Whisper output is scanned and matching words are replaced automatically.
    E.g. "wisp" → "freewispr",  "pra car" → "Prakhar"
    """

    def __init__(self):
        self.root = tk.Toplevel()
        self.root.title("freewispr — Personal Dictionary")
        self.root.geometry("580x400")
        self.root.configure(bg=BG)
        _style(self.root)
        self._build()
        self._load()

    def _build(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(16, 4))
        ttk.Label(hdr, text="Personal Dictionary", font=("Segoe UI", 13, "bold")).pack(side="left")

        ttk.Label(
            self.root,
            text="Words Whisper gets wrong are automatically replaced after transcription.",
            style="Sub.TLabel",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        cols = ("wrong", "right")
        self._tree = ttk.Treeview(self.root, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.heading("wrong", text="Whisper hears")
        self._tree.heading("right", text="Replace with")
        self._tree.column("wrong", width=230, minwidth=100, stretch=False)
        self._tree.column("right", width=310, minwidth=150)
        self._tree.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        sb = ttk.Scrollbar(self.root, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)

        btn_row = ttk.Frame(self.root)
        btn_row.pack(fill="x", padx=16, pady=(0, 16))
        ttk.Button(btn_row, text="Add",    command=self._add).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Edit",   command=self._edit).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="Delete", command=self._delete,
                   style="Danger.TButton").pack(side="left")

    def _load(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        for wrong, right in corr_module.load().items():
            self._tree.insert("", "end", values=(wrong, right))

    def _add(self):
        _PairDialog(
            self.root,
            title="Add Correction",
            key_label="Whisper hears (what it gets wrong):",
            val_label="Replace with (correct spelling / name):",
            on_save=self._save_pair,
        )

    def _edit(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("freewispr", "Select an entry to edit.", parent=self.root)
            return
        wrong = self._tree.item(sel[0])["values"][0]
        corrs = corr_module.load()
        _PairDialog(
            self.root,
            title="Edit Correction",
            key_label="Whisper hears:",
            val_label="Replace with:",
            key=wrong,
            val=corrs.get(wrong, ""),
            on_save=lambda nk, nv, old=wrong: self._update_pair(old, nk, nv),
        )

    def _delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("freewispr", "Select an entry to delete.", parent=self.root)
            return
        wrong = self._tree.item(sel[0])["values"][0]
        if not messagebox.askyesno("freewispr", f'Delete correction for "{wrong}"?', parent=self.root):
            return
        corrs = corr_module.load()
        corrs.pop(wrong, None)
        corr_module.save(corrs)
        self._load()

    def _save_pair(self, key: str, val: str):
        corrs = corr_module.load()
        corrs[key] = val
        corr_module.save(corrs)
        self._load()

    def _update_pair(self, old_key: str, new_key: str, new_val: str):
        corrs = corr_module.load()
        corrs.pop(old_key, None)
        corrs[new_key] = new_val
        corr_module.save(corrs)
        self._load()


# --------------------------------------------------------------------------- #
#  Settings window                                                             #
# --------------------------------------------------------------------------- #

class SettingsWindow:
    def __init__(self, config: dict, on_save=None):
        self.cfg = config.copy()
        self.on_save = on_save

        self.root = tk.Toplevel()
        self.root.title("freewispr — Settings")
        self.root.geometry("440x400")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        _style(self.root)

        self._build()

    def _build(self):
        pad = {"padx": 20, "pady": 6}

        ttk.Label(self.root, text="Settings", font=("Segoe UI", 13, "bold")).pack(anchor="w", **pad)

        # Hotkey
        ttk.Label(self.root, text="Dictation hotkey").pack(anchor="w", padx=20, pady=(12, 0))
        self._hotkey_var = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+space"))
        ttk.Entry(self.root, textvariable=self._hotkey_var, width=30).pack(anchor="w", **pad)
        ttk.Label(self.root, text="e.g. ctrl+space, right ctrl, F9, alt+shift",
                  style="Sub.TLabel").pack(anchor="w", padx=20, pady=(0, 4))

        # Model size
        ttk.Label(self.root, text="Whisper model").pack(anchor="w", padx=20, pady=(8, 0))
        self._model_var = tk.StringVar(value=self.cfg.get("model_size", "base"))
        ttk.Combobox(self.root, textvariable=self._model_var,
                     values=["tiny", "base", "small"],
                     state="readonly", width=20).pack(anchor="w", **pad)
        ttk.Label(self.root, text="tiny=fastest (~40MB)  base=balanced (~150MB)  small=best (~500MB)",
                  style="Sub.TLabel").pack(anchor="w", padx=20, pady=(0, 4))

        # Language
        ttk.Label(self.root, text="Language").pack(anchor="w", padx=20, pady=(8, 0))
        self._lang_var = tk.StringVar(value=self.cfg.get("language", "en"))
        ttk.Entry(self.root, textvariable=self._lang_var, width=10).pack(anchor="w", **pad)
        ttk.Label(self.root, text="ISO 639-1 code: en, es, fr, de, hi…",
                  style="Sub.TLabel").pack(anchor="w", padx=20, pady=(0, 4))

        # Checkboxes
        self._filler_var = tk.BooleanVar(value=self.cfg.get("filter_fillers", False))
        ttk.Checkbutton(
            self.root,
            text='Remove filler words ("um", "uh", "you know"…)',
            variable=self._filler_var,
        ).pack(anchor="w", padx=20, pady=(12, 2))

        self._punct_var = tk.BooleanVar(value=self.cfg.get("auto_punctuate", True))
        ttk.Checkbutton(
            self.root,
            text="Auto-punctuate (capitalize + add period if missing)",
            variable=self._punct_var,
        ).pack(anchor="w", padx=20, pady=(2, 12))

        ttk.Button(self.root, text="Save", command=self._save).pack(anchor="e", padx=20, pady=8)

    def _save(self):
        self.cfg["hotkey"] = self._hotkey_var.get().strip()
        self.cfg["model_size"] = self._model_var.get()
        self.cfg["language"] = self._lang_var.get().strip()
        self.cfg["filter_fillers"] = self._filler_var.get()
        self.cfg["auto_punctuate"] = self._punct_var.get()
        if self.on_save:
            self.on_save(self.cfg)
        self.root.destroy()
