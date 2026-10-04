"""Extract the user's original widgets; omit the replaced network/keyboard code."""
import ast
from pathlib import Path

SOURCE = Path('/app/original/autopicker_latest.py')
OUT = Path('/app/autopicker/lolpicker')
tree = ast.parse(SOURCE.read_text(encoding='utf-8'))


def write(name, nodes, imports):
    module = ast.Module(body=ast.parse(imports).body + nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    (OUT / name).write_text(ast.unparse(module) + '\n', encoding='utf-8')


class Compact(ast.NodeTransformer):
    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body.pop(0)
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'min' and len(node.args) == 2:
            if isinstance(node.args[0], ast.Call) and ast.unparse(node.args[0]) == 'len(matches)':
                node.args[1] = ast.Constant(5)
        return node


widget_nodes = [node for node in tree.body if 920 <= node.lineno <= 1260]
widget_nodes = [Compact().visit(node) for node in widget_nodes]
write('ui_widgets.py', widget_nodes, '''
import tkinter as tk
from .storage import read_json
from .platform_win import bundle_dir
CHAMPION_NAMES = {int(key): value for key, value in read_json(bundle_dir() / 'assets/champions.json', {}).items()}
''')

overlay = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'OverlayApp')
overlay.name = 'ClassicOverlay'
selected = []
for node in overlay.body:
    if not isinstance(node, ast.FunctionDef):
        continue
    if node.name == '__init__':
        node.args.args.append(ast.arg(arg='root'))
        node.body = [stmt for stmt in node.body if not (1311 <= stmt.lineno <= 1334 or 1447 <= stmt.lineno <= 1450)]
        node.body[0] = ast.parse('self.root = root').body[0]
        selected.append(node)
    elif (1473 <= node.lineno <= 1527 or 1595 <= node.lineno <= 2392 or node.name in ('start_drag', 'drag')):
        selected.append(node)
overlay.body = [Compact().visit(node) for node in selected]
write('ui_layout.py', [overlay], '''
import tkinter as tk
import queue
from .ui_widgets import (ROW_BG, FONT_ROW, FONT_ROW_SMALL, FONT_ENTRY, FONT_ENTRY_SMALL,
    PICK_BORDER, DRAG_BORDER, PICK_PLACEHOLDER, BAN_PLACEHOLDER, PLACEHOLDER_FG,
    ACTIVE_FG, CHAMPION_NAMES, NAME_TO_ID, NORM_NAMES, find_matches, ChampRow, BadMatchupsPanel)
''')

settings = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'SettingsWindow')
settings.name = 'ClassicSettings'
selected = []
for node in settings.body:
    if isinstance(node, ast.Assign):
        selected.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in ('__init__', '_build_row', '_weak_label', '_weak_bg', '_format_hotkey', '_start_drag', '_drag', '_reset_button'):
        if node.name == '__init__':
            node.body = [stmt for stmt in node.body if not 3568 <= stmt.lineno <= 3582]
            index = next(i for i, stmt in enumerate(node.body) if stmt.lineno == 3585)
            node.body.insert(index, ast.parse('self._build_tracking(track_row)').body[0])
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str) and 'lol_tool_debug.log neben der EXE' in child.value:
                    child.value = 'AN  =  schreibt Diagnose-Log in\n         %LOCALAPPDATA%\\LoLAutopicker'
        selected.append(Compact().visit(node))
settings.body = selected
write('settings_layout.py', [settings], '''
import tkinter as tk
from .ui_widgets import ROW_BG
HOTKEY_LABELS = {'toggle_overlay': 'Overlay ein/aus', 'open_lolalytics': 'Lolalytics oeffnen',
    'open_vs': 'VS-Matchup oeffnen', 'close_tab': 'Tab schliessen', 'close_all_browsers': 'Alle Browser schliessen'}
''')
print('Originalwidgets extrahiert; Farben/Abstände/Transparenz unverändert, maximal fünf Vorschläge.')