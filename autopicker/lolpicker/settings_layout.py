import tkinter as tk
from .ui_widgets import ROW_BG, ScrollFrame
from .lolalytics import TIERS, TIER_LABELS, BUILDS, BAN_SORTS, patch_options
from .storage import CLOSE_SCOPES
from . import updater
HOTKEY_LABELS = {'toggle_overlay': 'Overlay ein/aus', 'open_lolalytics': 'Lolalytics oeffnen', 'open_vs': 'VS-Matchup oeffnen', 'close_tab': 'Lolalytics-Tabs schliessen', 'close_all_browsers': 'Alles schliessen (alle Browser)'}
WIDTH = 324


class ClassicSettings:
    """Settings window: fixed header + footer, scrollable middle with one headed section per topic."""
    BG = ROW_BG
    BG_PANEL = '#11161f'
    BORDER = '#1a2a3a'
    ACCENT = '#c8aa6e'
    LABEL_FG = '#d4b87a'
    DIM_FG = '#7a7259'
    BTN_BG = '#1a2a3a'
    BTN_HOVER = '#23415e'
    REC_BG = '#8a3a1a'
    HEAD_FG = '#f0e6d2'

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
        self.win.geometry(f'{WIDTH}x400+{x}+{y}')
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
        tk.Label(wrap, text='Mausrad scrollt  ·  Aenderungen gelten sofort', bg=self.BG, fg=self.DIM_FG, font=('Segoe UI', 7)).pack(anchor=tk.W, padx=10, pady=(2, 4))
        max_height = max(300, self.win.winfo_screenheight() - 260)
        self.scroll = ScrollFrame(wrap, self.BG, max_height=max_height)
        self.scroll.frame.pack(fill=tk.X, padx=(10, 6))
        self.content = self.scroll.inner
        self.row_buttons = {}
        self.opacity_scales = {}
        self._build_hotkeys(self._section('TASTENKUERZEL', 'Klicke auf ein Kuerzel, um es neu zu belegen', first=True))
        self._build_display(self._section('DARSTELLUNG'))
        self._build_browser(self._section('BROWSER & SPIEL'))
        self._build_runes_section(self._section('RUNEN & ZAUBER (LOLALYTICS)'))
        self._build_ban_section(self._section('BAN-VORSCHLAEGE  (⤓ Bans)'))
        self._build_counter_section(self._section('HARDCOUNTER-VORSCHLAEGE'))
        self._build_program(self._section('PROGRAMM & UPDATES'))
        foot = tk.Frame(wrap, bg=self.BG)
        foot.pack(fill=tk.X, padx=10, pady=(8, 8))
        reset_btn = tk.Label(foot, text='↺  Kuerzel auf Standard zuruecksetzen', bg=self.BG, fg='#5fa8d3', font=('Segoe UI', 7, 'underline'), cursor='hand2')
        reset_btn.pack(side=tk.LEFT)
        reset_btn.bind('<Button-1>', lambda e: self._reset_defaults())
        reset_btn.bind('<Enter>', lambda e: reset_btn.config(fg='#a3d0ef'))
        reset_btn.bind('<Leave>', lambda e: reset_btn.config(fg='#5fa8d3'))
        hint = tk.Label(foot, text='ESC bricht Aufnahme ab', bg=self.BG, fg=self.DIM_FG, font=('Segoe UI', 6))
        hint.pack(side=tk.RIGHT)
        self._recording = None
        self.win.bind('<KeyPress>', self._on_keypress, add='+')
        self.win.focus_set()

    # ----- sections -----------------------------------------------------------------------------------
    def _section(self, heading, sub=None, first=False):
        head = tk.Frame(self.content, bg=self.BG)
        head.pack(fill=tk.X, pady=(0 if first else 10, 2))
        tk.Label(head, text=heading, bg=self.BG, fg=self.HEAD_FG, font=('Segoe UI', 7, 'bold'), anchor='w').pack(side=tk.LEFT)
        tk.Frame(head, bg=self.BORDER, height=1).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0), pady=(1, 0))
        if sub:
            tk.Label(self.content, text=sub, bg=self.BG, fg=self.DIM_FG, font=('Segoe UI', 6), anchor='w').pack(fill=tk.X, pady=(0, 2))
        frame = tk.Frame(self.content, bg=self.BG_PANEL, bd=1, relief='solid', highlightthickness=0)
        frame.configure(highlightbackground=self.BORDER)
        frame.pack(fill=tk.X)
        return frame

    def _build_hotkeys(self, parent):
        order = ['toggle_overlay', 'open_lolalytics', 'open_vs', 'close_tab', 'close_all_browsers']
        for i, action_id in enumerate(order):
            self._build_row(parent, action_id, HOTKEY_LABELS.get(action_id, action_id), top=i == 0)
        tk.Frame(parent, bg=self.BG_PANEL, height=3).pack()

    def _build_display(self, parent):
        self._build_opacity(parent, 'opacity_default', 'Deckkraft Client/Lobby', top=True)
        self._build_opacity(parent, 'opacity_ingame', 'Deckkraft im Spiel')

    def _build_browser(self, parent):
        toggle_row = tk.Frame(parent, bg=self.BG_PANEL)
        toggle_row.pack(fill=tk.X, padx=6, pady=(6, 3))
        tk.Label(toggle_row, text='Schwacher PC Modus', bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        self.weak_btn = tk.Label(toggle_row, text=self._weak_label(self.app.weak_pc_mode), bg=self._weak_bg(self.app.weak_pc_mode), fg='#f0e6d2', font=('Consolas', 8, 'bold'), padx=10, pady=2, cursor='hand2')
        self.weak_btn.pack(side=tk.RIGHT)
        self.weak_btn.bind('<Button-1>', lambda e: self._toggle_weak_pc())
        self._hint(parent, 'AN  =  sobald das Spiel im Vordergrund ist, wird geschlossen\n         (Umfang siehe unten, in allen verbundenen Browsern).\n         Im Client passiert NICHTS.')
        scope_row = self._row_label(parent, 'Schließen betrifft')
        self._menu_button(scope_row, CLOSE_SCOPES.get(self.app.close_scope, self.app.close_scope), list(CLOSE_SCOPES.items()), self._set_close_scope)
        self._hint(parent, 'Gilt für Alt+Shift+4 und den Schwachen PC Modus.\n         „Ganze Browser“ schließt alle Browserfenster samt Tabs.')
        track_row = tk.Frame(parent, bg=self.BG_PANEL)
        track_row.pack(fill=tk.X, padx=6, pady=(2, 6))
        tk.Label(track_row, text='Live-URL-Tracking', bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        self._build_tracking(track_row)

    def _build_runes_section(self, parent):
        app = self.app
        imp = app.lolalytics_import
        row = self._row_label(parent, 'Flash auf', top=True)
        self.flash_btn = self._toggle_button(row, 'D (links)' if app.flash_side == 'left' else 'F (rechts)', self._toggle_flash)
        self._hint(parent, 'Gilt für importierte und eigene Zauber: Flash wird\n         auf diese Taste gelegt.')
        row = self._row_label(parent, 'Lolalytics-Runen ohne eigene Wahl')
        self.import_btn = self._toggle_button(row, self._weak_label(imp['enabled']), self._toggle_import)
        self.import_btn.config(bg=self._weak_bg(imp['enabled']))
        self._hint(parent, 'AN  =  hat der Champion keine eigenen Runen, werden beim\n         Lock-in Runen + Zauber von Lolalytics genommen.')
        self._filter_rows(parent, imp, self._set_import, build=True)
        row = self._row_label(parent, 'Item-Werte im Runen-Fenster')
        self.item_rates_btn = self._toggle_button(row, self._weak_label(app.show_item_rates), self._toggle_item_rates)
        self.item_rates_btn.config(bg=self._weak_bg(app.show_item_rates))
        self._hint(parent, 'AN  =  Winrate + Spiele unter jedem Item des Standard-Builds.')
        self._hint(parent, 'Pro Champion anpassbar: Runen-Fenster (✦) → „▸ Einstellungen“.', size=6)
        tk.Frame(parent, bg=self.BG_PANEL, height=4).pack()

    def _build_ban_section(self, parent):
        cfg = self.app.ban_suggest_cfg
        row = self._row_label(parent, 'Liste zeigt', top=True)
        self._menu_button(row, BAN_SORTS.get(cfg['sort'], cfg['sort']), list(BAN_SORTS.items()), lambda v: self._set_suggest('ban_suggest_cfg', 'sort', v))
        self._hint(parent, 'Höchste Winrate / Meist gebannt / Meist gespielt –\n         jeweils in der gewählten Rolle, Wert steht daneben.')
        self._filter_rows(parent, cfg, lambda k, v: self._set_suggest('ban_suggest_cfg', k, v))
        tk.Frame(parent, bg=self.BG_PANEL, height=4).pack()

    def _build_counter_section(self, parent):
        cfg = self.app.counter_suggest_cfg
        self._hint(parent, 'Gegner derselben Lane mit deiner schlechtesten Winrate\n         (Bad-Matchup-Feld → „⤓ Hardcounter“).', top=True)
        self._filter_rows(parent, cfg, lambda k, v: self._set_suggest('counter_suggest_cfg', k, v))
        tk.Frame(parent, bg=self.BG_PANEL, height=4).pack()

    def _build_program(self, parent):
        dbg_row = tk.Frame(parent, bg=self.BG_PANEL)
        dbg_row.pack(fill=tk.X, padx=6, pady=(6, 3))
        tk.Label(dbg_row, text='Debug-Modus (Log)', bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        self.debug_btn = tk.Label(dbg_row, text=self._weak_label(self.app.debug_mode), bg=self._weak_bg(self.app.debug_mode), fg='#f0e6d2', font=('Consolas', 8, 'bold'), padx=10, pady=2, cursor='hand2')
        self.debug_btn.pack(side=tk.RIGHT)
        self.debug_btn.bind('<Button-1>', lambda e: self._toggle_debug())
        self._hint(parent, 'AN  =  schreibt Diagnose-Log in\n         %LOCALAPPDATA%\\LoLAutopicker')
        row = self._row_label(parent, 'Updates (GitHub)')
        self.update_btn = self._toggle_button(row, 'NACH UPDATES SUCHEN', self._check_updates)
        self.update_info = None
        self.update_label = tk.Label(parent, text=updater.describe(updater.installed(self.app.controller.bundle)), bg=self.BG_PANEL, fg=self.DIM_FG,
                                     font=('Segoe UI', 7), justify=tk.LEFT, anchor='w', wraplength=WIDTH - 40)
        self.update_label.pack(fill=tk.X, padx=8, pady=(0, 2))
        self._hint(parent, 'Holt den neuesten Branch des Repositories, ersetzt die Programm-\n         dateien (.venv + Browser-Bridge bleiben) und startet neu.')
        tk.Frame(parent, bg=self.BG_PANEL, height=4).pack()

    # ----- building blocks ----------------------------------------------------------------------------
    def _filter_rows(self, parent, cfg, setter, build=False):
        row = self._row_label(parent, 'Rang')
        self._menu_button(row, TIER_LABELS.get(cfg['tier'], cfg['tier']), [(t, TIER_LABELS[t]) for t in TIERS], lambda v: setter('tier', v))
        row = self._row_label(parent, 'Zeitraum / Patch')
        patches = patch_options(getattr(self.app.controller.runes, 'version', ''))
        label = dict(patches).get(cfg['patch'], f"Patch {cfg['patch']}")
        self._menu_button(row, label, patches, lambda v: setter('patch', v))
        if build:
            row = self._row_label(parent, 'Build')
            self._menu_button(row, BUILDS.get(cfg['build'], cfg['build']), list(BUILDS.items()), lambda v: setter('build', v))

    def _hint(self, parent, text, size=7, top=False):
        tk.Label(parent, text=text, bg=self.BG_PANEL, fg=self.DIM_FG, font=('Segoe UI', size), justify=tk.LEFT, anchor='w').pack(fill=tk.X, padx=8, pady=(6 if top else 0, 3))

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

    def _toggle_button(self, row, text, command):
        btn = tk.Label(row, text=text, bg=self.BTN_BG, fg='#f0e6d2', font=('Consolas', 8, 'bold'), padx=10, pady=2, cursor='hand2')
        btn.pack(side=tk.RIGHT)
        btn.bind('<Button-1>', lambda e: command())
        return btn

    def _menu_button(self, row, text, options, command):
        btn = tk.Menubutton(row, text=f'{text} ▾', bg=self.BTN_BG, fg='#f0e6d2', activebackground=self.BTN_HOVER, activeforeground='#f0e6d2',
                            font=('Consolas', 8, 'bold'), relief='flat', bd=0, padx=8, pady=2, cursor='hand2')
        menu = tk.Menu(btn, tearoff=0, bg='#0a1a2b', fg=self.ACCENT, activebackground='#2a3a4a', activeforeground='#f0e6d2', font=('Segoe UI', 7), bd=0)
        for value, label in options:
            menu.add_command(label=label, command=lambda v=value, b=btn, l=label: (command(v), b.config(text=f'{l} ▾')))
        btn.config(menu=menu)
        btn.pack(side=tk.RIGHT)
        return btn

    def _row_label(self, parent, text, top=False):
        row = tk.Frame(parent, bg=self.BG_PANEL)
        row.pack(fill=tk.X, padx=6, pady=(6 if top else 2, 3))
        tk.Label(row, text=text, bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        return row

    # ----- actions ------------------------------------------------------------------------------------
    def _set_close_scope(self, value):
        self.app.close_scope = value
        self.app.save_config()

    def _toggle_flash(self):
        self.app.flash_side = 'right' if self.app.flash_side == 'left' else 'left'
        self.app.save_config()
        self.flash_btn.config(text='D (links)' if self.app.flash_side == 'left' else 'F (rechts)')

    def _toggle_import(self):
        self.app.lolalytics_import = {**self.app.lolalytics_import, 'enabled': not self.app.lolalytics_import['enabled']}
        self.app.save_config()
        on = self.app.lolalytics_import['enabled']
        self.import_btn.config(text=self._weak_label(on), bg=self._weak_bg(on))

    def _toggle_item_rates(self):
        self.app.show_item_rates = not self.app.show_item_rates
        self.app.save_config()
        self.item_rates_btn.config(text=self._weak_label(self.app.show_item_rates), bg=self._weak_bg(self.app.show_item_rates))
        window = self.app._loadout_window
        if window and window.win.winfo_exists():
            window.render_items()

    def _set_import(self, key, value):
        self.app.lolalytics_import = {**self.app.lolalytics_import, key: value}
        self.app.save_config()
        window = self.app._loadout_window
        if window and window.win.winfo_exists() and window.tiles:
            window.build()
            window._refresh_runes()

    def _set_suggest(self, attr, key, value):
        setattr(self.app, attr, {**getattr(self.app, attr), key: value})
        self.app.save_config()
        self.app.reload_suggestions()

    def _check_updates(self):
        self.update_btn.config(text='SUCHE …')
        self.update_info = None
        self.app.check_updates()

    def show_update(self, info, error):
        if not self.win.winfo_exists():
            return
        if error:
            self.update_btn.config(text='NACH UPDATES SUCHEN')
            self.update_label.config(text=error, fg='#e74c3c')
            return
        if info['available']:
            self.update_info = info
            self.update_btn.config(text='JETZT INSTALLIEREN', bg='#1f5a2e')
            self.update_btn.bind('<Button-1>', lambda e: self._install_update())
            self.update_label.config(text=f"Update verfügbar: {info['branch']} @ {info['sha'][:7]} ({info['date'][:10]})\n{info['message']}", fg=self.ACCENT)
        else:
            self.update_btn.config(text='AKTUELL ✓')
            self.update_label.config(text=f"Du hast den neuesten Stand ({info['branch']} @ {info['sha'][:7]}).", fg=self.DIM_FG)

    def _install_update(self):
        if self.update_info is None:
            return
        self.update_btn.config(text='LÄDT …', bg=self.BTN_BG)
        self.update_btn.unbind('<Button-1>')
        self.app.install_update(self.update_info)

    def _build_opacity(self, parent, key, label, top=False):
        row = tk.Frame(parent, bg=self.BG_PANEL)
        row.pack(fill=tk.X, padx=6, pady=(6 if top else 2, 4))
        tk.Label(row, text=label, bg=self.BG_PANEL, fg=self.LABEL_FG, font=('Segoe UI', 8), anchor='w').pack(side=tk.LEFT)
        value = tk.Label(row, text=f'{round(getattr(self.app, key) * 100)} %', bg=self.BG_PANEL, fg='#f0e6d2', font=('Consolas', 8, 'bold'), width=5, anchor='e')
        value.pack(side=tk.RIGHT)
        scale = tk.Scale(row, from_=20, to=100, resolution=5, orient=tk.HORIZONTAL, showvalue=0, length=110, width=8, sliderlength=14,
                         bg=self.BG_PANEL, fg=self.LABEL_FG, troughcolor=self.BTN_BG, activebackground=self.ACCENT, highlightthickness=0, bd=0,
                         command=lambda v, k=key, lbl=value: self._opacity_changed(k, v, lbl))
        scale.set(round(getattr(self.app, key) * 100))
        scale.pack(side=tk.RIGHT, padx=(6, 6))
        scale.bind('<ButtonRelease-1>', lambda e: (self.app.apply_opacity(), self.app.save_config()))
        self.opacity_scales[key] = scale

    def _opacity_changed(self, key, value, label):
        label.config(text=f'{int(float(value))} %')
        self.app.set_opacity(key, float(value))
        self.app.root.attributes('-alpha', int(float(value)) / 100)  # live preview while dragging

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
