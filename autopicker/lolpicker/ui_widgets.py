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
HINT_FG = '#8d8d8d'
LINK_FG = '#5fa8d3'
LINK_HOVER_FG = '#a3d0ef'
FONT_ROW = ('Segoe UI', 7, 'bold')
FONT_ROW_SMALL = ('Segoe UI', 6, 'bold')
FONT_ENTRY = ('Segoe UI', 7)
FONT_ENTRY_SMALL = ('Segoe UI', 6)


def link_label(parent, text, command, font=FONT_ENTRY):
    lbl = tk.Label(parent, text=text, bg=ROW_BG, fg=LINK_FG, font=font, cursor='hand2')
    lbl.bind('<Button-1>', lambda e: command())
    lbl.bind('<Enter>', lambda e: lbl.config(fg=LINK_HOVER_FG))
    lbl.bind('<Leave>', lambda e: lbl.config(fg=LINK_FG))
    return lbl


def install_wheel(widget):
    """One application-wide mouse-wheel handler: scrolls the ScrollFrame under the pointer (Windows delta / X11 buttons)."""
    root = widget._root()
    if getattr(root, '_wheel_installed', False):
        return
    root._wheel_installed = True

    def on_wheel(event):
        try:
            target = event.widget.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, AttributeError):
            return None
        while target is not None:
            scroller = getattr(target, '_scroller', None)
            if scroller is not None:
                scroller.scroll(-1 if (getattr(event, 'num', 0) == 4 or event.delta > 0) else 1)
                return 'break'
            target = target.master
        return None
    for sequence in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        root.bind_all(sequence, on_wheel, add='+')


class ScrollFrame:
    """Vertical scroll area in the overlay style: canvas + inner frame, mouse wheel, thin thumb instead of a native scrollbar.
    The canvas grows with its content up to `max_height`; beyond that the content scrolls."""
    TRACK = 3

    def __init__(self, parent, bg=ROW_BG, max_height=200, track_bg='#141c28', thumb='#3a4a5e'):
        self.max_height, self.thumb_color = max_height, thumb
        self.frame = tk.Frame(parent, bg=bg)
        self.canvas = tk.Canvas(self.frame, bg=bg, highlightthickness=0, bd=0, width=1, height=1)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.track = tk.Canvas(self.frame, width=self.TRACK, height=1, bg=track_bg, highlightthickness=0, bd=0)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda e: self.fit())
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas._scroller = self
        self.track._scroller = self
        self.track.bind('<Button-1>', self._jump)
        self.track.bind('<B1-Motion>', self._jump)
        install_wheel(parent)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        self._draw_thumb()

    def fit(self):
        height = self.inner.winfo_reqheight()
        visible = max(1, min(height, self.max_height))
        self.canvas.config(height=visible, width=self.inner.winfo_reqwidth(), scrollregion=(0, 0, 0, height))
        if height > visible:
            if not self.track.winfo_ismapped():
                self.track.pack(side=tk.RIGHT, fill=tk.Y, padx=(1, 0), before=self.canvas)
        else:
            self.track.pack_forget()
            self.canvas.yview_moveto(0)
        self._draw_thumb()

    def scrollable(self):
        return self.inner.winfo_reqheight() > self.max_height

    def scroll(self, steps):
        if not self.scrollable():
            return
        self.canvas.yview_scroll(steps * 2, 'units')
        self._draw_thumb()

    def _jump(self, event):
        height = max(1, self.track.winfo_height())
        top, bottom = self.canvas.yview()
        self.canvas.yview_moveto(max(0.0, min(1.0, event.y / height - (bottom - top) / 2)))
        self._draw_thumb()

    def _draw_thumb(self):
        self.track.delete('all')
        if not self.scrollable():
            return
        height = max(1, self.canvas.winfo_height())
        top, bottom = self.canvas.yview()
        self.track.create_rectangle(0, top * height, self.TRACK, max(top * height + 8, bottom * height), fill=self.thumb_color, outline='')


