import logging
import queue
import tkinter as tk

from .hotkeys import Hotkeys
from .settings_ui import SettingsWindow
from .ui_layout import ClassicOverlay
from .ui_widgets import CHAMPION_NAMES, PICK_BORDER, ROW_BG


class App(ClassicOverlay):
    SETTINGS = ('auto_ready_enabled', 'auto_pick_enabled', 'auto_pick_champs',
                'auto_ban_champs', 'auto_pick_minimized', 'bad_matchups',
                'hotkeys', 'weak_pc_mode', 'debug_mode', 'live_tracking')

    def __init__(self, root, controller):
        self.controller = controller
        self._settings_window = None
        self._toast = None
        self._toast_timer = None
        self._closed = False
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

    def save_config(self):
        changes = {key: getattr(self, key) for key in self.SETTINGS}
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
                   'close_all_browsers': lambda: self.controller.enqueue('close_browsers', all_clients=True)}
        if action in actions:
            actions[action]()

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
                if phase in ('None', '', None, 'Lobby'):
                    for row in self.pick_rows:
                        row.border_color = PICK_BORDER
                        row.outer.config(bg=PICK_BORDER)
                    if self.hidden and phase == 'Lobby':
                        self.show_overlay()
                self._update_match()
                resize = True
            elif kind in ('draft', 'live'):
                self._update_match()
                resize = True
            elif kind == 'pick_status' and self.current_phase == 'ChampSelect':
                shades = {'banned': '#33ff00', 'bad_matchup': '#ffd900', 'hovered': '#3a8fd4'}
                for row in self.pick_rows:
                    row.border_color = shades.get(message['status'].get(row.champ_id), '#818181')
                    if not self._dnd_state or self._dnd_state.get('row') is not row:
                        row.outer.config(bg=row.border_color)
            elif kind == 'browsers':
                self.browser_clients = message['clients']
                if self._settings_window:
                    self._settings_window.refresh_tracking()
            elif kind == 'notice':
                self.notice(message['text'])
            elif kind == 'browsers_closed' and message.get('count'):
                self.notice('Fokus an. Tabs aus.', 1200)
        if resize:
            self._resize_window()
        self._poll_id = self.root.after(50, self.process_queue)

    def quit(self):
        if self._closed:
            return
        self._closed = True
        if self._settings_window:
            self._settings_window.close()
        self.hotkey_manager.close()
        self.controller.close()
        if self._toast_timer:
            self.root.after_cancel(self._toast_timer)
        if self._poll_id:
            self.root.after_cancel(self._poll_id)
        self.root.destroy()

    close = quit