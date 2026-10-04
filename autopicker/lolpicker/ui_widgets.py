import tkinter as tk
from .storage import read_json
from .platform_win import bundle_dir
CHAMPION_NAMES = {int(key): value for key, value in read_json(bundle_dir() / 'assets/champions.json', {}).items()}
NAME_TO_ID = {n: i for i, n in CHAMPION_NAMES.items()}
NORM_NAMES = {n.lower().replace(' ', '').replace("'", ''): (n, c) for n, c in NAME_TO_ID.items()}

def find_matches(text):
    text = text.lower().replace(' ', '').replace("'", '')
    if not text:
        return []
    starts = sorted((n for norm, (n, _) in NORM_NAMES.items() if norm.startswith(text)))
    if len(text) <= 2:
        return starts
    contains = sorted((n for norm, (n, _) in NORM_NAMES.items() if text in norm and (not norm.startswith(text))))
    return starts + contains
PICK_BORDER = '#2ecc71'
BAN_BORDER = '#e74c3c'
BAD_BORDER = '#f1c40f'
DRAG_BORDER = '#3a8fd4'
ROW_BG = '#0b0f16'
PICK_PLACEHOLDER = 'Auto Picks ...'
BAN_PLACEHOLDER = 'Auto Bans ...'
BAD_PLACEHOLDER = 'Bad Matchup ...'
PLACEHOLDER_FG = '#6a6a6a'
RUNE_ON_FG = '#c8aa6e'
RUNE_OFF_FG = '#4f4838'
ACTIVE_FG = '#ffffff'
FONT_ROW = ('Segoe UI', 7, 'bold')
FONT_ROW_SMALL = ('Segoe UI', 6, 'bold')
FONT_ENTRY = ('Segoe UI', 7)
FONT_ENTRY_SMALL = ('Segoe UI', 6)

class ChampRow:

    def __init__(self, app, parent, list_type):
        self.app = app
        self.list_type = list_type
        self.champ_id = None
        self.border_color = PICK_BORDER if list_type == 'pick' else BAN_BORDER
        self.outer = tk.Frame(parent, bg=self.border_color, bd=1, relief='solid')
        self.inner = tk.Frame(self.outer, bg=ROW_BG)
        self.inner.pack(fill=tk.X, padx=1, pady=1)
        self.lbl = tk.Label(self.inner, text='', bg=ROW_BG, fg='#f0e6d2', font=FONT_ROW)
        self.lbl.pack(side=tk.LEFT)
        self.del_btn = tk.Label(self.inner, text='✕', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 7), cursor='hand2')
        self.del_btn.pack(side=tk.RIGHT, padx=(2, 0))
        self.del_btn.bind('<Enter>', lambda e: self.del_btn.config(fg='#f0e6d2'))
        self.del_btn.bind('<Leave>', lambda e: self.del_btn.config(fg='#c8aa6e'))
        self.del_btn.bind('<Button-1>', lambda e: self.app._delete_row(self))
        self.dots_btn = None
        self.rune_btn = None
        if list_type == 'pick':
            self.dots_btn = tk.Label(self.inner, text='…', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 8, 'bold'), cursor='hand2')
            self.dots_btn.pack(side=tk.RIGHT, padx=(2, 0))
            self.dots_btn.bind('<Enter>', lambda e: self.dots_btn.config(fg='#f0e6d2'))
            self.dots_btn.bind('<Leave>', lambda e: self.dots_btn.config(fg='#c8aa6e'))
            self.dots_btn.bind('<Button-1>', lambda e: self.app._toggle_bad_matchups(self))
            # Runes & summoner spells for this champion: gold = configured, dim = none yet.
            self.rune_btn = tk.Label(self.inner, text='✦', bg=ROW_BG, fg=RUNE_OFF_FG, font=('Segoe UI', 8, 'bold'), cursor='hand2')
            self.rune_btn.pack(side=tk.RIGHT, padx=(2, 0))
            self.rune_btn.bind('<Enter>', lambda e: self.rune_btn.config(fg='#f0e6d2'))
            self.rune_btn.bind('<Leave>', lambda e: self.refresh_rune_btn())
            self.rune_btn.bind('<Button-1>', lambda e: self.app._open_loadout(self))
        for w in (self.outer, self.inner, self.lbl):
            w.bind('<ButtonPress-1>', lambda e, r=self: self.app._dnd_start(e, r))
            w.bind('<B1-Motion>', lambda e, r=self: self.app._dnd_motion(e, r))
            w.bind('<ButtonRelease-1>', lambda e, r=self: self.app._dnd_release(e, r))
            w.bind('<Double-Button-1>', lambda e, r=self: self.app._edit_row(r))
        self.edit_entry = None
        self.is_initial_edit_replace = False
        self.edit_list_frame = None
        self.edit_listbox = None

    def set_data(self, champ_id, display_index):
        self.champ_id = champ_id
        name = CHAMPION_NAMES.get(champ_id, 'Unbekannt')
        self.lbl.config(text=f'{display_index}. {name}')
        self.refresh_rune_btn()

    def refresh_rune_btn(self):
        if self.rune_btn is not None:
            configured = str(self.champ_id) in getattr(self.app, 'loadouts', {})
            self.rune_btn.config(fg=RUNE_ON_FG if configured else RUNE_OFF_FG)

    def set_index(self, display_index):
        if self.champ_id is not None:
            name = CHAMPION_NAMES.get(self.champ_id, 'Unbekannt')
            self.lbl.config(text=f'{display_index}. {name}')

    def set_dragged(self, dragged):
        self.outer.config(bg=DRAG_BORDER if dragged else self.border_color)

    def destroy(self):
        self.outer.destroy()

