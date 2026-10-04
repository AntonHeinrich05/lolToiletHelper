import tkinter as tk
from .ui_widgets import ROW_BG
HOTKEY_LABELS = {'toggle_overlay': 'Overlay ein/aus', 'open_lolalytics': 'Lolalytics oeffnen', 'open_vs': 'VS-Matchup oeffnen', 'close_tab': 'Tab schliessen', 'close_all_browsers': 'Alle Browser schliessen'}

class ClassicSettings:
    BG = ROW_BG
    BG_PANEL = '#11161f'
    BORDER = '#1a2a3a'
    ACCENT = '#c8aa6e'
    LABEL_FG = '#d4b87a'
    DIM_FG = '#7a7259'
    BTN_BG = '#1a2a3a'
    BTN_HOVER = '#23415e'
    REC_BG = '#8a3a1a'

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.attributes('-alpha', 0.96)
        self.win.configure(bg=self.BORDER)
        try:
            x = self.root.winfo_x() + 20
            y = self.root.winfo_y() + 30
        except Exception:
            x, y = (200, 200)
        self.win.geometry(f'320x400+{x}+{y}')
        wrap = tk.Frame(self.win, bg=self.BG, bd=0)
        wrap.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        top = tk.Frame(wrap, bg=self.BG, height=22)
        top.pack(fill=tk.X, padx=8, pady=(6, 0))
        title = tk.Label(top, text='⋮  Einstellungen', bg=self.BG, fg=self.ACCENT, font=('Segoe UI', 9, 'bold'))
        title.pack(side=tk.LEFT)
        close_lbl = tk.Label(top, text='✕', bg=self.BG, fg=self.ACCENT, font=('Segoe UI', 10, 'bold'), cursor='hand2')
        close_lbl.pack(side=tk.RIGHT)
        close_lbl.bind('<Button-1>', lambda e: self.close())
        close_lbl.bind('<Enter>', lambda e: close_lbl.config(fg='#f0e6d2'))
        close_lbl.bind('<Leave>', lambda e: close_lbl.config(fg=self.ACCENT))
        self._drag_x = 0
        self._drag_y = 0
        for w in (top, title):
            w.bind('<Button-1>', self._start_drag)
            w.bind('<B1-Motion>', self._drag)
        sub = tk.Label(wrap, text='Tastenkuerzel  -  klicke auf einen Hotkey um ihn neu zu binden', bg=self.BG, fg=self.DIM_FG, font=('Segoe UI', 7))
        sub.pack(anchor=tk.W, padx=10, pady=(2, 6))
        list_frame = tk.Frame(wrap, bg=self.BG_PANEL, bd=1, relief='solid', highlightthickness=0)
        list_frame.pack(fill=tk.X, padx=10, pady=2)
        list_frame.configure(highlightbackground=self.BORDER)
        self.row_buttons = {}
        order = ['toggle_overlay', 'open_lolalytics', 'open_vs', 'close_tab', 'close_all_browsers']
        for i, action_id in enumerate(order):
            self._build_row(list_frame, action_id, HOTKEY_LABELS.get(action_id, action_id), top=i == 0)
        opt_frame = tk.Frame(wrap, bg=self.BG_PANEL, bd=1, relief='solid', highlightthickness=0)
        opt_frame.configure(highlightbackground=self.BORDER)
        opt_frame.pack(fill=tk.X, padx=10, pady=(8, 2))
        toggle_row = tk.Frame(opt_frame, bg=self.BG_PANEL)
        toggle_row.pack(fill=tk.X, padx=6, pady=(6, 3))
        tk.Label(toggle_row, text='Schwacher PC Modus', bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        self.weak_btn = tk.Label(toggle_row, text=self._weak_label(self.app.weak_pc_mode), bg=self._weak_bg(self.app.weak_pc_mode), fg='#f0e6d2', font=('Consolas', 8, 'bold'), padx=10, pady=2, cursor='hand2')
        self.weak_btn.pack(side=tk.RIGHT)
        self.weak_btn.bind('<Button-1>', lambda e: self._toggle_weak_pc())
        hint1 = tk.Label(opt_frame, text='AN  =  beim Spielstart (im Match!) werden\n         alle Browser lautlos geschlossen.\n         Im Client/Lobby passiert NICHTS.', bg=self.BG_PANEL, fg=self.DIM_FG, font=('Segoe UI', 7), justify=tk.LEFT, anchor='w')
        hint1.pack(fill=tk.X, padx=8, pady=(0, 4))
        dbg_row = tk.Frame(opt_frame, bg=self.BG_PANEL)
        dbg_row.pack(fill=tk.X, padx=6, pady=(2, 3))
        tk.Label(dbg_row, text='Debug-Modus (Log)', bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        self.debug_btn = tk.Label(dbg_row, text=self._weak_label(self.app.debug_mode), bg=self._weak_bg(self.app.debug_mode), fg='#f0e6d2', font=('Consolas', 8, 'bold'), padx=10, pady=2, cursor='hand2')
        self.debug_btn.pack(side=tk.RIGHT)
        self.debug_btn.bind('<Button-1>', lambda e: self._toggle_debug())
        dbg_hint = tk.Label(opt_frame, text='AN  =  schreibt Diagnose-Log in\n         %LOCALAPPDATA%\\LoLAutopicker', bg=self.BG_PANEL, fg=self.DIM_FG, font=('Segoe UI', 7), justify=tk.LEFT, anchor='w')
        dbg_hint.pack(fill=tk.X, padx=8, pady=(0, 4))
        track_row = tk.Frame(opt_frame, bg=self.BG_PANEL)
        track_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Label(track_row, text='Live-URL-Tracking', bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        self._build_tracking(track_row)
        foot = tk.Frame(wrap, bg=self.BG)
        foot.pack(fill=tk.X, padx=10, pady=(10, 8))
        reset_btn = tk.Label(foot, text='↺  Auf Standard zuruecksetzen', bg=self.BG, fg='#5fa8d3', font=('Segoe UI', 7, 'underline'), cursor='hand2')
        reset_btn.pack(side=tk.LEFT)
        reset_btn.bind('<Button-1>', lambda e: self._reset_defaults())
        reset_btn.bind('<Enter>', lambda e: reset_btn.config(fg='#a3d0ef'))
        reset_btn.bind('<Leave>', lambda e: reset_btn.config(fg='#5fa8d3'))
        hint = tk.Label(foot, text='ESC bricht Aufnahme ab', bg=self.BG, fg=self.DIM_FG, font=('Segoe UI', 6))
        hint.pack(side=tk.RIGHT)
        self._recording = None
        self.win.bind('<KeyPress>', self._on_keypress, add='+')
        self.win.focus_set()

    def _build_row(self, parent, action_id, label, top=False):
        row = tk.Frame(parent, bg=self.BG_PANEL)
        row.pack(fill=tk.X, padx=6, pady=(6 if top else 3, 3))
        name = tk.Label(row, text=label, bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w')
        name.pack(side=tk.LEFT)
        hk_text = self._format_hotkey(self.app.hotkeys.get(action_id, ''))
        btn = tk.Label(row, text=hk_text, bg=self.BTN_BG, fg='#f0e6d2', font=('Consolas', 8, 'bold'), padx=8, pady=2, cursor='hand2')
        btn.pack(side=tk.RIGHT)
        btn.bind('<Button-1>', lambda e, a=action_id: self._start_recording(a))
        btn.bind('<Enter>', lambda e, b=btn, a=action_id: b.config(bg=self.BTN_HOVER) if self._recording != a else None)
        btn.bind('<Leave>', lambda e, b=btn, a=action_id: b.config(bg=self.BTN_BG) if self._recording != a else None)
        self.row_buttons[action_id] = btn

    @staticmethod
    def _weak_label(on):
        return 'AN' if on else 'AUS'

    @staticmethod
    def _weak_bg(on):
        return '#1f5a2e' if on else '#5a2e1f'

    @staticmethod
    def _format_hotkey(combo):
        if not combo:
            return '— nicht gesetzt —'
        out = combo.replace('<alt>', 'Alt').replace('<shift>', 'Shift').replace('<ctrl>', 'Ctrl').replace('<cmd>', 'Cmd').replace('<enter>', 'Enter').replace('<space>', 'Space').replace('<tab>', 'Tab')
        parts = []
        for p in out.split('+'):
            p = p.strip()
            if p.startswith('<') and p.endswith('>') and (len(p) > 2) and (p[1] == 'f') and p[2:-1].isdigit():
                parts.append('F' + p[2:-1])
            elif len(p) == 1:
                parts.append(p.upper())
            else:
                parts.append(p)
        return ' + '.join(parts)

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.win.winfo_x()
        self._drag_y = e.y_root - self.win.winfo_y()

    def _drag(self, e):
        self.win.geometry(f'+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}')

    def _reset_button(self, action_id):
        if action_id in self.row_buttons:
            self.row_buttons[action_id].config(text=self._format_hotkey(self.app.hotkeys.get(action_id, '')), bg=self.BTN_BG)