class SuggestionList:
    """Lolalytics suggestions (bans / hard counters): values always visible, more than VISIBLE rows scroll, click = take over."""
    VISIBLE = 5

    def __init__(self, app, parent, title, on_pick, on_close, taken):
        self.app, self.on_pick, self.taken = app, on_pick, taken
        self.items, self.rows = [], []
        self.frame = tk.Frame(parent, bg=ROW_BG)
        head = tk.Frame(self.frame, bg=ROW_BG)
        head.pack(fill=tk.X)
        self.title = tk.Label(head, text=title, bg=ROW_BG, fg='#7a7259', font=FONT_ENTRY_SMALL, anchor='w')
        self.title.pack(side=tk.LEFT, padx=(2, 0))
        close = tk.Label(head, text='✕', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 6), cursor='hand2')
        close.pack(side=tk.RIGHT, padx=(0, 2))
        close.bind('<Button-1>', lambda e: on_close())
        self.scroll = ScrollFrame(self.frame, ROW_BG, max_height=self.VISIBLE * 21)
        self.scroll.frame.pack(fill=tk.X)
        self.body = self.scroll.inner
        self.status = tk.Label(self.frame, text='', bg=ROW_BG, fg='#7a7259', font=FONT_ENTRY_SMALL, anchor='w', wraplength=200, justify='left')

    def set_loading(self, text='Lolalytics wird geladen …'):
        self.status.config(text=text)
        self.status.pack(fill=tk.X, padx=2)

    def set_error(self, text):
        self.set_loading(text)

    def set_items(self, items, title=None):
        if title:
            self.title.config(text=title)
        self.items = list(items)
        self.status.pack_forget()
        if not self.items:
            self.set_loading('Keine Vorschläge gefunden')
        self.render()

    def render(self):
        for row in self.rows:
            row.destroy()
        self.rows = [self._row(cid, value) for cid, value in self.items]
        self.frame.update_idletasks()
        if len(self.rows) > self.VISIBLE:
            self.scroll.max_height = sum(row.winfo_reqheight() + 2 for row in self.rows[:self.VISIBLE])
        self.scroll.fit()
        self.app._resize_window()

    def _row(self, cid, value):
        taken = self.taken(cid)
        outer = tk.Frame(self.body, bg='#2a3a4a' if not taken else '#1a2230', bd=1, relief='solid')
        outer.pack(fill=tk.X, pady=1, padx=2)
        inner = tk.Frame(outer, bg='#11161f')
        inner.pack(fill=tk.X, padx=1, pady=1)
        fg = '#4f4838' if taken else '#f0e6d2'
        name = tk.Label(inner, text=CHAMPION_NAMES.get(cid, str(cid)) + ('  ✓' if taken else ''), bg='#11161f', fg=fg, font=FONT_ROW_SMALL, anchor='w')
        name.pack(side=tk.LEFT, padx=(3, 0))
        val = tk.Label(inner, text=value, bg='#11161f', fg='#4f4838' if taken else value_color(value), font=FONT_ENTRY_SMALL)
        val.pack(side=tk.RIGHT, padx=(0, 3))
        if not taken:
            for w in (outer, inner, name, val):
                w.config(cursor='hand2')
                w.bind('<Button-1>', lambda e, c=cid: self.on_pick(c))
                w.bind('<Enter>', lambda e, o=outer: o.config(bg='#c8aa6e'))
                w.bind('<Leave>', lambda e, o=outer: o.config(bg='#2a3a4a'))
        return outer

    def destroy(self):
        self.frame.destroy()


def value_color(value):
    """Win rates well below 50 % are the real hard counters: red, then yellow; ban/pick rates stay gold, high win rates green."""
    try:
        number = float(value.split('%')[0].replace(',', '.').strip())
    except (ValueError, IndexError):
        return '#c8aa6e'
    if 'WR' not in value:
        return '#c8aa6e'
    return '#e74c3c' if number < 47 else '#f1c40f' if number < 49 else '#2ecc71' if number >= 52 else '#b0a88a'

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
        self.display_index = 0
        self.hint = ''

    def set_data(self, champ_id, display_index):
        self.champ_id = champ_id
        self.display_index = display_index
        self._render_label()
        self.refresh_rune_btn()

    def _render_label(self):
        name = CHAMPION_NAMES.get(self.champ_id, 'Unbekannt')
        text = f'{self.display_index}. {name}' + (f'  · {self.hint}' if self.hint else '')
        self.lbl.config(text=text, fg=HINT_FG if self.hint else '#f0e6d2')

    def set_hint(self, hint):
        """Short grey note after the name, e.g. 'Mate will' when a teammate hovers this ban."""
        if hint != self.hint:
            self.hint = hint
            if self.champ_id is not None:
                self._render_label()

    def refresh_rune_btn(self):
        if self.rune_btn is not None:
            configured = str(self.champ_id) in getattr(self.app, 'loadouts', {})
            self.rune_btn.config(fg=RUNE_ON_FG if configured else RUNE_OFF_FG)

    def set_index(self, display_index):
        self.display_index = display_index
        if self.champ_id is not None:
            self._render_label()

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
        tools = tk.Frame(self.frame, bg=ROW_BG)
        tools.pack(fill=tk.X, padx=4, pady=(0, 2))
        self.counter_btn = link_label(tools, '⤓ Hardcounter (Lolalytics)', lambda: self.app._load_counters(self), FONT_ENTRY_SMALL)
        self.counter_btn.pack(side=tk.LEFT, padx=(2, 0))
        self.suggest = None
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

    def open_suggestions(self, title):
        """Suggestion list below the grid; the panel's own search stays usable."""
        if self.suggest is None:
            self.suggest = SuggestionList(self.app, self.frame, title, lambda cid: self.app._add_bm(self, cid), self.close_suggestions,
                                          lambda cid: cid in self.app.bad_matchups.get(str(self.owner_champ_id), []))
            self.suggest.frame.pack(fill=tk.X, padx=4, pady=(0, 2))
        return self.suggest

    def close_suggestions(self):
        if self.suggest is not None:
            self.suggest.destroy()
            self.suggest = None
            self.app._resize_window()

    def destroy(self):
        for bm in self.bm_rows:
            bm.destroy()
        if self._focusout_after is not None:
            self.app.root.after_cancel(self._focusout_after)
            self._focusout_after = None
        self.suggest = None
        self.frame.destroy()