class BadMatchupRow:

    def __init__(self, app, parent, owner_champ_id):
        self.app = app
        self.owner_champ_id = owner_champ_id
        self.champ_id = None
        self.border_color = BAD_BORDER
        self.outer = tk.Frame(parent, bg=self.border_color, bd=1, relief='solid')
        self.inner = tk.Frame(self.outer, bg=ROW_BG)
        self.inner.pack(fill=tk.X, padx=1, pady=1)
        self.lbl = tk.Label(self.inner, text='', bg=ROW_BG, fg='#f0e6d2', font=FONT_ROW_SMALL)
        self.lbl.pack(side=tk.LEFT, padx=(2, 2))
        self.del_btn = tk.Label(self.inner, text='✕', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 6), cursor='hand2')
        self.del_btn.pack(side=tk.RIGHT, padx=(2, 2))
        self.del_btn.bind('<Enter>', lambda e: self.del_btn.config(fg='#f0e6d2'))
        self.del_btn.bind('<Leave>', lambda e: self.del_btn.config(fg='#c8aa6e'))
        self.del_btn.bind('<Button-1>', lambda e: self.app._delete_bm(self))
        for w in (self.outer, self.inner, self.lbl):
            w.bind('<ButtonPress-1>', lambda e, r=self: self.app._bm_dnd_start(e, r))
            w.bind('<B1-Motion>', lambda e, r=self: self.app._bm_dnd_motion(e, r))
            w.bind('<ButtonRelease-1>', lambda e, r=self: self.app._bm_dnd_release(e, r))
            w.bind('<Double-Button-1>', lambda e, r=self: self.app._edit_bm(r))
        self.edit_entry = None
        self.is_initial_edit_replace = False
        self.edit_list_frame = None
        self.edit_listbox = None

    def set_data(self, champ_id):
        self.champ_id = champ_id
        name = CHAMPION_NAMES.get(champ_id, 'Unbekannt')
        self.lbl.config(text=name)

    def set_dragged(self, dragged):
        self.outer.config(bg=DRAG_BORDER if dragged else self.border_color)

    def destroy(self):
        self.outer.destroy()

