import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.patches import FancyArrowPatch

INK = "#16130E"
CREAM = "#FFFDF5"
CREAM2 = "#FBF6E6"
CORAL = "#FF6B6B"
YELLOW = "#FFD93D"
PURPLE = "#C4B5FD"
GRID = "#EFE8D6"

def category(node_type):
    t = node_type.lower()
    if "trigger" in t or "webhook" in t:
        return CORAL
    if "langchain" in t or "openai" in t or "gemini" in t or "anthropic" in t:
        return PURPLE
    if any(k in t for k in ["if", "switch", "filter", "merge", "code", "set", "splitinbatches", "removeduplicates", "aggregate"]):
        return YELLOW
    return "#9FD8B8"  # soft green for actions/integrations (kept distinct, not in core palette, muted)

def short_type(node_type):
    return node_type.split(".")[-1]

def load_workflow(path):
    with open(path) as f:
        return json.load(f)

def render(path, title, out_path, max_nodes=None):
    d = load_workflow(path)
    nodes = d.get("nodes", [])
    if max_nodes:
        nodes = nodes[:max_nodes]
    names = {n["name"] for n in nodes}
    conns = d.get("connections", {})

    xs = [n["position"][0] for n in nodes]
    ys = [n["position"][1] for n in nodes]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    padx = (maxx - minx) * 0.06 + 140
    pady = (maxy - miny) * 0.08 + 100

    w = maxx - minx + 2 * padx
    h = maxy - miny + 2 * pady
    fig_w = 16
    fig_h = max(6, fig_w * h / w)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(minx - padx, maxx + padx)
    ax.set_ylim(maxy + pady, miny - pady)  # invert y (n8n y grows downward)
    ax.set_facecolor(CREAM)
    fig.patch.set_facecolor(CREAM)

    # points-per-data-unit, so node/font sizes stay visually constant regardless
    # of this workflow's raw coordinate spread (matplotlib font sizes are in
    # points, not data units, so this conversion is required)
    pts_per_x = (fig_w * 72.0) / (w)
    pts_per_y = (fig_h * 72.0) / (h)
    def px(pt): return pt / pts_per_x
    def py(pt): return pt / pts_per_y

    # dotted grid, n8n-style
    step = 40
    gx = int((maxx - minx + 2*padx) // step) + 1
    gy = int((maxy - miny + 2*pady) // step) + 1
    xs_grid = [minx - padx + i*step for i in range(gx)]
    ys_grid = [miny - pady + i*step for i in range(gy)]
    ax.scatter([x for x in xs_grid for _ in ys_grid],
               [y for _ in xs_grid for y in ys_grid],
               s=1.2, color=GRID, zorder=0)

    pos = {n["name"]: (n["position"][0], n["position"][1]) for n in nodes}
    node_w, node_h = px(58), py(34)

    # connections first (under nodes)
    for src, out in conns.items():
        if src not in pos:
            continue
        x1, y1 = pos[src]
        for branch in out.get("main", []):
            for edge in branch:
                tgt = edge.get("node")
                if tgt not in pos:
                    continue
                x2, y2 = pos[tgt]
                arrow = FancyArrowPatch(
                    (x1 + node_w/2, y1 + node_h/2), (x2 - node_w/2, y2 + node_h/2),
                    connectionstyle="arc3,rad=0.15", arrowstyle="-|>",
                    mutation_scale=14, linewidth=1.6, color=INK, alpha=0.55, zorder=1,
                )
                ax.add_patch(arrow)

    for n in nodes:
        x, y = n["position"]
        color = category(n.get("type", ""))
        box = FancyBboxPatch(
            (x - node_w/2, y), node_w, node_h,
            boxstyle="round,pad=0,rounding_size=10",
            linewidth=2, edgecolor=INK, facecolor="white", zorder=2,
        )
        ax.add_patch(box)
        # accent bar
        accent = FancyBboxPatch(
            (x - node_w/2, y), px(4), node_h,
            boxstyle="round,pad=0,rounding_size=2",
            linewidth=0, facecolor=color, zorder=3,
        )
        ax.add_patch(accent)
        label = n["name"]
        if len(label) > 10:
            label = label[:9] + "…"
        ax.text(x - node_w/2 + px(5), y + node_h*0.32, label, fontsize=4.6, fontweight="bold",
                color=INK, ha="left", va="center", zorder=4, family="DejaVu Sans")
        ax.text(x - node_w/2 + px(5), y + node_h*0.74, short_type(n.get("type",""))[:11], fontsize=3.7,
                color="#6b6455", ha="left", va="center", zorder=4, family="monospace")

    ax.set_title(title, fontsize=17, fontweight="bold", color=INK, loc="left", pad=16,
                 family="DejaVu Sans")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, facecolor=CREAM, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)

    # autocrop excess cream margin left by variable-aspect layouts
    from PIL import Image, ImageChops
    im = Image.open(out_path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 253, 245))
    diff = ImageChops.difference(im, bg).convert("L")
    # threshold out the faint dot-grid (low-contrast vs background); keep only
    # strong edges (node borders/text/arrows) for the crop bounding box
    diff = diff.point(lambda p: 255 if p > 40 else 0)
    bbox = diff.getbbox()
    if bbox:
        pad = 24
        l, t, r, b = bbox
        l = max(0, l - pad); t = max(0, t - pad)
        r = min(im.width, r + pad); b = min(im.height, b + pad)
        im = im.crop((l, t, r, b))
    im.save(out_path)

    return len(nodes), len(d.get("nodes", []))

if __name__ == "__main__":
    jobs = json.loads(sys.argv[1])
    for j in jobs:
        n_shown, n_total = render(j["path"], j["title"], j["out"], j.get("max_nodes"))
        print(f"{j['out']}: {n_shown}/{n_total} nodes rendered")
