"""Rune page + summoner spell picker per auto-pick champion, in the overlay's style (client-like layout)."""
import logging
import threading
import tkinter as tk

from .lolalytics import BUILDS, TIERS, TIER_LABELS, import_settings, patch_options
from .runes import STAT_SHARDS, SPELL_IDS
from .ui_widgets import CHAMPION_NAMES, ROW_BG

LOG = logging.getLogger(__name__)
BG_PANEL = '#11161f'
BORDER = '#1a2a3a'
ACCENT = '#c8aa6e'
LABEL_FG = '#d4b87a'
DIM_FG = '#7a7259'
SELECTED = '#f0e6d2'
TILE = 36
ICON = 32


class IconStore:
    """Tk PhotoImages (32px) from Data Dragon PNGs; integer subsampling keeps Tk-only (no Pillow)."""

    def __init__(self, data):
        self.data, self.images = data, {}

    def get(self, icon):
        if icon not in self.images:
            try:
                data = self.data.icon_bytes(icon, fetch=False)  # never block the UI thread on the network
                if data is None:
                    return None
                image = tk.PhotoImage(data=data)
                factor = max(1, round(image.width() / ICON))
                self.images[icon] = image.subsample(factor) if factor > 1 else image
            except (OSError, tk.TclError, ValueError):
                self.images[icon] = None
        return self.images[icon]