class BadMatchupsPanel:
    MAX = 6
    PER_ROW = 3

    def __init__(self, app, parent, owner_row):
        self.app = app
        self.owner_row = owner_row
        self.owner_champ_id = owner_row.champ_id
        self.bm_rows = []
        self.frame = tk.Frame(parent, bg=ROW_BG)
        self.search_frame = tk.Frame(self.frame, bg=ROW_BG)
        self.search_frame.pack(fill=tk.X, padx=4, pady=(2, 0))
        self.entry = tk.Entry(self.search_frame, bg='#1a2a3a', fg=PLACEHOLDER_FG, insertbackground='#ffffff', font=FONT_ENTRY_SMALL, relief='flat', borderwidth=0, selectbackground='#1a2a3a', selectforeground=PLACEHOLDER_FG, highlightthickness=0)
        self.entry.pack(fill=tk.X, padx=2, pady=1)
        self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)
        self.listbox = tk.Listbox(self.search_frame, bg='#0a1a2b', fg='#c8aa6e', font=FONT_ENTRY_SMALL, height=4, borderwidth=0, highlightthickness=0, selectbackground='#2a3a4a', selectforeground='#f0e6d2', activestyle='none', exportselection=False)
        self.listbox.pack_forget()
        self.grid_frame = tk.Frame(self.frame, bg=ROW_BG)
        self.grid_frame.pack(fill=tk.X, padx=4, pady=(2, 2))
        self.entry.bind('<KeyPress>', self._on_keypress)
        self.entry.bind('<KeyRelease>', self._on_keyrelease)
        self.entry.bind('<FocusIn>', self._on_focusin)
        self.entry.bind('<FocusOut>', self._on_focusout)
        self.entry.bind('<Button-1>', self._on_click)
        self.entry.bind('<Double-Button-1>', self._on_dblclick)
        self.entry.bind('<Return>', lambda e: self._confirm())
        self.entry.bind('<Down>', lambda e: self.app._listbox_navigate(self.listbox, 1))
        self.entry.bind('<Up>', lambda e: self.app._listbox_navigate(self.listbox, -1))
        self.listbox.bind('<Button-1>', self._on_listbox_click)
        self.listbox.bind('<Double-Button-1>', self._on_listbox_click)
        self._focusout_after = None

    def _on_keypress(self, event):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            if event.char and len(event.char) == 1 and event.char.isprintable():
                self.entry.delete(0, tk.END)
                self.entry.config(fg=ACTIVE_FG)
                self.entry.insert(0, event.char)
                self.entry.icursor(1)
                return 'break'
            if event.keysym not in ('Tab', 'Escape'):
                return 'break'
        return None

    def _on_keyrelease(self, event):
        if self.entry.get() == '':
            if not self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
                self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)
            self.listbox.pack_forget()
            return
        if event.keysym in ('Up', 'Down', 'Return', 'Left', 'Right', 'Escape'):
            return
        self._update_suggestions()

    def _on_focusin(self, event):
        if self._focusout_after is not None:
            try:
                self.app.root.after_cancel(self._focusout_after)
            except Exception:
                pass
            self._focusout_after = None
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.entry.icursor(0)
        elif self.entry.get().strip():
            self._update_suggestions()

    def _on_focusout(self, event):
        if self._focusout_after is not None:
            try:
                self.app.root.after_cancel(self._focusout_after)
            except Exception:
                pass
        self._focusout_after = self.app.root.after(150, self._hide_suggestions)

    def _hide_suggestions(self):
        self.listbox.pack_forget()
        if self.entry.get().strip() == '':
            self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)

    def _on_click(self, event):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.app.root.after_idle(lambda: self.entry.icursor(0))
        return None

    def _on_dblclick(self, event):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.entry.selection_clear()
            self.entry.icursor(0)
            return 'break'
        return None

    def _update_suggestions(self):
        if self.app._is_placeholder(self.entry, BAD_PLACEHOLDER):
            self.listbox.pack_forget()
            return
        self.listbox.delete(0, tk.END)
        matches = find_matches(self.entry.get())
        if not matches:
            self.listbox.pack_forget()
            return
        if matches:
            num = min(len(matches), 5)
            self.listbox.config(height=num)
            for m in matches[:num]:
                self.listbox.insert(tk.END, m)
            if not self.listbox.winfo_ismapped():
                self.listbox.pack(fill=tk.X, padx=2, pady=(0, 1))
        else:
            self.listbox.pack_forget()
        self.app._resize_window()

    def _on_listbox_click(self, event):
        try:
            idx = self.listbox.nearest(event.y)
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx)
            self.listbox.activate(idx)
        except Exception:
            pass
        if self._focusout_after is not None:
            try:
                self.app.root.after_cancel(self._focusout_after)
            except Exception:
                pass
            self._focusout_after = None
        self._confirm()
        return 'break'

    def _confirm(self):
        sel = self.listbox.curselection()
        if sel:
            name = self.listbox.get(sel[0])
        elif self.listbox.size() > 0:
            name = self.listbox.get(0)
        else:
            name = self.entry.get().strip()
        if name in NAME_TO_ID:
            self.app._add_bm(self, NAME_TO_ID[name])
            self.entry.delete(0, tk.END)
            self.app._set_placeholder(self.entry, BAD_PLACEHOLDER)
            self.listbox.pack_forget()
            self.app._resize_window()

    def rebuild_grid(self):
        for bm in self.bm_rows:
            try:
                bm.outer.grid_forget()
                bm.outer.pack_forget()
            except Exception:
                pass
        for c in range(self.PER_ROW):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform='bm')
        for i, bm in enumerate(self.bm_rows):
            r = i // self.PER_ROW
            c = i % self.PER_ROW
            bm.outer.grid(in_=self.grid_frame, row=r, column=c, sticky='ew', padx=1, pady=1)

    def add_row(self, champ_id):
        if len(self.bm_rows) >= self.MAX:
            return
        bm = BadMatchupRow(self.app, self.grid_frame, self.owner_champ_id)
        bm.set_data(champ_id)
        self.bm_rows.append(bm)
        self.rebuild_grid()

    def remove_row(self, bm_row):
        if bm_row in self.bm_rows:
            self.bm_rows.remove(bm_row)
            bm_row.destroy()
            self.rebuild_grid()

    def destroy(self):
        for bm in self.bm_rows:
            bm.destroy()
        if self._focusout_after is not None:
            self.app.root.after_cancel(self._focusout_after)
            self._focusout_after = None
        self.frame.destroy()
