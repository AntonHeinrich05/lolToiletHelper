import logging
import queue
import tkinter as tk

from .hotkeys import Hotkeys
from .loadout_ui import LoadoutWindow
from .settings_ui import SettingsWindow
from .ui_layout import ClassicOverlay
from .ui_widgets import BAN_BORDER, CHAMPION_NAMES, PICK_BORDER, ROW_BG
from .storage import ROLE_LABELS
from .urls import LANES
from .lolalytics import fetch_build, to_loadout, import_settings, fetch_bans, fetch_counters
import threading

INGAME_PHASES = ('InProgress', 'GameStart', 'Reconnect')
NEUTRAL_BORDER = '#818181'
STATUS_SHADES = {'banned': '#33ff00', 'bad_matchup': '#ffd900', 'hovered': '#3a8fd4', 'teammate': '#4a4a4a'}
BAN_HINTS = {'teammate': 'Mate will – übersprungen'}


class App(ClassicOverlay):
    SETTINGS = ('auto_ready_enabled', 'auto_pick_enabled', 'auto_pick_champs',
                'auto_ban_champs', 'auto_pick_minimized', 'bad_matchups',
                'hotkeys', 'weak_pc_mode', 'debug_mode', 'live_tracking',
                'opacity_default', 'opacity_ingame', 'loadouts',
                'flash_side', 'lolalytics_import', 'role_lists', 'list_role', 'close_scope')

    def __init__(self, root, controller):
        self.controller = controller
        self._settings_window = None
        self._loadout_window = None
        self._toast = None
        self._toast_timer = None
        self._closed = False
        self._manual_role = None
        self.last_notice = ''
        self.browser_clients = {}
        self.connected = False
        super().__init__(root)
        root.title('LoL Autopicker')
        root.protocol('WM_DELETE_WINDOW', self.quit)
        self.auto_ready_var.set(self.auto_ready_enabled)
        try:
            self.icon = tk.PhotoImage(file=str(controller.bundle / 'assets/icon.png'))
            root.iconphoto(True, self.icon)
        except tk.TclError:
            pass
        self.hotkey_manager = Hotkeys(root, self.action)
        try:
            self.hotkey_manager.apply(self.hotkeys)
        except ValueError as error:
            self.last_notice = str(error)
        self.status_label.bind('<Button-3>', lambda _: self.notice(self.connection_status()))
        root.deiconify()
        self._resize_window()
        self.controller.changed()
        self._poll_id = root.after(50, self.process_queue)

    def load_config(self):
        config = self.controller.settings.snapshot()
        for key in self.SETTINGS:
            setattr(self, key, config[key])
        # The overlay lists show the selected role list; the general lists stay stored separately.
        self.general_lists = {'auto_pick_champs': list(config['auto_pick_champs']), 'auto_ban_champs': list(config['auto_ban_champs'])}
        if self.list_role:
            lists = self.role_lists.get(self.list_role, {})
            self.auto_pick_champs = list(lists.get('auto_pick_champs', []))
            self.auto_ban_champs = list(lists.get('auto_ban_champs', []))

    def save_config(self):
        changes = {key: getattr(self, key) for key in self.SETTINGS}
        if self.list_role:
            role_lists = {k: dict(v) for k, v in self.role_lists.items()}
            role_lists[self.list_role] = {'auto_pick_champs': list(self.auto_pick_champs), 'auto_ban_champs': list(self.auto_ban_champs)}
            changes.update(role_lists=role_lists, **self.general_lists)
        if not self.controller.settings.update(**changes):
            error = self.controller.settings.last_error
            self.load_config()
            self.notice(error)
            self.root.after_idle(self._restore_saved_widgets)
            return False
        self.controller.changed()
        return True

    def _restore_saved_widgets(self):
        if self._closed:
            return
        self.auto_ready_var.set(self.auto_ready_enabled)
        self.auto_pick_toggle_var.set(self.auto_pick_enabled)
        self._close_bm_panel()
        self._refresh_row_data('pick')
        self._refresh_row_data('ban')
        if self.auto_pick_enabled and not self.auto_pick_minimized:
            self.show_auto_pick_widgets()
            self._arrange_content()
        else:
            self.hide_auto_pick_widgets()
        self.update_min_btn_text()
        self._resize_window()

    def toggle_auto_ready(self):
        self.auto_ready_enabled = self.auto_ready_var.get()
        self.save_config()

    def toggle_auto_pick(self):
        self.auto_pick_enabled = self.auto_pick_toggle_var.get()
        if self.auto_pick_enabled:
            self.auto_pick_minimized = False
        if not self.save_config():
            return
        if self.auto_pick_enabled:
            self.show_auto_pick_widgets()
            self._arrange_content()
            self._refresh_row_data('pick')
            self._refresh_row_data('ban')
            self.pick_search_entry.focus_set()
        else:
            self.hide_auto_pick_widgets()
        self.update_min_btn_text()
        self._ensure_champ_frame_at_bottom()
        self._resize_window()

    def action(self, action):
        actions = {'toggle_overlay': self.toggle_overlay,
                   'open_lolalytics': self.open_lolalytics, 'open_vs': self.open_vs,
                   'close_tab': lambda: self.controller.enqueue('close'),
                   'close_all_browsers': lambda: self.controller.enqueue('close_lolalytics', all_clients=True)}
        logging.getLogger(__name__).info('Hotkey empfangen: %s', action)
        if action in actions:
            actions[action]()

    def _select_role(self, role, manual=True):
        if role == self.list_role:
            return
        if manual:
            self._manual_role = None
        if not self.save_config():
            return
        if not self.controller.settings.update(list_role=role):
            return
        self.load_config()
        self._close_bm_panel()
        self._close_ban_suggestions()
        self._refresh_row_data('pick')
        self._refresh_row_data('ban')
        self._arrange_content()
        self.role_btn.config(text=f'{ROLE_LABELS.get(role, role)}  ▾')
        self._resize_window()

    def _follow_assigned_role(self, position):
        """Champion select: the assigned role's own list wins; otherwise the list the player selected stays. Restored after."""
        role = LANES.get(str(position or '').lower(), '')
        target = role if role in self.role_lists else (self._manual_role if self._manual_role is not None else self.list_role)
        if target == self.list_role or self._dnd_state:
            return
        if self._manual_role is None:
            self._manual_role = self.list_role
        self._select_role(target, manual=False)
        self.notice(f'Liste für {ROLE_LABELS.get(target, target)} aktiv (zugewiesene Rolle)' if target == role
                    else f'Liste für {ROLE_LABELS.get(target, target)} aktiv (deine Auswahl)')

    def import_lolalytics(self, champ_ids, role=None, done=None, config=None):
        """Background import of Lolalytics runes/spells for the given champions (lane = role list or default).
        Rank/patch/build: `config` if given, else the champion's own settings, else the global settings."""
        role = self.list_role if role is None else role
        names = {cid: CHAMPION_NAMES.get(cid, str(cid)) for cid in champ_ids}
        configs = {cid: config or import_settings(self.lolalytics_import, self.loadouts.get(str(cid))) for cid in champ_ids}

        def work():
            results, failed = {}, []
            for cid, name in names.items():
                cfg = configs[cid]
                try:
                    build = fetch_build(name, role, cfg['tier'], cfg['patch'], cfg['build'])
                    results[str(cid)] = to_loadout(build, self.controller.runes, self.flash_side)
                except (OSError, ValueError, KeyError) as error:
                    logging.getLogger(__name__).info('Lolalytics-Import %s fehlgeschlagen: %s', name, error)
                    failed.append(name)
            # Tk is touched only from the main thread: deliver through the UI event queue.
            self.controller.emit({'type': 'import_done', 'results': results, 'failed': failed, 'done': done})

        self.notice(f'Lolalytics-Import läuft ({len(names)}) …', 2500)
        threading.Thread(target=work, daemon=True, name='LolalyticsImport').start()

    def _import_finished(self, results, failed, done):
        if self._closed:
            return
        for key, loadout in results.items():
            existing = self.loadouts.get(key, {})
            for keep in ('jungle_spells', 'lolalytics'):
                if existing.get(keep):
                    loadout[keep] = existing[keep]
            self.loadouts[key] = loadout
        if results:
            self.save_config()
            self._refresh_row_data('pick')
        text = f'Lolalytics-Runen importiert: {len(results)}' + (f', fehlgeschlagen: {", ".join(failed)}' if failed else '')
        self.notice(text)
        if done:
            done(results)

    def fetch_suggestions(self, kind, panel, champ_id=None):
        """Background Lolalytics lookup (rank/period from the import settings, default All Ranks / 30 days):
        'bans' = most banned champions of the selected role list, 'counters' = worst matchups of `champ_id` in its lane."""
        role, cfg = self.list_role, self.lolalytics_import
        name = CHAMPION_NAMES.get(champ_id, str(champ_id))
        token = id(panel)

        def work():
            try:
                if kind == 'bans':
                    rows = fetch_bans(role, cfg['tier'], cfg['patch'])
                    items = [(r['champion_id'], f"{r['banrate']:.1f} % Bans") for r in rows]
                    title = f"Meistgebannt · {ROLE_LABELS.get(role, role)} · {cfg['patch']} Tage" if cfg['patch'].isdigit() else f"Meistgebannt · {ROLE_LABELS.get(role, role)}"
                else:
                    result = fetch_counters(name, role, cfg['tier'], cfg['patch'])
                    items = [(r['champion_id'], f"{r['winrate']:.1f} % WR") for r in result['counters']]
                    title = f"Hardcounter {name} ({result['lane']}) · WR von {name}"
                self.controller.emit({'type': 'suggestions', 'token': token, 'items': items, 'title': title, 'error': None})
            except (OSError, ValueError, KeyError) as error:
                logging.getLogger(__name__).info('Lolalytics-Vorschläge (%s) fehlgeschlagen: %s', kind, error)
                self.controller.emit({'type': 'suggestions', 'token': token, 'items': [], 'title': None,
                                      'error': 'Lolalytics nicht erreichbar oder keine Daten (Internet / Champion-Seite?)'})
        threading.Thread(target=work, daemon=True, name='LolalyticsSuggest').start()

    def _suggestions_done(self, message):
        if self._closed:
            return
        panels = [self.ban_suggest, self.active_bm_panel.suggest if self.active_bm_panel else None]
        panel = next((p for p in panels if p is not None and id(p) == message['token']), None)
        if panel is None:
            return  # closed in the meantime
        if message['error']:
            panel.set_error(message['error'])
        else:
            panel.set_items(message['items'], message['title'])
        self._resize_window()

    def _open_loadout(self, row):
        if self._loadout_window and self._loadout_window.win.winfo_exists():
            self._loadout_window.close()
        self._loadout_window = LoadoutWindow(self, row.champ_id)

    def apply_opacity(self):
        ingame = self.current_phase in INGAME_PHASES
        self.root.attributes('-alpha', self.opacity_ingame if ingame else self.opacity_default)

    def set_opacity(self, key, percent):
        setattr(self, key, max(0.2, min(1.0, int(percent) / 100)))
        self.apply_opacity()

    def _set_borders(self, rows, color):
        for row in rows:
            row.border_color = color
            if not self._dnd_state or self._dnd_state.get('row') is not row:
                row.outer.config(bg=color)

    def open_lolalytics(self):
        self.controller.open('base')

    def open_vs(self):
        self.controller.open('vs')

    def _open_settings(self):
        if self._settings_window and self._settings_window.win.winfo_exists():
            self._settings_window.win.lift()
            self._settings_window.win.focus_force()
        else:
            self._settings_window = SettingsWindow(self)

    def connection_status(self):
        names = ', '.join(self.browser_clients.values())
        return ('League verbunden' if self.connected else 'Warte auf League') + '\n' + (names or 'Browser-Brücke wartet auf Verbindung')

    def notice(self, text, duration=4000):
        if self._closed:
            return
        self.last_notice = text
        logging.getLogger(__name__).info(text)
        if self._settings_window and self._settings_window.win.winfo_exists():
            self._settings_window.show_message(text)
            return
        if self._toast and self._toast.winfo_exists():
            if self._toast_timer:
                self.root.after_cancel(self._toast_timer)
            self._toast.destroy()
        top = self._toast = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes('-topmost', True)
        top.attributes('-alpha', 0.92)
        top.configure(bg='#1a2a3a')
        label = tk.Label(top, text=text, bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 7),
                         wraplength=230, justify='left', padx=7, pady=5)
        label.pack(padx=1, pady=1)
        top.update_idletasks()
        x = max(0, min(self.root.winfo_x(), self.root.winfo_screenwidth() - top.winfo_reqwidth()))
        y = min(self.root.winfo_y() + self.root.winfo_height() + 4,
                self.root.winfo_screenheight() - top.winfo_reqheight())
        top.geometry(f'+{x}+{max(0, y)}')
        self._toast_timer = self.root.after(duration, lambda: top.destroy() if top.winfo_exists() else None)

    def _update_match(self):
        c = self.controller
        self.current_champion = c.champion or None
        self.current_role, self.current_queue_id = c.role, c.queue_id
        if self.current_champion:
            name = next((name for name in CHAMPION_NAMES.values() if name.lower().replace(' ', '').replace("'", '') == c.champion.lower()), c.champion)
            self.champ_label.config(text=f'{name} ({c.role})' if c.role else name)
            self._ensure_champ_frame_at_bottom()
        else:
            self.champ_frame.pack_forget()
            self.champ_label.config(text='')
        visible = bool(c.vs_url())
        if visible and not self._vs_visible:
            self.vs_btn.pack(side=tk.LEFT, padx=(4, 0))
        elif not visible:
            self.vs_btn.pack_forget()
        self._vs_visible = visible

    def process_queue(self):
        if self._closed:
            return
        pending = getattr(self, '_poll_id', None)
        if pending:
            self.root.after_cancel(pending)
        self._poll_id = None
        resize = False
        for _ in range(100):
            try:
                message = self.controller.events.get_nowait()
            except queue.Empty:
                break
            self.controller.handle(message)
            kind = message['type']
            if kind == 'status':
                self.connected = message['connected']
                self.status_label.config(text='Verbunden' if self.connected else 'Getrennt',
                                         fg='#d4b87a' if self.connected else '#e74c3c')
                self.status_canvas.itemconfig(self.status_dot, fill='#2ecc71' if self.connected else '#e74c3c')
            elif kind == 'phase':
                phase = self.current_phase = message['phase']
                display = 'Client' if phase in ('None', '', None) else phase
                bg, fg = {'ReadyCheck': ('#4a3a1a', '#f0a830'), 'ChampSelect': ('#1a3b4a', '#3a8fd4'),
                          'InProgress': ('#2e3a2e', '#2ecc71')}.get(display, ('#1a2a3a', '#c8aa6e'))
                self.phase_badge.config(text=display, bg=bg, fg=fg)
                self.apply_opacity()
                if phase in ('None', '', None, 'Lobby'):
                    self._set_borders(self.pick_rows, PICK_BORDER)
                    self._set_borders(self.ban_rows, BAN_BORDER)
                    for row in self.ban_rows:
                        row.set_hint('')
                    if self.hidden and phase == 'Lobby':
                        self.show_overlay()
                    if self._manual_role is not None and self._manual_role != self.list_role:
                        self._select_role(self._manual_role, manual=False)  # back to the list the player chose
                    self._manual_role = None
                elif phase == 'ChampSelect':
                    # Neutral grey frame on every row from the first second; colours follow with pick_status.
                    self._set_borders(self.pick_rows, NEUTRAL_BORDER)
                    self._set_borders(self.ban_rows, NEUTRAL_BORDER)
                self._update_match()
                resize = True
            elif kind in ('draft', 'live'):
                self._update_match()
                resize = True
            elif kind == 'pick_status' and self.current_phase == 'ChampSelect':
                self._follow_assigned_role(message.get('role', ''))
                for rows, status in ((self.pick_rows, message['status']), (self.ban_rows, message.get('ban_status', {}))):
                    for row in rows:
                        row.border_color = STATUS_SHADES.get(status.get(row.champ_id), NEUTRAL_BORDER)
                        if not self._dnd_state or self._dnd_state.get('row') is not row:
                            row.outer.config(bg=row.border_color)
                        if row.list_type == 'ban':
                            row.set_hint(BAN_HINTS.get(status.get(row.champ_id), ''))
            elif kind == 'browsers':
                self.browser_clients = message['clients']
                if self._settings_window:
                    self._settings_window.refresh_tracking()
            elif kind == 'notice':
                self.notice(message['text'])
            elif kind == 'suggestions':
                self._suggestions_done(message)
            elif kind == 'import_done':
                self._import_finished(message['results'], message['failed'], message['done'])
        if resize:
            self._resize_window()
        self._poll_id = self.root.after(50, self.process_queue)

    def quit(self):
        if self._closed:
            return
        self._closed = True
        if self._settings_window:
            self._settings_window.close()
        if self._loadout_window:
            self._loadout_window.close()
        self.hotkey_manager.close()
        self.controller.close()
        if self._toast_timer:
            self.root.after_cancel(self._toast_timer)
        if self._poll_id:
            self.root.after_cancel(self._poll_id)
        self.root.destroy()

    close = quit