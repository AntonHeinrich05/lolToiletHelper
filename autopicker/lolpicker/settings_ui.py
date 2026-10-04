import tkinter as tk

from .hotkeys import combo_from_event
from .settings_layout import ClassicSettings
from .storage import DEFAULT_HOTKEYS


class SettingsWindow(ClassicSettings):
    def __init__(self, app):
        super().__init__(app)
        self.win.protocol('WM_DELETE_WINDOW', self.close)
        self.win.bind('<Escape>', self._escape, add='+')
        self.message = None
        self._message_timer = None
        self.refresh_buttons()
        self.win.update_idletasks()
        height = max(400, self.win.winfo_reqheight())
        self.win.geometry(f'320x{height}+{self.win.winfo_x()}+{self.win.winfo_y()}')

    def _build_tracking(self, row):
        self.track_btn = tk.Label(row, fg='#f0e6d2', font=('Consolas', 8, 'bold'),
                                  padx=10, pady=2, cursor='hand2')
        self.track_btn.pack(side=tk.RIGHT)
        self.track_btn.bind('<Button-1>', lambda _: self._toggle_tracking())
        self.track_btn.bind('<Button-3>', lambda _: self.app.notice(self.app.connection_status()))
        self.refresh_tracking()

    def refresh_tracking(self):
        if not self.win.winfo_exists():
            return
        on = self.app.live_tracking
        ready = bool(self.app.controller.bridge.listing())
        self.track_btn.config(text='AKTIV' if on and ready else 'WARTE' if on else 'AUS',
                              bg=self._weak_bg(on and ready))

    def show_message(self, text):
        if self._message_timer:
            self.win.after_cancel(self._message_timer)
        if self.message is not None and self.message.winfo_exists():
            self.message.destroy()
        self.message = tk.Label(self.win, text=text, bg=self.BG_PANEL, fg=self.ACCENT,
                                font=('Segoe UI', 7), wraplength=288, justify='left', padx=6, pady=4)
        self.message.place(relx=0.5, rely=1, anchor='s', relwidth=0.97, y=-1)
        message = self.message
        self._message_timer = self.win.after(5000, lambda: message.destroy() if message.winfo_exists() else None)

    def refresh_buttons(self):
        for action, button in self.row_buttons.items():
            registered = action in self.app.hotkey_manager.ids.values()
            button.config(text=self._format_hotkey(self.app.hotkeys.get(action, '')),
                          bg=self.BTN_BG, fg='#f0e6d2' if registered else self.DIM_FG)

    def _toggle_tracking(self):
        self.app.live_tracking = not self.app.live_tracking
        self.app.save_config()
        self.refresh_tracking()

    def _toggle_weak_pc(self):
        self.app.weak_pc_mode = not self.app.weak_pc_mode
        self.app.save_config()
        self.weak_btn.config(text=self._weak_label(self.app.weak_pc_mode), bg=self._weak_bg(self.app.weak_pc_mode))

    def _toggle_debug(self):
        self.app.debug_mode = not self.app.debug_mode
        self.app.save_config()
        self.debug_btn.config(text=self._weak_label(self.app.debug_mode), bg=self._weak_bg(self.app.debug_mode))

    def _cancel_recording(self):
        if self._recording:
            self._recording = None
            try:
                self.app.hotkey_manager.apply(self.app.hotkeys)
            except ValueError as error:
                self.show_message(str(error))
        self.app.hotkey_manager.suspended = False
        self.refresh_buttons()

    def _start_recording(self, action):
        self._cancel_recording()
        self._recording = action
        self.app.hotkey_manager.suspended = True
        self.app.hotkey_manager._clear()
        self.row_buttons[action].config(text='►  Taste druecken ...', bg=self.REC_BG)
        self.win.focus_force()

    def _on_keypress(self, event):
        if not self._recording:
            return
        if event.keysym == 'Escape':
            self._cancel_recording()
            return 'break'
        try:
            combo = combo_from_event(event)
            if combo:
                updated = dict(self.app.hotkeys)
                updated[self._recording] = combo
                self.commit(updated)
        except ValueError as error:
            self.show_message(str(error))
        return 'break'

    def commit(self, updated):
        old = dict(self.app.hotkeys)
        try:
            self.app.hotkey_manager.apply(updated)
            self.app.hotkeys = updated
            if not self.app.save_config():
                raise ValueError('Nicht gespeichert; bisheriges Kürzel bleibt aktiv')
        except ValueError as error:
            self.app.hotkeys = old
            try:
                self.app.hotkey_manager.apply(old)
            except ValueError as restore_error:
                self.show_message(f'{error}\n{restore_error}')
            else:
                self.show_message(str(error))
        finally:
            self._recording = None
            self.app.hotkey_manager.suspended = False
            self.refresh_buttons()

    def _reset_defaults(self):
        self.commit(dict(DEFAULT_HOTKEYS))

    def _escape(self, _):
        if self._recording:
            self._cancel_recording()
        return 'break'

    def close(self):
        self._cancel_recording()
        if self._message_timer:
            self.win.after_cancel(self._message_timer)
        self.win.destroy()
        self.app._settings_window = None