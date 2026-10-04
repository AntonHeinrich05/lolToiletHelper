import tkinter as tk
import queue
from .ui_widgets import ROW_BG, FONT_ROW, FONT_ROW_SMALL, FONT_ENTRY, FONT_ENTRY_SMALL, PICK_BORDER, DRAG_BORDER, PICK_PLACEHOLDER, BAN_PLACEHOLDER, PLACEHOLDER_FG, ACTIVE_FG, CHAMPION_NAMES, NAME_TO_ID, NORM_NAMES, find_matches, ChampRow, BadMatchupsPanel

class ClassicOverlay:

    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.geometry('220x80+100+100')
        self.root.configure(bg=ROW_BG)
        self.root.withdraw()
        self._drag_x = 0
        self._drag_y = 0
        self.auto_ready_enabled = True
        self.current_champion = None
        self.current_role = ''
        self.current_queue_id = 0
        self.current_phase = None
        self.enemy_roster = []
        self.my_cell_id = None
        self.my_team_cells = []
        self.data_queue = queue.Queue()
        self.hidden = False
        self.auto_pick_enabled = False
        self.auto_pick_champs = []
        self.auto_ban_champs = []
        self.auto_pick_minimized = True
        self.bad_matchups = {}
        self.pick_rows = []
        self.ban_rows = []
        self.editing_row = None
        self.editing_bm = None
        self._dnd_state = None
        self._bm_dnd_state = None
        self._pick_focusout_after = None
        self._ban_focusout_after = None
        self._edit_focusout_after = None
        self.active_bm_panel = None
        self.loadouts = {}
        self.opacity_default, self.opacity_ingame = 0.75, 0.5
        self.load_config()
        self.root.attributes('-alpha', self.opacity_default)
        self.top_frame = tk.Frame(self.root, bg=ROW_BG, height=18)
        self.top_frame.pack(fill=tk.X, padx=4, pady=(3, 0))
        self.top_frame.bind('<Button-1>', self.start_drag)
        self.top_frame.bind('<B1-Motion>', self.drag)
        self.status_canvas = tk.Canvas(self.top_frame, width=6, height=6, bg=ROW_BG, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 3))
        self.status_dot = self.status_canvas.create_oval(0, 0, 6, 6, fill='#f0a830', outline='')
        self.status_canvas.bind('<Button-1>', self.start_drag)
        self.status_canvas.bind('<B1-Motion>', self.drag)
        self.status_label = tk.Label(self.top_frame, text='Verbinde...', bg=ROW_BG, fg='#b0a88a', font=('Segoe UI', 7))
        self.status_label.pack(side=tk.LEFT)
        self.status_label.bind('<Button-1>', self.start_drag)
        self.status_label.bind('<B1-Motion>', self.drag)
        self.exit_btn = tk.Label(self.top_frame, text='✕', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 9, 'bold'), cursor='hand2')
        self.exit_btn.pack(side=tk.RIGHT)
        self.exit_btn.bind('<Button-1>', lambda e: self.quit())
        self.exit_btn.bind('<Enter>', lambda e: self.exit_btn.config(fg='#f0e6d2'))
        self.exit_btn.bind('<Leave>', lambda e: self.exit_btn.config(fg='#c8aa6e'))
        self.min_btn = tk.Label(self.top_frame, text='–', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 9, 'bold'), cursor='hand2')
        self.min_btn.pack(side=tk.RIGHT, padx=(0, 2))
        self.min_btn.bind('<Button-1>', lambda e: self.hide_overlay())
        self.min_btn.bind('<Enter>', lambda e: self.min_btn.config(fg='#f0e6d2'))
        self.min_btn.bind('<Leave>', lambda e: self.min_btn.config(fg='#c8aa6e'))
        self.settings_btn = tk.Label(self.top_frame, text='⋮', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 12, 'bold'), cursor='hand2')
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 4))
        self.settings_btn.bind('<Button-1>', lambda e: self._open_settings())
        self.settings_btn.bind('<Enter>', lambda e: self.settings_btn.config(fg='#f0e6d2'))
        self.settings_btn.bind('<Leave>', lambda e: self.settings_btn.config(fg='#c8aa6e'))
        self.phase_badge = tk.Label(self.top_frame, text='Client', bg='#1a2a3a', fg='#c8aa6e', font=('Segoe UI', 7, 'bold'), padx=5, pady=0)
        self.phase_badge.pack(side=tk.RIGHT, padx=(0, 4))
        self.phase_badge.bind('<Button-1>', self.start_drag)
        self.phase_badge.bind('<B1-Motion>', self.drag)
        self.auto_ready_var = tk.BooleanVar(value=True)
        self.auto_ready_check = tk.Checkbutton(self.root, text='Auto‑Ready', variable=self.auto_ready_var, command=self.toggle_auto_ready, bg=ROW_BG, fg='#d4b87a', selectcolor=ROW_BG, activebackground=ROW_BG, font=('Segoe UI', 7), relief='flat')
        self.auto_ready_check.pack(anchor=tk.W, padx=4, pady=(2, 0))
        self.auto_pick_frame = tk.Frame(self.root, bg=ROW_BG)
        self.auto_pick_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.auto_pick_toggle_var = tk.BooleanVar(value=self.auto_pick_enabled)
        self.auto_pick_check = tk.Checkbutton(self.auto_pick_frame, text='Auto-Pick&Ban', variable=self.auto_pick_toggle_var, command=self.toggle_auto_pick, bg=ROW_BG, fg='#d4b87a', selectcolor=ROW_BG, activebackground=ROW_BG, font=('Segoe UI', 7), relief='flat')
        self.auto_pick_check.pack(side=tk.LEFT)
        self.auto_pick_min_btn = tk.Label(self.auto_pick_frame, text='+', bg=ROW_BG, fg='#c8aa6e', font=('Segoe UI', 9, 'bold'), cursor='hand2')
        self.auto_pick_min_btn.pack(side=tk.RIGHT)
        self.auto_pick_min_btn.bind('<Button-1>', lambda e: self.toggle_auto_pick_minimize())
        self.auto_pick_min_btn.bind('<Enter>', lambda e: self.auto_pick_min_btn.config(fg='#f0e6d2'))
        self.auto_pick_min_btn.bind('<Leave>', lambda e: self.auto_pick_min_btn.config(fg='#c8aa6e'))
        self.auto_pick_content_frame = tk.Frame(self.root, bg=ROW_BG)
        self.pick_search_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)
        self.pick_search_entry = self._make_search_entry(self.pick_search_frame, 'pick', PICK_PLACEHOLDER)
        self.pick_suggestions_listbox = self._make_suggestions_listbox(self.pick_search_frame, 'pick')
        self.pick_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.pick_champ_list_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)
        self.ban_search_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)
        self.ban_search_entry = self._make_search_entry(self.ban_search_frame, 'ban', BAN_PLACEHOLDER)
        self.ban_suggestions_listbox = self._make_suggestions_listbox(self.ban_search_frame, 'ban')
        self.ban_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.ban_champ_list_frame = tk.Frame(self.auto_pick_content_frame, bg=ROW_BG)
        self.auto_pick_content_frame.pack(anchor=tk.W, fill=tk.X)
        self.auto_pick_content_frame.pack_forget()
        self.champ_frame = tk.Frame(self.root, bg=ROW_BG, height=16)
        self.champ_label = tk.Label(self.champ_frame, text='', bg=ROW_BG, fg='#f0e6d2', font=FONT_ROW)
        self.champ_label.pack(side=tk.LEFT, padx=(0, 3))
        self.lolalytics_btn = tk.Label(self.champ_frame, text='LoLalytics', bg='#1a5a8a', fg='#ffffff', font=FONT_ROW, padx=6, pady=0, cursor='hand2')
        self.lolalytics_btn.pack(side=tk.LEFT)
        self.lolalytics_btn.bind('<Button-1>', lambda e: self.open_lolalytics())
        self.lolalytics_btn.bind('<Enter>', lambda e: self.lolalytics_btn.config(bg='#1d7bb0'))
        self.lolalytics_btn.bind('<Leave>', lambda e: self.lolalytics_btn.config(bg='#1a5a8a'))
        self.vs_btn = tk.Label(self.champ_frame, text='VS', bg='#a01818', fg='#ffffff', font=FONT_ROW, padx=6, pady=0, cursor='hand2')
        self.vs_btn.bind('<Button-1>', lambda e: self.open_vs())
        self.vs_btn.bind('<Enter>', lambda e: self.vs_btn.config(bg='#c41f1f'))
        self.vs_btn.bind('<Leave>', lambda e: self.vs_btn.config(bg='#a01818'))
        self._vs_visible = False
        for cid in self.auto_pick_champs:
            self.pick_rows.append(ChampRow(self, self.pick_champ_list_frame, 'pick'))
        for cid in self.auto_ban_champs:
            self.ban_rows.append(ChampRow(self, self.ban_champ_list_frame, 'ban'))
        self._refresh_row_data('pick')
        self._refresh_row_data('ban')
        self.update_min_btn_text()
        if self.auto_pick_enabled and (not self.auto_pick_minimized):
            self.auto_pick_toggle_var.set(True)
            self.show_auto_pick_widgets()
            self._arrange_content()
        elif self.auto_pick_enabled:
            self.auto_pick_toggle_var.set(True)
        self.root.bind_all('<Button-1>', self._on_global_click, add='+')
        self._resize_window()

    def _make_search_entry(self, parent, list_type, placeholder):
        e = tk.Entry(parent, bg='#1a2a3a', fg=PLACEHOLDER_FG, insertbackground='#ffffff', font=FONT_ENTRY, relief='flat', borderwidth=0, selectbackground='#1a2a3a', selectforeground=PLACEHOLDER_FG, highlightthickness=0)
        e.pack(fill=tk.X, padx=2, pady=1)
        self._set_placeholder(e, placeholder)
        e.bind('<KeyPress>', lambda ev: self._on_search_keypress(ev, list_type))
        e.bind('<KeyRelease>', lambda ev: self._on_search_keyrelease(ev, list_type))
        e.bind('<FocusIn>', lambda ev: self._on_search_focusin(list_type))
        e.bind('<FocusOut>', lambda ev: self._on_search_focusout(list_type))
        e.bind('<Button-1>', lambda ev: self._on_search_click(ev, list_type))
        e.bind('<Double-Button-1>', lambda ev: self._on_search_dblclick(ev, list_type))
        e.bind('<Return>', lambda ev: self._on_search_enter(list_type))
        e.bind('<Down>', lambda ev: self._on_search_arrow(list_type, 1))
        e.bind('<Up>', lambda ev: self._on_search_arrow(list_type, -1))
        return e

    def _make_suggestions_listbox(self, parent, list_type):
        lb = tk.Listbox(parent, bg='#0a1a2b', fg='#c8aa6e', font=FONT_ENTRY, height=4, borderwidth=0, highlightthickness=0, selectbackground='#2a3a4a', selectforeground='#f0e6d2', activestyle='none', exportselection=False)
        lb.pack_forget()
        lb.bind('<Button-1>', lambda e: self._on_listbox_click(e, list_type))
        lb.bind('<Double-Button-1>', lambda e: self._on_listbox_click(e, list_type, True))
        return lb

    def _is_placeholder(self, entry, placeholder):
        return entry.get() == placeholder and entry.cget('fg') == PLACEHOLDER_FG

    def _set_placeholder(self, entry, placeholder):
        entry.delete(0, tk.END)
        entry.insert(0, placeholder)
        entry.config(fg=PLACEHOLDER_FG)
        entry.icursor(0)

    def _placeholder_for(self, list_type):
        return PICK_PLACEHOLDER if list_type == 'pick' else BAN_PLACEHOLDER

    def _entry_for(self, list_type):
        return self.pick_search_entry if list_type == 'pick' else self.ban_search_entry

    def _listbox_for(self, list_type):
        return self.pick_suggestions_listbox if list_type == 'pick' else self.ban_suggestions_listbox

    def _rows_for(self, list_type):
        return self.pick_rows if list_type == 'pick' else self.ban_rows

    def _champs_for(self, list_type):
        return self.auto_pick_champs if list_type == 'pick' else self.auto_ban_champs

    def _list_frame_for(self, list_type):
        return self.pick_champ_list_frame if list_type == 'pick' else self.ban_champ_list_frame

    def toggle_overlay(self):
        if self.hidden:
            self.show_overlay()
        else:
            self.hide_overlay()

    def hide_overlay(self):
        self.hidden = True
        self.root.withdraw()

    def show_overlay(self):
        if self.hidden:
            self.root.deiconify()
            self.root.attributes('-topmost', True)
            self.root.lift()
            self.hidden = False

    def _resize_window(self):
        if self.hidden:
            return
        self.root.update_idletasks()
        w = max(self.root.winfo_reqwidth(), 220)
        h = max(self.root.winfo_reqheight(), 80)
        self.root.geometry(f'{w}x{h}+{self.root.winfo_x()}+{self.root.winfo_y()}')

    def update_min_btn_text(self):
        self.auto_pick_min_btn.config(text='–' if self.auto_pick_enabled and (not self.auto_pick_minimized) else '+')

    def _ensure_champ_frame_at_bottom(self):
        if self.hidden:
            return
        if self.current_champion:
            self.champ_frame.pack_forget()
            self.champ_frame.pack(anchor=tk.W, padx=4, pady=(4, 6))

    def _arrange_content(self):
        self.pick_search_frame.pack_forget()
        self.pick_champ_list_frame.pack_forget()
        self.ban_search_frame.pack_forget()
        self.ban_champ_list_frame.pack_forget()
        self.pick_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        if self.auto_pick_champs:
            self.pick_champ_list_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self.ban_search_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        if self.auto_ban_champs:
            self.ban_champ_list_frame.pack(anchor=tk.W, fill=tk.X, padx=4, pady=(2, 0))
        self._ensure_champ_frame_at_bottom()
        if self.active_bm_panel is not None:
            self._pack_bm_panel(self.active_bm_panel)

    def toggle_auto_pick(self):
        self.auto_pick_enabled = self.auto_pick_toggle_var.get()
        self.save_config()
        if self.auto_pick_enabled:
            self.auto_pick_minimized = False
            self.show_auto_pick_widgets()
            self._arrange_content()
            self._refresh_row_data('pick')
            self._refresh_row_data('ban')
            self.pick_search_entry.focus_set()
        else:
            self._close_bm_panel()
            self.hide_auto_pick_widgets()
        self.update_min_btn_text()
        self._ensure_champ_frame_at_bottom()
        self._resize_window()

    def show_auto_pick_widgets(self):
        self.auto_pick_content_frame.pack(anchor=tk.W, fill=tk.X)
        self._set_placeholder(self.pick_search_entry, PICK_PLACEHOLDER)
        self._set_placeholder(self.ban_search_entry, BAN_PLACEHOLDER)
        self.pick_suggestions_listbox.pack_forget()
        self.ban_suggestions_listbox.pack_forget()

    def hide_auto_pick_widgets(self):
        self._close_bm_panel()
        self.auto_pick_content_frame.pack_forget()
        self.pick_suggestions_listbox.pack_forget()
        self.ban_suggestions_listbox.pack_forget()

    def toggle_auto_pick_minimize(self):
        if not self.auto_pick_enabled:
            self.auto_pick_toggle_var.set(True)
            self.toggle_auto_pick()
            return
        self.auto_pick_minimized = not self.auto_pick_minimized
        self.save_config()
        self.update_min_btn_text()
        if self.auto_pick_minimized:
            self.hide_auto_pick_widgets()
        else:
            self.show_auto_pick_widgets()
            self._arrange_content()
            self._refresh_row_data('pick')
            self._refresh_row_data('ban')
            self.pick_search_entry.focus_set()
        self._ensure_champ_frame_at_bottom()
        self._resize_window()

    def _refresh_row_data(self, list_type):
        rows = self._rows_for(list_type)
        champs = self._champs_for(list_type)
        while len(rows) < len(champs):
            rows.append(ChampRow(self, self._list_frame_for(list_type), list_type))
        while len(rows) > len(champs):
            extra = rows.pop()
            extra.destroy()
        for i, (row, cid) in enumerate(zip(rows, champs), 1):
            row.set_data(cid, i)
            row.outer.pack_forget()
            row.outer.pack(fill=tk.X, pady=1)

    def _add_champ(self, list_type, champ_id):
        champs = self._champs_for(list_type)
        if len(champs) >= 5 or champ_id in champs:
            return
        champs.append(champ_id)
        rows = self._rows_for(list_type)
        new_row = ChampRow(self, self._list_frame_for(list_type), list_type)
        new_row.set_data(champ_id, len(champs))
        new_row.outer.pack(fill=tk.X, pady=1)
        rows.append(new_row)
        self._arrange_content()
        self.save_config()
        self._resize_window()

    def _delete_row(self, row):
        list_type = row.list_type
        rows = self._rows_for(list_type)
        champs = self._champs_for(list_type)
        if row not in rows:
            return
        idx = rows.index(row)
        if self.editing_row is row:
            self._cancel_edit(row)
        if self.active_bm_panel is not None and self.active_bm_panel.owner_row is row:
            self._close_bm_panel()
        rows.pop(idx)
        champs.pop(idx)
        row.destroy()
        for i, r in enumerate(rows, 1):
            r.set_index(i)
        if not champs:
            self._list_frame_for(list_type).pack_forget()
        self.save_config()
        self._resize_window()

    def _edit_row(self, row):
        self.pick_suggestions_listbox.pack_forget()
        self.ban_suggestions_listbox.pack_forget()
        if self.editing_row is not None and self.editing_row is not row:
            self._commit_edit(self.editing_row)
        if self.editing_row is row:
            return
        row.lbl.pack_forget()
        row.edit_entry = tk.Entry(row.inner, bg=ROW_BG, fg=ACTIVE_FG, insertbackground='#ffffff', font=FONT_ROW, relief='flat', borderwidth=0, selectbackground=ROW_BG, selectforeground=ACTIVE_FG, highlightthickness=0)
        old_name = CHAMPION_NAMES.get(row.champ_id, '')
        row.edit_entry.insert(0, old_name)
        row.edit_entry.icursor(0)
        anchor_btn = row.dots_btn if row.dots_btn is not None else row.del_btn
        row.edit_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, before=anchor_btn)
        row.is_initial_edit_replace = True
        row.edit_list_frame = tk.Frame(row.outer.master, bg=ROW_BG)
        row.edit_listbox = tk.Listbox(row.edit_list_frame, bg='#0a1a2b', fg='#c8aa6e', font=FONT_ENTRY, height=0, borderwidth=0, highlightthickness=0, selectbackground='#2a3a4a', selectforeground='#f0e6d2', activestyle='none', exportselection=False)
        row.edit_listbox.pack(fill=tk.X)
        row.edit_listbox.pack_forget()
        row.edit_list_frame.pack_forget()
        row.edit_entry.bind('<KeyPress>', lambda e, r=row: self._on_edit_keypress(e, r))
        row.edit_entry.bind('<KeyRelease>', lambda e, r=row: self._on_edit_keyrelease(e, r))
        row.edit_entry.bind('<Return>', lambda e, r=row: self._commit_edit(r))
        row.edit_entry.bind('<Escape>', lambda e, r=row: self._cancel_edit(r))
        row.edit_entry.bind('<Down>', lambda e, r=row: self._listbox_navigate(r.edit_listbox, 1))
        row.edit_entry.bind('<Up>', lambda e, r=row: self._listbox_navigate(r.edit_listbox, -1))
        row.edit_entry.bind('<FocusOut>', lambda e, r=row: self._on_edit_focusout(r))
        row.edit_listbox.bind('<Button-1>', lambda e, r=row: self._on_edit_listbox_click(e, r))
        row.edit_listbox.bind('<Double-Button-1>', lambda e, r=row: self._on_edit_listbox_click(e, r))
        row.edit_entry.focus_set()
        self.editing_row = row
        self._resize_window()

    def _on_edit_keypress(self, event, row):
        if row.is_initial_edit_replace and event.char and (len(event.char) == 1) and event.char.isprintable():
            row.edit_entry.delete(0, tk.END)
            row.edit_entry.insert(0, event.char)
            row.edit_entry.icursor(1)
            row.is_initial_edit_replace = False
            return 'break'
        if event.keysym in ('BackSpace', 'Delete'):
            row.is_initial_edit_replace = False
        return None

    def _on_edit_keyrelease(self, event, row):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Left', 'Right'):
            return
        row.edit_listbox.delete(0, tk.END)
        matches = find_matches(row.edit_entry.get())
        if not matches:
            row.edit_list_frame.pack_forget()
            self._resize_window()
            return
        if matches:
            num = min(len(matches), 5)
            row.edit_listbox.config(height=num)
            for m in matches[:num]:
                row.edit_listbox.insert(tk.END, m)
            if not row.edit_list_frame.winfo_ismapped():
                row.edit_list_frame.pack(after=row.outer, fill=tk.X, pady=(0, 2))
                row.edit_listbox.pack(fill=tk.X)
        else:
            row.edit_list_frame.pack_forget()
        self._resize_window()

    def _on_edit_focusout(self, row):
        if self._edit_focusout_after is not None:
            try:
                self.root.after_cancel(self._edit_focusout_after)
            except Exception:
                pass
        self._edit_focusout_after = self.root.after(150, lambda: self._commit_edit(row))

    def _on_edit_listbox_click(self, event, row):
        if self._edit_focusout_after is not None:
            try:
                self.root.after_cancel(self._edit_focusout_after)
            except Exception:
                pass
            self._edit_focusout_after = None
        try:
            idx = row.edit_listbox.nearest(event.y)
            row.edit_listbox.selection_clear(0, tk.END)
            row.edit_listbox.selection_set(idx)
            row.edit_listbox.activate(idx)
        except Exception:
            pass
        self._commit_edit(row)
        return 'break'

    def _commit_edit(self, row):
        if self.editing_row is not row or row.edit_entry is None:
            return
        if self._edit_focusout_after is not None:
            try:
                self.root.after_cancel(self._edit_focusout_after)
            except Exception:
                pass
            self._edit_focusout_after = None
        sel = row.edit_listbox.curselection()
        if sel:
            name = row.edit_listbox.get(sel[0])
        elif row.edit_listbox.size() > 0:
            name = row.edit_listbox.get(0)
        else:
            name = row.edit_entry.get().strip()
        norm = name.lower().replace(' ', '').replace("'", '')
        new_id = NORM_NAMES.get(norm, (None, None))[1]
        champs = self._champs_for(row.list_type)
        rows = self._rows_for(row.list_type)
        idx = rows.index(row)
        old_id = row.champ_id
        if new_id is not None and (new_id == old_id or new_id not in champs):
            champs[idx] = new_id
            self.save_config()
        self._cancel_edit(row)
        row.set_data(champs[idx], idx + 1)

    def _cancel_edit(self, row):
        if row.edit_entry is None:
            return
        try:
            row.edit_entry.destroy()
        except Exception:
            pass
        row.edit_entry = None
        try:
            if row.edit_list_frame is not None:
                row.edit_list_frame.destroy()
        except Exception:
            pass
        row.edit_list_frame = None
        row.edit_listbox = None
        anchor_btn = row.dots_btn if row.dots_btn is not None else row.del_btn
        row.lbl.pack(side=tk.LEFT, before=anchor_btn)
        if self.editing_row is row:
            self.editing_row = None
        self._resize_window()

    def _on_search_keypress(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            if event.char and len(event.char) == 1 and event.char.isprintable():
                entry.delete(0, tk.END)
                entry.config(fg=ACTIVE_FG)
                entry.insert(0, event.char)
                entry.icursor(1)
                return 'break'
            if event.keysym not in ('Tab', 'Escape'):
                return 'break'
        return None

    def _on_search_keyrelease(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        listbox = self._listbox_for(list_type)
        if entry.get() == '':
            if not self._is_placeholder(entry, placeholder):
                self._set_placeholder(entry, placeholder)
            listbox.pack_forget()
            self._resize_window()
            return
        if event.keysym in ('Up', 'Down', 'Return', 'Left', 'Right', 'Escape'):
            return
        self._update_suggestions(list_type)

    def _on_search_click(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            self.root.after_idle(lambda: entry.icursor(0))
        return None

    def _on_search_dblclick(self, event, list_type):
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            entry.selection_clear()
            entry.icursor(0)
            return 'break'
        return None

    def _on_search_focusin(self, list_type):
        attr = '_pick_focusout_after' if list_type == 'pick' else '_ban_focusout_after'
        pending = getattr(self, attr)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
            setattr(self, attr, None)
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            entry.icursor(0)
            return
        if entry.get().strip():
            self._update_suggestions(list_type)

    def _on_search_focusout(self, list_type):
        attr = '_pick_focusout_after' if list_type == 'pick' else '_ban_focusout_after'
        pending = getattr(self, attr)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
        setattr(self, attr, self.root.after(150, lambda: self._hide_suggestions(list_type)))

    def _hide_suggestions(self, list_type):
        self._listbox_for(list_type).pack_forget()
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if entry.get().strip() == '':
            self._set_placeholder(entry, placeholder)
        self._resize_window()

    def _update_suggestions(self, list_type):
        entry = self._entry_for(list_type)
        listbox = self._listbox_for(list_type)
        placeholder = self._placeholder_for(list_type)
        if self._is_placeholder(entry, placeholder):
            listbox.pack_forget()
            return
        listbox.delete(0, tk.END)
        matches = find_matches(entry.get())
        if not matches:
            listbox.pack_forget()
            self._resize_window()
            return
        if matches:
            num = min(len(matches), 5)
            listbox.config(height=num)
            for m in matches[:num]:
                listbox.insert(tk.END, m)
            if not listbox.winfo_ismapped():
                listbox.pack(anchor=tk.W, padx=4, pady=(0, 2))
        else:
            listbox.pack_forget()
        self._resize_window()

    def _on_search_enter(self, list_type):
        self._confirm_search(list_type)
        return 'break'

    def _on_search_arrow(self, list_type, direction):
        self._listbox_navigate(self._listbox_for(list_type), direction)
        return 'break'

    def _on_listbox_click(self, event, list_type, double=False):
        listbox = self._listbox_for(list_type)
        try:
            idx = listbox.nearest(event.y)
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(idx)
            listbox.activate(idx)
        except Exception:
            pass
        attr = '_pick_focusout_after' if list_type == 'pick' else '_ban_focusout_after'
        pending = getattr(self, attr)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
            setattr(self, attr, None)
        self._confirm_search(list_type)
        return 'break'

    def _confirm_search(self, list_type):
        listbox = self._listbox_for(list_type)
        entry = self._entry_for(list_type)
        placeholder = self._placeholder_for(list_type)
        sel = listbox.curselection()
        if sel:
            name = listbox.get(sel[0])
        elif listbox.size() > 0:
            name = listbox.get(0)
        else:
            name = entry.get().strip()
        if name in NAME_TO_ID:
            self._add_champ(list_type, NAME_TO_ID[name])
            entry.delete(0, tk.END)
            self._set_placeholder(entry, placeholder)
            listbox.pack_forget()
            self._resize_window()

    def _listbox_navigate(self, listbox, direction):
        try:
            if listbox is None or not listbox.winfo_ismapped():
                return 'break'
        except tk.TclError:
            return 'break'
        size = listbox.size()
        if size == 0:
            return 'break'
        current = listbox.curselection()
        if not current:
            new_idx = 0 if direction > 0 else size - 1
        else:
            new_idx = max(0, min(size - 1, current[0] + direction))
        listbox.selection_clear(0, tk.END)
        listbox.selection_set(new_idx)
        listbox.activate(new_idx)
        listbox.see(new_idx)
        return 'break'

    def _dnd_start(self, event, row):
        if self.editing_row is row:
            return
        rows = self._rows_for(row.list_type)
        if row not in rows:
            return
        self._dnd_state = {'row': row, 'moved': False, 'highlighted': False, 'list_type': row.list_type, 'start_x': event.x_root, 'start_y': event.y_root}

    def _dnd_motion(self, event, row):
        state = self._dnd_state
        if not state or state['row'] is not row:
            return
        if not state['highlighted']:
            dx = abs(event.x_root - state['start_x'])
            dy = abs(event.y_root - state['start_y'])
            if dx + dy < 3:
                return
            row.set_dragged(True)
            state['highlighted'] = True
        rows = self._rows_for(row.list_type)
        if row not in rows:
            return
        current_idx = rows.index(row)
        parent = self._list_frame_for(row.list_type)
        try:
            pointer_y = parent.winfo_pointery() - parent.winfo_rooty()
        except tk.TclError:
            return
        if current_idx + 1 < len(rows):
            below = rows[current_idx + 1]
            try:
                mid = below.outer.winfo_y() + below.outer.winfo_height() / 2
            except tk.TclError:
                return
            if pointer_y > mid:
                self._dnd_swap(row, current_idx, current_idx + 1)
                return
        if current_idx - 1 >= 0:
            above = rows[current_idx - 1]
            try:
                mid = above.outer.winfo_y() + above.outer.winfo_height() / 2
            except tk.TclError:
                return
            if pointer_y < mid:
                self._dnd_swap(row, current_idx, current_idx - 1)
                return

    def _dnd_swap(self, dragged_row, from_idx, to_idx):
        list_type = dragged_row.list_type
        rows = self._rows_for(list_type)
        champs = self._champs_for(list_type)
        champs[from_idx], champs[to_idx] = (champs[to_idx], champs[from_idx])
        rows[from_idx], rows[to_idx] = (rows[to_idx], rows[from_idx])
        new_idx = rows.index(dragged_row)
        if new_idx == 0:
            dragged_row.outer.pack(fill=tk.X, pady=1, before=rows[1].outer)
        else:
            dragged_row.outer.pack(fill=tk.X, pady=1, after=rows[new_idx - 1].outer)
        for i, r in enumerate(rows, 1):
            r.set_index(i)
        dragged_row.set_dragged(True)
        self._dnd_state['moved'] = True
        self.root.update_idletasks()

    def _dnd_release(self, event, row):
        state = self._dnd_state
        if not state or state['row'] is not row:
            return
        if state.get('highlighted'):
            row.set_dragged(False)
        if state['moved']:
            self.save_config()
        self._dnd_state = None

    def _toggle_bad_matchups(self, pick_row):
        if self.active_bm_panel is not None and self.active_bm_panel.owner_row is pick_row:
            self._close_bm_panel()
            return
        if self.active_bm_panel is not None:
            self._close_bm_panel()
        panel = BadMatchupsPanel(self, self.pick_champ_list_frame, pick_row)
        for opp_cid in self.bad_matchups.get(str(pick_row.champ_id), []):
            panel.add_row(opp_cid)
        self.active_bm_panel = panel
        self._pack_bm_panel(panel)
        panel.entry.focus_set()
        self._resize_window()

    def _pack_bm_panel(self, panel):
        panel.frame.pack_forget()
        panel.frame.pack(after=panel.owner_row.outer, fill=tk.X, padx=4, pady=(1, 2))

    def _close_bm_panel(self):
        if self.active_bm_panel is None:
            return
        if self.editing_bm is not None:
            self._commit_bm_edit(self.editing_bm)
        self.active_bm_panel.destroy()
        self.active_bm_panel = None
        self._resize_window()

    def _add_bm(self, panel, opp_champ_id):
        owner_key = str(panel.owner_champ_id)
        cur = list(self.bad_matchups.get(owner_key, []))
        if len(cur) >= BadMatchupsPanel.MAX or opp_champ_id in cur:
            return
        cur.append(opp_champ_id)
        self.bad_matchups[owner_key] = cur
        self.save_config()
        panel.add_row(opp_champ_id)
        self._resize_window()

    def _delete_bm(self, bm_row):
        if self.active_bm_panel is None:
            return
        owner_key = str(self.active_bm_panel.owner_champ_id)
        cur = list(self.bad_matchups.get(owner_key, []))
        if bm_row.champ_id in cur:
            cur.remove(bm_row.champ_id)
            self.bad_matchups[owner_key] = cur
            self.save_config()
        self.active_bm_panel.remove_row(bm_row)
        self._resize_window()

    def _edit_bm(self, bm_row):
        if self.active_bm_panel is None:
            return
        if self.editing_bm is not None and self.editing_bm is not bm_row:
            self._commit_bm_edit(self.editing_bm)
        if self.editing_bm is bm_row:
            return
        bm_row.lbl.pack_forget()
        bm_row.edit_entry = tk.Entry(bm_row.inner, bg=ROW_BG, fg=ACTIVE_FG, insertbackground='#ffffff', font=FONT_ROW_SMALL, relief='flat', borderwidth=0, selectbackground=ROW_BG, selectforeground=ACTIVE_FG, highlightthickness=0, width=1)
        old_name = CHAMPION_NAMES.get(bm_row.champ_id, '')
        bm_row.edit_entry.insert(0, old_name)
        bm_row.edit_entry.icursor(0)
        bm_row.edit_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, before=bm_row.del_btn)
        bm_row.is_initial_edit_replace = True
        if self.active_bm_panel is not None:
            bm_row.edit_list_frame = tk.Frame(self.active_bm_panel.frame, bg=ROW_BG)
        else:
            bm_row.edit_list_frame = tk.Frame(bm_row.outer.master, bg=ROW_BG)
        bm_row.edit_listbox = tk.Listbox(bm_row.edit_list_frame, bg='#0a1a2b', fg='#c8aa6e', font=FONT_ENTRY_SMALL, height=0, borderwidth=0, highlightthickness=0, selectbackground='#2a3a4a', selectforeground='#f0e6d2', activestyle='none', exportselection=False)
        bm_row.edit_listbox.pack(fill=tk.X)
        bm_row.edit_listbox.pack_forget()
        bm_row.edit_list_frame.pack_forget()
        bm_row.edit_entry.bind('<KeyPress>', lambda e, r=bm_row: self._on_bm_edit_keypress(e, r))
        bm_row.edit_entry.bind('<KeyRelease>', lambda e, r=bm_row: self._on_bm_edit_keyrelease(e, r))
        bm_row.edit_entry.bind('<Return>', lambda e, r=bm_row: self._commit_bm_edit(r))
        bm_row.edit_entry.bind('<Escape>', lambda e, r=bm_row: self._cancel_bm_edit(r))
        bm_row.edit_entry.bind('<Down>', lambda e, r=bm_row: self._listbox_navigate(r.edit_listbox, 1))
        bm_row.edit_entry.bind('<Up>', lambda e, r=bm_row: self._listbox_navigate(r.edit_listbox, -1))
        bm_row.edit_entry.bind('<FocusOut>', lambda e, r=bm_row: self.root.after(150, lambda: self._commit_bm_edit(r)))
        bm_row.edit_listbox.bind('<Button-1>', lambda e, r=bm_row: self._on_bm_edit_listbox_click(e, r))
        bm_row.edit_listbox.bind('<Double-Button-1>', lambda e, r=bm_row: self._on_bm_edit_listbox_click(e, r))
        bm_row.edit_entry.focus_set()
        self.editing_bm = bm_row
        self._resize_window()

    def _on_bm_edit_keypress(self, event, row):
        if row.is_initial_edit_replace and event.char and (len(event.char) == 1) and event.char.isprintable():
            row.edit_entry.delete(0, tk.END)
            row.edit_entry.insert(0, event.char)
            row.edit_entry.icursor(1)
            row.is_initial_edit_replace = False
            return 'break'
        if event.keysym in ('BackSpace', 'Delete'):
            row.is_initial_edit_replace = False
        return None

    def _on_bm_edit_keyrelease(self, event, row):
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Left', 'Right'):
            return
        row.edit_listbox.delete(0, tk.END)
        matches = find_matches(row.edit_entry.get())
        if not matches:
            row.edit_list_frame.pack_forget()
            self._resize_window()
            return
        num = min(len(matches), 5)
        row.edit_listbox.config(height=num)
        for m in matches[:num]:
            row.edit_listbox.insert(tk.END, m)
        if not row.edit_list_frame.winfo_ismapped():
            if self.active_bm_panel is not None:
                row.edit_list_frame.pack(after=self.active_bm_panel.grid_frame, fill=tk.X, padx=4, pady=(0, 1))
            else:
                row.edit_list_frame.pack(fill=tk.X, pady=(0, 1))
            row.edit_listbox.pack(fill=tk.X)
        self._resize_window()

    def _on_bm_edit_listbox_click(self, event, row):
        try:
            idx = row.edit_listbox.nearest(event.y)
            row.edit_listbox.selection_clear(0, tk.END)
            row.edit_listbox.selection_set(idx)
            row.edit_listbox.activate(idx)
        except Exception:
            pass
        self._commit_bm_edit(row)
        return 'break'

    def _commit_bm_edit(self, row):
        if self.editing_bm is not row or row.edit_entry is None:
            return
        sel = row.edit_listbox.curselection()
        if sel:
            name = row.edit_listbox.get(sel[0])
        elif row.edit_listbox.size() > 0:
            name = row.edit_listbox.get(0)
        else:
            name = row.edit_entry.get().strip()
        norm = name.lower().replace(' ', '').replace("'", '')
        new_id = NORM_NAMES.get(norm, (None, None))[1]
        if self.active_bm_panel is not None:
            owner_key = str(self.active_bm_panel.owner_champ_id)
            cur = list(self.bad_matchups.get(owner_key, []))
            if row.champ_id in cur:
                idx = cur.index(row.champ_id)
                old_id = row.champ_id
                if new_id is not None and (new_id == old_id or new_id not in cur):
                    cur[idx] = new_id
                    self.bad_matchups[owner_key] = cur
                    self.save_config()
                    row.set_data(new_id)
        self._cancel_bm_edit(row)

    def _cancel_bm_edit(self, row):
        if row.edit_entry is None:
            return
        try:
            row.edit_entry.destroy()
        except Exception:
            pass
        row.edit_entry = None
        try:
            if row.edit_list_frame is not None:
                row.edit_list_frame.destroy()
        except Exception:
            pass
        row.edit_list_frame = None
        row.edit_listbox = None
        row.lbl.pack(side=tk.LEFT, padx=(2, 2), before=row.del_btn)
        if self.editing_bm is row:
            self.editing_bm = None
        self._resize_window()

    def _bm_dnd_start(self, event, bm_row):
        if self.editing_bm is bm_row or self.active_bm_panel is None:
            return
        if bm_row not in self.active_bm_panel.bm_rows:
            return
        self._bm_dnd_state = {'row': bm_row, 'moved': False, 'highlighted': False, 'start_x': event.x_root, 'start_y': event.y_root}

    def _bm_dnd_motion(self, event, bm_row):
        state = self._bm_dnd_state
        if not state or state['row'] is not bm_row or self.active_bm_panel is None:
            return
        if not state['highlighted']:
            dx = abs(event.x_root - state['start_x'])
            dy = abs(event.y_root - state['start_y'])
            if dx + dy < 3:
                return
            bm_row.set_dragged(True)
            state['highlighted'] = True
        panel = self.active_bm_panel
        bms = panel.bm_rows
        if bm_row not in bms:
            return
        cur = bms.index(bm_row)
        try:
            px = panel.grid_frame.winfo_pointerx()
            py = panel.grid_frame.winfo_pointery()
        except tk.TclError:
            return
        best = cur
        best_dist = None
        for i, other in enumerate(bms):
            try:
                ox = other.outer.winfo_rootx() + other.outer.winfo_width() / 2
                oy = other.outer.winfo_rooty() + other.outer.winfo_height() / 2
            except tk.TclError:
                continue
            d = (px - ox) ** 2 + (py - oy) ** 2
            if best_dist is None or d < best_dist:
                best_dist = d
                best = i
        if best != cur:
            bms[cur], bms[best] = (bms[best], bms[cur])
            owner_key = str(panel.owner_champ_id)
            self.bad_matchups[owner_key] = [b.champ_id for b in bms]
            state['moved'] = True
            panel.rebuild_grid()
            bm_row.set_dragged(True)

    def _bm_dnd_release(self, event, bm_row):
        state = self._bm_dnd_state
        if not state or state['row'] is not bm_row:
            return
        if state.get('highlighted'):
            bm_row.set_dragged(False)
        if state['moved']:
            self.save_config()
        self._bm_dnd_state = None

    def _on_global_click(self, event):
        if self.active_bm_panel is None:
            return
        w = event.widget
        panel = self.active_bm_panel
        if self._widget_in(w, panel.frame):
            return
        if self._widget_in(w, panel.owner_row.outer):
            return
        if panel.owner_row.dots_btn is not None and w is panel.owner_row.dots_btn:
            return
        self._close_bm_panel()

    @staticmethod
    def _widget_in(widget, container):
        try:
            wpath = str(widget)
            cpath = str(container)
            return wpath == cpath or wpath.startswith(cpath + '.')
        except Exception:
            return False

    def start_drag(self, event):
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def drag(self, event):
        self.root.geometry(f'+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}')