class Tile:
    def __init__(self, window, parent, identifier, icon, name, desc='', command=None):
        self.window, self.identifier, self.name, self.desc, self.command = window, identifier, name, desc, command
        self.canvas = tk.Canvas(parent, width=TILE, height=TILE, bg=BG_PANEL, highlightthickness=0, cursor='hand2')
        image = window.icons.get(icon) if icon else None
        if image is not None:
            self.canvas.create_image(TILE // 2, TILE // 2, image=image)
        else:
            self.canvas.create_text(TILE // 2, TILE // 2, text=name[:3], fill=LABEL_FG, font=('Segoe UI', 7, 'bold'))
        self.dim = self.canvas.create_rectangle(0, 0, TILE, TILE, fill=ROW_BG, stipple='gray50', outline='')
        self.ring = self.canvas.create_rectangle(1, 1, TILE - 1, TILE - 1, outline='#263445', width=2)
        self.canvas.bind('<Button-1>', lambda e: command(identifier) if command else None)
        self.canvas.bind('<Enter>', self._enter)
        self.canvas.bind('<Leave>', self._leave)
        self.selected = False

    def set_selected(self, selected):
        self.selected = selected
        self.canvas.itemconfigure(self.dim, state='hidden' if selected else 'normal')
        self.canvas.itemconfigure(self.ring, outline=ACCENT if selected else '#263445', width=2)

    def _enter(self, _):
        if not self.selected:
            self.canvas.itemconfigure(self.ring, outline=LABEL_FG)
        self.window.show_tooltip(self.canvas, self.name, self.desc)

    def _leave(self, _):
        if not self.selected:
            self.canvas.itemconfigure(self.ring, outline='#263445')
        self.window.hide_tooltip()


class LoadoutWindow:
    def __init__(self, app, champ_id):
        self.app, self.champ_id = app, champ_id
        self.data = app.controller.runes
        self.icons = IconStore(self.data)
        self.tooltip = None
        self.tiles = {}
        self.root = app.root
        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.attributes('-alpha', 0.96)
        self.win.configure(bg=BORDER)
        self.win.geometry(f'+{self.root.winfo_x() + 20}+{self.root.winfo_y() + 30}')
        self.wrap = tk.Frame(self.win, bg=ROW_BG)
        self.wrap.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        top = tk.Frame(self.wrap, bg=ROW_BG)
        top.pack(fill=tk.X, padx=8, pady=(6, 0))
        name = CHAMPION_NAMES.get(champ_id, str(champ_id))
        title = tk.Label(top, text=f'✦  Runen & Zauber  –  {name}', bg=ROW_BG, fg=ACCENT, font=('Segoe UI', 9, 'bold'))
        title.pack(side=tk.LEFT)
        close = tk.Label(top, text='✕', bg=ROW_BG, fg=ACCENT, font=('Segoe UI', 10, 'bold'), cursor='hand2')
        close.pack(side=tk.RIGHT)
        close.bind('<Button-1>', lambda e: self.close())
        for w in (top, title):
            w.bind('<Button-1>', self._start_drag)
            w.bind('<B1-Motion>', self._drag)
        self.body = tk.Frame(self.wrap, bg=ROW_BG)
        self.body.pack(fill=tk.BOTH, expand=True)
        self.status = tk.Label(self.wrap, text='', bg=ROW_BG, fg=DIM_FG, font=('Segoe UI', 7), anchor='w')
        self.status.pack(fill=tk.X, padx=10, pady=(0, 6))
        saved = app.loadouts.get(str(champ_id))
        self.state = dict(saved) if saved else None
        self.show_jungle = bool(saved and saved.get('jungle_spells'))
        self.show_import_settings = bool(saved and saved.get('lolalytics'))
        self.previews = {}
        self.preview = None
        self.win.bind('<Escape>', lambda e: self.close())
        self._wait_for_data()

    def _wait_for_data(self):
        if not self.win.winfo_exists():
            return
        if self.data.ready():
            self.icons_ready = threading.Event()
            threading.Thread(target=self._prefetch_icons, daemon=True).start()
            self.status.config(text='Symbole werden geladen …')
            self._poll_icons()
            return
        if self.data.loaded.is_set():
            self.status.config(text=self.data.error or 'Runen-Daten fehlen')
            return
        self.status.config(text='Runen-Daten werden geladen …')
        self.win.after(400, self._wait_for_data)

    def _prefetch_icons(self):
        self.data.prefetch_icons()  # instant when the background loader already cached them
        self.icons_ready.set()  # Tk is touched only from the main thread (see _poll_icons)

    def _poll_icons(self):
        if not self.win.winfo_exists():
            return
        if self.icons_ready.is_set():
            self.build()
        else:
            self.win.after(100, self._poll_icons)

    def style(self, identifier):
        return next((s for s in self.data.styles if s['id'] == identifier), None)

    def default_state(self):
        primary, sub = self.data.styles[0], self.data.styles[1]
        return {'primary': primary['id'], 'sub': sub['id'],
                'perks': [slot['runes'][0]['id'] for slot in primary['slots']] + [sub['slots'][1]['runes'][0]['id'], sub['slots'][2]['runes'][0]['id']],
                'shards': [row[0][0] for row in STAT_SHARDS], 'spells': [4, 12]}

    def build(self):
        if not self.win.winfo_exists():
            return
        if not self.state or not self.data.validate(self.state):
            self.state = self.default_state()
        for child in self.body.winfo_children():
            child.destroy()
        self.tiles = {}
        columns = tk.Frame(self.body, bg=ROW_BG)
        columns.pack(fill=tk.X, padx=8, pady=(4, 0))
        left = self._panel(columns, 'HAUPTPFAD')
        right = self._panel(columns, 'NEBENPFAD')
        left.master.pack(side=tk.LEFT, anchor='n', padx=(0, 4))
        right.master.pack(side=tk.LEFT, anchor='n')
        primary, sub = self.style(self.state['primary']), self.style(self.state['sub'])
        self._row(left, [(s['id'], s['icon'], s['name'], '') for s in self.data.styles], self.set_primary, {primary['id']})
        self._separator(left)
        for index, slot in enumerate(primary['slots']):
            self._row(left, [(r['id'], r['icon'], r['name'], r['shortDesc']) for r in slot['runes']],
                      lambda rid, i=index: self.set_perk(i, rid), {self.state['perks'][index]})
        self._row(right, [(s['id'], s['icon'], s['name'], '') for s in self.data.styles if s['id'] != primary['id']], self.set_sub, {sub['id']})
        self._separator(right)
        for slot in sub['slots'][1:]:
            self._row(right, [(r['id'], r['icon'], r['name'], r['shortDesc']) for r in slot['runes']], self.set_sub_perk, set(self.state['perks'][4:]))
        self._separator(right)
        for index, shards in enumerate(STAT_SHARDS):
            self._row(right, [(sid, f'perk-images/StatMods/{icon}', name, desc) for sid, name, icon, desc in shards],
                      lambda sid, i=index: self.set_shard(i, sid), {self.state['shards'][index]}, size_pad=0)
        spells = self._panel(self.body, 'BESCHWÖRERZAUBER')
        spells.master.pack(fill=tk.X, padx=8, pady=(6, 0))
        items = [(sid, self.data.spells[sid]['icon'], self.data.spells[sid]['name'], '') for sid in SPELL_IDS if sid in self.data.spells]
        self._row(spells, items[:6], self.set_spell, set(self.state['spells']))
        self._row(spells, items[6:], self.set_spell, set(self.state['spells']))
        side = 'D (links)' if self.app.flash_side == 'left' else 'F (rechts)'
        tk.Label(spells, text=f'Flash liegt auf {side} (Einstellungen). Jungle ohne Smite → Flash + Smite.', bg=BG_PANEL, fg=DIM_FG,
                 font=('Segoe UI', 6)).pack(anchor='w', padx=4)
        jungle = tk.Frame(self.body, bg=ROW_BG)
        jungle.pack(fill=tk.X, padx=8, pady=(4, 0))
        toggle = tk.Label(jungle, text=('▾' if self.show_jungle else '▸') + '  Zauber, falls zufällig Jungle', bg=ROW_BG, fg=DIM_FG,
                          font=('Segoe UI', 7), cursor='hand2')
        toggle.pack(anchor='w')
        toggle.bind('<Button-1>', lambda e: self.toggle_jungle())
        if self.show_jungle:
            panel = self._panel(jungle, 'JUNGLE-ZAUBER (optional, sonst Flash + Smite)')
            panel.master.pack(fill=tk.X, pady=(2, 0))
            selected = set(self.state.get('jungle_spells') or [])
            self._row(panel, items[:6], self.set_jungle_spell, selected)
            self._row(panel, items[6:], self.set_jungle_spell, selected)
        foot = tk.Frame(self.body, bg=ROW_BG)
        foot.pack(fill=tk.X, padx=10, pady=(8, 2))
        save = tk.Label(foot, text='SPEICHERN', bg='#1a2a3a', fg=SELECTED, font=('Consolas', 8, 'bold'), padx=12, pady=3, cursor='hand2')
        save.pack(side=tk.LEFT)
        save.bind('<Button-1>', lambda e: self.save())
        save.bind('<Enter>', lambda e: save.config(bg='#23415e'))
        save.bind('<Leave>', lambda e: save.config(bg='#1a2a3a'))
        imp = tk.Label(foot, text='⤓ Von Lolalytics', bg=ROW_BG, fg='#5fa8d3', font=('Segoe UI', 7, 'underline'), cursor='hand2')
        imp.pack(side=tk.LEFT, padx=(10, 0))
        imp.bind('<Button-1>', lambda e: self.import_lolalytics())
        own = self.state.get('lolalytics') or {}
        toggle = tk.Label(foot, text=('▾' if self.show_import_settings else '▸') + (' Einstellungen •' if own else ' Einstellungen'),
                          bg=ROW_BG, fg=ACCENT if own else DIM_FG, font=('Segoe UI', 7), cursor='hand2')
        toggle.pack(side=tk.LEFT, padx=(8, 0))
        toggle.bind('<Button-1>', lambda e: self.toggle_import_settings())
        if str(self.champ_id) in self.app.loadouts:
            remove = tk.Label(foot, text='Entfernen', bg=ROW_BG, fg='#e74c3c', font=('Segoe UI', 7, 'underline'), cursor='hand2')
            remove.pack(side=tk.RIGHT)
            remove.bind('<Button-1>', lambda e: self.remove())
        if self.show_import_settings:
            self._build_import_settings()
        # Import preview: win rate + games of the Lolalytics rune page that "⤓ Von Lolalytics" would take.
        self.preview = tk.Label(self.body, text='', bg=ROW_BG, fg=DIM_FG, font=('Segoe UI', 6), anchor='w')
        self.preview.pack(fill=tk.X, padx=10, pady=(2, 0))
        self._load_preview()
        self.status.config(text='Gewählt = hell mit goldenem Rand. Wird beim Lock-in automatisch gesetzt.')
        self.win.update_idletasks()
        self.win.geometry(f'{self.win.winfo_reqwidth()}x{self.win.winfo_reqheight()}')

    def preview_key(self):
        cfg = import_settings(self.app.lolalytics_import, self.state)
        return (cfg['tier'], cfg['patch'], cfg['build'], self.app.list_role)

    def _load_preview(self):
        key = self.preview_key()
        if key in self.previews:
            self.preview.config(text=self.previews[key])
            return
        self.preview.config(text='Lolalytics-Vorschau wird geladen …')
        self.app.fetch_rune_preview(self.champ_id, key)

    def show_preview(self, key, text):
        self.previews[key] = text
        if self.preview is not None and self.preview.winfo_exists() and key == self.preview_key():
            self.preview.config(text=text)

    def _build_import_settings(self):
        """Champion-specific Lolalytics rank/patch/build (collapsed): try e.g. 'Highest Win' for just this champion."""
        panel = self._panel(self.body, f'LOLALYTICS FÜR {CHAMPION_NAMES.get(self.champ_id, self.champ_id).upper()} (sonst Einstellungen)')
        panel.master.pack(fill=tk.X, padx=8, pady=(2, 0))
        panel.pack_configure(fill=tk.X)
        cfg = import_settings(self.app.lolalytics_import, self.state)
        own = self.state.get('lolalytics') or {}
        patches = patch_options(getattr(self.data, 'version', ''))
        rows = (('Rang', 'tier', [(t, TIER_LABELS[t]) for t in TIERS], TIER_LABELS.get(cfg['tier'], cfg['tier'])),
                ('Zeitraum / Patch', 'patch', patches, dict(patches).get(cfg['patch'], f"Patch {cfg['patch']}")),
                ('Build', 'build', list(BUILDS.items()), BUILDS.get(cfg['build'], cfg['build'])))
        for label, key, options, current in rows:
            row = tk.Frame(panel, bg=BG_PANEL)
            row.pack(fill=tk.X, padx=4, pady=1)
            tk.Label(row, text=label, bg=BG_PANEL, fg=LABEL_FG, font=('Segoe UI', 7), anchor='w').pack(side=tk.LEFT)
            btn = tk.Menubutton(row, text=f'{current} ▾', bg='#1a2a3a' if key in own else '#141c28', fg=SELECTED, activebackground='#23415e',
                                activeforeground=SELECTED, font=('Consolas', 7, 'bold'), relief='flat', bd=0, padx=6, pady=1, cursor='hand2')
            menu = tk.Menu(btn, tearoff=0, bg='#0a1a2b', fg=ACCENT, activebackground='#2a3a4a', activeforeground=SELECTED, font=('Segoe UI', 7), bd=0)
            for value, text in options:
                menu.add_command(label=text, command=lambda v=value, k=key: self.set_import_setting(k, v))
            btn.config(menu=menu)
            btn.pack(side=tk.RIGHT)
        foot = tk.Frame(panel, bg=BG_PANEL)
        foot.pack(fill=tk.X, padx=4, pady=(2, 0))
        hint = 'Eigene Werte (gold) gelten nur für diesen Champion.' if own else 'Noch keine eigenen Werte – es gelten die Einstellungen.'
        tk.Label(foot, text=hint, bg=BG_PANEL, fg=DIM_FG, font=('Segoe UI', 6)).pack(side=tk.LEFT)
        if own:
            reset = tk.Label(foot, text='Standard', bg=BG_PANEL, fg='#5fa8d3', font=('Segoe UI', 6, 'underline'), cursor='hand2')
            reset.pack(side=tk.RIGHT)
            reset.bind('<Button-1>', lambda e: self.set_import_setting(None, None))

    def set_import_setting(self, key, value):
        if key is None:
            self.state.pop('lolalytics', None)
        else:
            own = {**(self.state.get('lolalytics') or {}), key: value}
            self.state['lolalytics'] = {k: v for k, v in own.items() if self.app.lolalytics_import.get(k) != v} or None
            if not self.state['lolalytics']:
                self.state.pop('lolalytics')
        self.build()

    def toggle_import_settings(self):
        self.show_import_settings = not self.show_import_settings
        self.build()

    def _panel(self, parent, caption):
        frame = tk.Frame(parent, bg=BG_PANEL, bd=1, relief='solid', highlightthickness=0)
        tk.Label(frame, text=caption, bg=BG_PANEL, fg=DIM_FG, font=('Segoe UI', 6, 'bold')).pack(anchor='w', padx=6, pady=(3, 0))
        inner = tk.Frame(frame, bg=BG_PANEL)
        inner.pack(padx=4, pady=(0, 4))
        return inner

    def _separator(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill=tk.X, padx=6, pady=3)

    def _row(self, parent, items, command, selected, size_pad=2):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(anchor='w', pady=size_pad)
        for identifier, icon, name, desc in items:
            tile = Tile(self, row, identifier, icon, name, desc, command)
            tile.canvas.pack(side=tk.LEFT, padx=2)
            tile.set_selected(identifier in selected)
            self.tiles.setdefault(identifier, []).append(tile)

    def set_primary(self, style_id):
        if style_id == self.state['primary']:
            return
        style = self.style(style_id)
        if self.state['sub'] == style_id:
            other = self.style(self.state['primary'])  # swap: the old primary becomes the sub path
            self.state['sub'] = other['id']
            self.state['perks'][4:] = [other['slots'][1]['runes'][0]['id'], other['slots'][2]['runes'][0]['id']]
        self.state['primary'] = style_id
        self.state['perks'][:4] = [slot['runes'][0]['id'] for slot in style['slots']]
        self.build()

    def set_sub(self, style_id):
        if style_id == self.state['sub']:
            return
        style = self.style(style_id)
        self.state['sub'] = style_id
        self.state['perks'][4:] = [style['slots'][1]['runes'][0]['id'], style['slots'][2]['runes'][0]['id']]
        self.build()

    def set_perk(self, index, perk_id):
        self.state['perks'][index] = perk_id
        self.build()

    def set_sub_perk(self, perk_id):
        sub = self.style(self.state['sub'])
        row_of = {r['id']: i for i, slot in enumerate(sub['slots'][1:]) for r in slot['runes']}
        current = list(self.state['perks'][4:])
        same_row = [i for i, p in enumerate(current) if row_of.get(p) == row_of[perk_id]]
        # Like the client: one rune per row, two rows; a third row replaces the older selection.
        if same_row:
            current[same_row[0]] = perk_id
        else:
            current = [current[1], perk_id]
        self.state['perks'][4:] = current
        self.build()

    def set_shard(self, index, shard_id):
        self.state['shards'][index] = shard_id
        self.build()

    def set_spell(self, spell_id):
        spells = self.state['spells']
        if spell_id not in spells:
            self.state['spells'] = [spells[1], spell_id]
        self.build()

    def set_jungle_spell(self, spell_id):
        spells = list(self.state.get('jungle_spells') or [4, 11])
        if spell_id not in spells:
            self.state['jungle_spells'] = [spells[1], spell_id]
        self.build()

    def toggle_jungle(self):
        self.show_jungle = not self.show_jungle
        if not self.show_jungle:
            self.state.pop('jungle_spells', None)
        self.build()

    def import_lolalytics(self):
        self.status.config(text='Lolalytics wird geladen …')
        own = self.state.get('lolalytics')

        def done(results):
            if not self.win.winfo_exists():
                return
            loadout = results.get(str(self.champ_id))
            if loadout:
                keep = {k: self.state[k] for k in ('jungle_spells',) if self.state.get(k)}
                if own:
                    keep['lolalytics'] = own
                self.state = {**loadout, **keep}
                self.build()
            else:
                self.status.config(text='Lolalytics-Import fehlgeschlagen (Internet / Champion-Seite?)')
        self.app.import_lolalytics([self.champ_id], done=done, config=import_settings(self.app.lolalytics_import, self.state))

    def save(self):
        self.app.loadouts[str(self.champ_id)] = dict(self.state)
        if self.app.save_config():
            self.app.notice(f'Runen & Zauber gespeichert: {CHAMPION_NAMES.get(self.champ_id, self.champ_id)}')
            self.app._refresh_row_data('pick')
            self.close()

    def remove(self):
        self.app.loadouts.pop(str(self.champ_id), None)
        if self.app.save_config():
            self.app._refresh_row_data('pick')
            self.close()

    def show_tooltip(self, widget, name, desc):
        self.hide_tooltip()
        self.tooltip = tk.Toplevel(self.win)
        self.tooltip.overrideredirect(True)
        self.tooltip.attributes('-topmost', True)
        self.tooltip.configure(bg=ACCENT)
        text = name if not desc else f'{name}\n{strip_tags(desc)}'
        tk.Label(self.tooltip, text=text, bg=ROW_BG, fg=SELECTED, font=('Segoe UI', 7), justify='left',
                 wraplength=220, padx=6, pady=4).pack(padx=1, pady=1)
        self.tooltip.geometry(f'+{widget.winfo_rootx() + TILE}+{widget.winfo_rooty() + TILE}')

    def hide_tooltip(self):
        if self.tooltip is not None and self.tooltip.winfo_exists():
            self.tooltip.destroy()
        self.tooltip = None

    def _start_drag(self, e):
        self._drag_origin = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag(self, e):
        self.win.geometry(f'+{e.x_root - self._drag_origin[0]}+{e.y_root - self._drag_origin[1]}')

    def close(self):
        self.hide_tooltip()
        if self.win.winfo_exists():
            self.win.destroy()
        if self.app._loadout_window is self:
            self.app._loadout_window = None


def strip_tags(text):
    import re
    return re.sub(r'<[^>]+>', '', text or '').replace('&nbsp;', ' ')
