"""One-time asset conversion. Runtime has no Pillow/AST dependency."""
import ast
from collections import deque
import json
from pathlib import Path
from PIL import Image

ROOT = Path("/app")
OUT = ROOT / "autopicker/assets"
OUT.mkdir(parents=True, exist_ok=True)
tree = ast.parse((ROOT / "original/autopicker.py").read_text(encoding="utf-8"))
names = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "CHAMPION_NAMES" for t in node.targets))
(OUT / "champions.json").write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")

image = Image.open(ROOT / "original/icon.jpeg").convert("RGBA")
width, height = image.size
pixels = image.load()
pending = deque([(x, 0) for x in range(width)] + [(x, height - 1) for x in range(width)]
                + [(0, y) for y in range(height)] + [(width - 1, y) for y in range(height)])
seen = set()
while pending:
    x, y = pending.popleft()
    if (x, y) in seen or not (0 <= x < width and 0 <= y < height):
        continue
    seen.add((x, y))
    r, g, b, a = pixels[x, y]
    if min(r, g, b) >= 165 and max(r, g, b) - min(r, g, b) < 50:
        pixels[x, y] = (r, g, b, 0)
        pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
box = image.getbbox()
image = image.crop(box)
image.save(OUT / "icon.png")
canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
image.thumbnail((248, 248), Image.Resampling.LANCZOS)
canvas.alpha_composite(image, ((256 - image.width) // 2, (256 - image.height) // 2))
canvas.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
for browser in ("chromium", "firefox"):
    canvas.resize((128, 128), Image.Resampling.LANCZOS).save(ROOT / f"autopicker/extension/{browser}/icon.png")
print(f"{len(names)} Champion-Namen aus Original übernommen; Icon außen transparent, Innenweiß erhalten.")