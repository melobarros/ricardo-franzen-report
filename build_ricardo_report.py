#!/usr/bin/env python3
"""Build the Ricardo Franzen 2026 channel report.

Reads data/ricardo/video_stats.json and the thumbnail cache, generates the
inline SVG charts and base64 contact sheets, and injects them into the HTML
template at report/ricardo_template.html.
"""

import base64
import html
import io
import json
import sys
from datetime import date
from pathlib import Path
from statistics import median

from PIL import Image

ROOT = Path(__file__).resolve().parent
STATS = json.loads((ROOT / "data/ricardo/video_stats.json").read_text(encoding="utf-8"))
SAMPLE = json.loads((ROOT / "data/ricardo/sample.json").read_text(encoding="utf-8"))
THUMBS = ROOT / "data/ricardo/thumbs"
TEMPLATES = {
    "pt": ROOT / "report/ricardo_template_pt.html",
    "en": ROOT / "report/ricardo_template.html",
}
OUTPUTS = {
    "pt": ROOT / "report/ricardo-franzen.html",
    "en": ROOT / "report/ricardo-franzen-en.html",
}

LANG = "en"
MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"],
    "pt": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov"],
}
MONTH_KEYS = [f"2026-{m:02d}" for m in range(1, 12)]


def fint(v):
    s = f"{v:,}"
    return s if LANG == "en" else s.replace(",", ".")


def fdec(v, digits=1):
    s = f"{v:.{digits}f}"
    return s if LANG == "en" else s.replace(".", ",")


def fpct(v, digits=1):
    return fdec(v, digits) + "%"

# Validated categorical palette (dataviz reference slots 1-3, checked against
# the report surfaces with scripts/validate_palette.js --pairs all).
C_ESSAY = "var(--series-essay)"
C_GEAR = "var(--series-gear)"
C_LEI = "var(--series-lei)"
C_VLOG = "var(--series-vlog)"


def esc(s):
    return html.escape(str(s), quote=True)


def img_uri(video_id, width=480, quality=78):
    path = THUMBS / f"{video_id}.jpg"
    im = Image.open(path).convert("RGB")
    height = round(width * 9 / 16)
    im = im.resize((width, height), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def bar_path(x, y, w, h, r=4):
    """Column with a rounded top and a square baseline."""
    if h <= 0:
        return ""
    r = min(r, h, w / 2)
    return (f"M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} "
            f"Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
            f"L{x + w - r:.1f},{y:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
            f"L{x + w:.1f},{y + h:.1f} Z")


def monthly_svg(kind):
    W, H, L, R, T, B = 360, 280, 44, 14, 24, 36
    PW, PH = W - L - R, H - T - B
    months = MONTHS[LANG]
    n = len(months)
    step = PW / n
    counts = [len([r for r in STATS if r["month"] == k]) for k in MONTH_KEYS]

    if kind == "views":
        values = [3469, 1848, 2542, 2321, 2347, 1749, 1848, 1986, 3491, 3614, 2761]
        y_max, ticks = 4000, [0, 1000, 2000, 3000, 4000]
        mark_class = "mark-gear"
        label_idx = {0: fint(3469), 6: fint(1848), 9: fint(3614)}
        aria = ("Median views per video by month" if LANG == "en"
                else "Mediana de views por vídeo, por mês")
        band = "Sep–Nov" if LANG == "en" else "Set–Nov"
        tip_tpl = ("{m} · {c} videos · {v} median views" if LANG == "en"
                   else "{m} · {c} vídeos · {v} views medianas")
    else:
        values = [15.5, 17.1, 15.0, 14.4, 16.5, 16.8, 15.8, 13.1, 6.1, 5.4, 6.1]
        y_max, ticks = 20, [0, 5, 10, 15, 20]
        mark_class = "mark-essay"
        label_idx = {0: fpct(15.5), 7: fpct(13.1), 9: fpct(5.4)}
        aria = ("Median like rate by month" if LANG == "en"
                else "Taxa de like mediana, por mês")
        band = "Sep–Nov" if LANG == "en" else "Set–Nov"
        tip_tpl = ("{m} · {c} videos · {v}% median like rate" if LANG == "en"
                   else "{m} · {c} vídeos · {v}% de taxa de like mediana")

    def y(v):
        return T + PH - (v / y_max) * PH

    def x(i):
        return L + step * i + step / 2

    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart-svg" role="img" aria-label="{aria}">']

    # Post-August wash: September is the first full month after the shift.
    band_x = L + step * 8
    parts.append(f'<rect class="wash" x="{band_x:.1f}" y="{T}" width="{L + PW - band_x:.1f}" height="{PH}"/>')
    if kind == "views":
        parts.append(f'<text class="band-label" x="{band_x + 4:.1f}" y="{T - 8}">{band}</text>')

    # Grid and y ticks.
    for t in ticks:
        yy = y(t)
        parts.append(f'<line class="gridline" x1="{L}" x2="{L + PW}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        lab = f"{t // 1000}k" if kind == "views" and t else f"{t}%"
        parts.append(f'<text class="tick" x="{L - 7}" y="{yy + 3.5:.1f}" text-anchor="end">{lab}</text>')

    # Baseline.
    parts.append(f'<line class="axisline" x1="{L}" x2="{L + PW}" y1="{T + PH}" y2="{T + PH}"/>')

    if kind == "views":
        for i, v in enumerate(values):
            w = 15
            xx = x(i) - w / 2
            yy = y(v)
            parts.append(f'<path class="{mark_class}" d="{bar_path(xx, yy, w, T + PH - yy)}"/>')
            if i in label_idx:
                parts.append(f'<text class="val" x="{x(i):.1f}" y="{yy - 6:.1f}" text-anchor="middle">{label_idx[i]}</text>')
        for i, v in enumerate(values):
            tip = tip_tpl.format(m=months[i], c=counts[i], v=fint(v))
            parts.append(f'<g class="hit" tabindex="0" role="img" aria-label="{tip}" data-tip="{tip}">'
                         f'<rect class="hit-shape" x="{L + step * i:.1f}" y="{y(v) - 8:.1f}" width="{step:.1f}" '
                         f'height="{T + PH - y(v) + 8:.1f}"/></g>')
    else:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
        parts.append(f'<polyline class="line-essay" points="{pts}"/>')
        for i, v in enumerate(values):
            parts.append(f'<circle class="{mark_class} ring" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4"/>')
            if i in label_idx:
                if i == 7:  # August: above-right of the elbow, clear of the falling line
                    lx, ly, anchor = x(i) + 12, y(v) - 4, "start"
                elif i == 9:  # October: below the point, away from the flat Sep–Oct run
                    lx, ly, anchor = x(i), y(v) + 19, "middle"
                else:
                    lx, ly, anchor = x(i), y(v) - 9, "middle"
                parts.append(f'<text class="val" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{label_idx[i]}</text>')
        for i, v in enumerate(values):
            tip = tip_tpl.format(m=months[i], c=counts[i], v=fdec(v))
            parts.append(f'<g class="hit" tabindex="0" role="img" aria-label="{tip}" data-tip="{tip}">'
                         f'<circle class="hit-shape" cx="{x(i):.1f}" cy="{y(v):.1f}" r="14"/></g>')

    # X labels.
    for i, m in enumerate(months):
        parts.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 12}" text-anchor="middle">{m}</text>')

    parts.append("</svg>")
    return "".join(parts)


def format_svg():
    W, H, L, R, T, B = 560, 400, 64, 120, 28, 58
    PW, PH = W - L - R, H - T - B
    x_max, y_max = 4000, 20.0

    def x(v):
        return L + (v / x_max) * PW

    def y(v):
        return T + PH - (v / y_max) * PH

    # Pre-August 25 medians (n=36 gear, 27 essay, 185 vlog/other, 27 LEI).
    labels = {
        "en": {
            "essay": "Essay / manifesto", "gear": "Gear story",
            "vlog": "Daily vlog / other", "lei": "LEI series",
            "views_axis": "Median views per video", "like_axis": "Like rate (likes ÷ views)",
            "tip": "{label} · {n} videos · {v} median views · {r}% like rate",
            "aria": ("Format map: median views against median like rate, January to August 24. "
                     "Essays reach more than daily vlogs with a similar like rate; gear reaches most "
                     "and is liked least; the highest reach and highest engagement quadrant is empty."),
        },
        "pt": {
            "essay": "Ensaio / manifesto", "gear": "Equipamento",
            "vlog": "Vlog diário / outros", "lei": "Série LEI",
            "views_axis": "Mediana de views por vídeo", "like_axis": "Taxa de like (likes ÷ views)",
            "tip": "{label} · {n} vídeos · {v} views medianas · {r}% de taxa de like",
            "aria": ("Mapa dos formatos: mediana de views por taxa de like mediana, de janeiro a 24 de agosto. "
                     "O ensaio chega mais longe que o vlog diário com taxa de like parecida; o equipamento "
                     "alcança mais e é o menos curtido; o quadrante de maior alcance e maior vínculo está vazio."),
        },
    }[LANG]
    points = [
        {"key": "essay", "label": labels["essay"], "n": 27, "v": 2849, "r": 14.4,
         "shape": "circle", "cls": "mark-essay"},
        {"key": "gear", "label": labels["gear"], "n": 36, "v": 3696, "r": 11.0,
         "shape": "square", "cls": "mark-gear"},
        {"key": "vlog", "label": labels["vlog"], "n": 185, "v": 1975, "r": 16.4,
         "shape": "circle", "cls": "mark-vlog"},
        {"key": "lei", "label": labels["lei"], "n": 27, "v": 1397, "r": 17.3,
         "shape": "diamond", "cls": "mark-lei"},
    ]

    parts = [f'<svg viewBox="0 0 {W} {H}" class="chart-svg" role="img" '
             f'aria-label="{labels["aria"]}">']

    # Quadrant lines at the pre-August medians.
    qx, qy = 2208, 15.6
    parts.append(f'<line class="gridline quad" x1="{x(qx):.1f}" x2="{x(qx):.1f}" y1="{T}" y2="{T + PH}"/>')
    parts.append(f'<line class="gridline quad" x1="{L}" x2="{L + PW}" y1="{y(qy):.1f}" y2="{y(qy):.1f}"/>')

    # Grid and ticks.
    for t in [0, 1000, 2000, 3000, 4000]:
        parts.append(f'<line class="gridline faint" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{T}" y2="{T + PH}"/>')
        lab = "0" if t == 0 else f"{t // 1000}k"
        parts.append(f'<text class="tick" x="{x(t):.1f}" y="{H - 38}" text-anchor="middle">{lab}</text>')
    for t in [0, 5, 10, 15, 20]:
        parts.append(f'<line class="gridline faint" x1="{L}" x2="{L + PW}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        lab = "0" if t == 0 else f"{t}%"
        parts.append(f'<text class="tick" x="{L - 7}" y="{y(t) + 3.5:.1f}" text-anchor="end">{lab}</text>')

    parts.append(f'<line class="axisline" x1="{L}" x2="{L + PW}" y1="{T + PH}" y2="{T + PH}"/>')

    # Axis titles.
    parts.append(f'<text class="axis-title" x="{L + PW / 2:.1f}" y="{H - 10}" text-anchor="middle">{labels["views_axis"]}</text>')
    parts.append(f'<text class="axis-title" x="16" y="{T + PH / 2:.1f}" text-anchor="middle" '
                 f'transform="rotate(-90 16 {T + PH / 2:.1f})">{labels["like_axis"]}</text>')

    # Points + labels.
    label_pos = {
        "essay": (x(2849) + 13, y(14.4) + 20, "start", f'{labels["essay"]} · 27'),
        "gear": (x(3696) + 14, y(11.0) + 17, "start", f'{labels["gear"]} · 36'),
        "vlog": (x(1975) + 12, y(16.4) - 6, "start", f'{labels["vlog"]} · 185'),
        "lei": (x(1397) - 12, y(17.3) + 4, "end", f'{labels["lei"]} · 27'),
    }
    for p in points:
        cx, cy = x(p["v"]), y(p["r"])
        if p["shape"] == "circle":
            parts.append(f'<circle class="{p["cls"]} ring-thick" cx="{cx:.1f}" cy="{cy:.1f}" r="9"/>')
        elif p["shape"] == "square":
            parts.append(f'<rect class="{p["cls"]} ring-thick" x="{cx - 8:.1f}" y="{cy - 8:.1f}" width="16" height="16" rx="2"/>')
        else:
            parts.append(f'<polygon class="{p["cls"]} ring-thick" points="{cx:.1f},{cy - 10:.1f} {cx + 10:.1f},{cy:.1f} '
                         f'{cx:.1f},{cy + 10:.1f} {cx - 10:.1f},{cy:.1f}"/>')
        tip = labels["tip"].format(label=p["label"], n=p["n"], v=fint(p["v"]), r=fdec(p["r"]))
        parts.append(f'<g class="hit" tabindex="0" role="img" aria-label="{tip}" data-tip="{tip}">'
                     f'<circle class="hit-shape" cx="{cx:.1f}" cy="{cy:.1f}" r="17"/></g>')
        lx, ly, anchor, text = label_pos[p["key"]]
        parts.append(f'<text class="val-label" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{text}</text>')

    parts.append("</svg>")
    return "".join(parts)


def format_legend():
    labels = {
        "en": ["Essay / manifesto", "Gear story", "Daily vlog / other", "LEI series"],
        "pt": ["Ensaio / manifesto", "Equipamento", "Vlog diário / outros", "Série LEI"],
    }[LANG]
    items = [
        ("circle", "mark-essay", labels[0]),
        ("square", "mark-gear", labels[1]),
        ("circle", "mark-vlog", labels[2]),
        ("diamond", "mark-lei", labels[3]),
    ]
    out = []
    for shape, cls, label in items:
        if shape == "circle":
            mark = f'<circle class="{cls}" cx="7" cy="7" r="5.5"/>'
        elif shape == "square":
            mark = f'<rect class="{cls}" x="2" y="2" width="10" height="10" rx="1.5"/>'
        else:
            mark = f'<polygon class="{cls}" points="7,1.5 12.5,7 7,12.5 1.5,7"/>'
        out.append(f'<span class="key"><svg viewBox="0 0 14 14" aria-hidden="true">{mark}</svg>{label}</span>')
    return "".join(out)


def monthly_table():
    rows = []
    bym = {}
    for r in STATS:
        bym.setdefault(r["month"], []).append(r)
    for key, label in zip(MONTH_KEYS, MONTHS[LANG]):
        rs = bym.get(key, [])
        med_v = round(median([r["views"] for r in rs]))
        med_l = median([r["like_rate"] for r in rs])
        share = sum(1 for r in rs if r["views"] >= 5000) / len(rs) * 100
        rows.append(f"<tr><td>{label}</td><td>{len(rs)}</td><td>{fint(med_v)}</td>"
                    f"<td>{fpct(med_l)}</td><td>{fpct(share, 0)}</td></tr>")
    return "".join(rows)


def format_table():
    pre = [r for r in STATS if date.fromisoformat(r["date"]) < date(2026, 8, 25)]
    names = {
        "en": ["Gear story", "Essay / manifesto", "Daily vlog / other", "LEI series"],
        "pt": ["Equipamento", "Ensaio / manifesto", "Vlog diário / outros", "Série LEI"],
    }[LANG]
    groups = [
        (names[0], [r for r in pre if r["fmt"] == "gear"]),
        (names[1], [r for r in pre if r["fmt"] == "essay"]),
        (names[2], [r for r in pre if r["fmt"] in ("VLOG", "other")]),
        (names[3], [r for r in pre if r["fmt"] == "LEI"]),
    ]
    rows = []
    for name, rs in groups:
        mv = median([r["views"] for r in rs])
        ml = median([r["like_rate"] for r in rs])
        rows.append(f"<tr><td>{name}</td><td class='num'>{len(rs)}</td>"
                    f"<td class='num'>{fint(round(mv))}</td><td class='num'>{fpct(ml)}</td></tr>")
    return "".join(rows)


def top_table():
    top = sorted(STATS, key=lambda r: -r["views"])[:14]
    type_of = {
        "b6akAEW0F4k": ("Manifesto", "idea"),
        "4N9UMkzNTu4": ("Gear story", "object"),
        "9kN0D0Uxg2Y": ("Essay", "idea"),
        "Www-gU4q9lA": ("Gear test", "object"),
        "kZ8YSZt5SEw": ("Gear story", "object"),
        "mTxxFnRR_-o": ("Collab film", "collab"),
        "Yuxa43mIFx8": ("Essay", "idea"),
        "E0NMaljitq8": ("Manifesto", "idea"),
        "IdV8lyX5KQo": ("Essay", "idea"),
        "enRYqjleVtk": ("Photo / gear", "object"),
        "qwu_d8aYZ80": ("Manifesto", "idea"),
        "53JgVpnZhWo": ("Essay", "idea"),
        "Se7qGrPBujo": ("Gear story", "object"),
        "IM4lyKfP2hE": ("Gear test", "object"),
    }
    tag_names = {
        "en": {"Manifesto": "Manifesto", "Gear story": "Gear story", "Essay": "Essay",
               "Gear test": "Gear test", "Collab film": "Collab film", "Photo / gear": "Photo / gear",
               "Other": "Other"},
        "pt": {"Manifesto": "Manifesto", "Gear story": "Equipamento", "Essay": "Ensaio",
               "Gear test": "Teste de equipamento", "Collab film": "Colab", "Photo / gear": "Foto / equipamento",
               "Other": "Outro"},
    }[LANG]
    rows = []
    for r in top:
        tag, cls = type_of.get(r["id"], ("Other", "idea"))
        tag = tag_names[tag]
        title = esc(r["title"])
        length = f'{r["duration"]:.0f}m' if LANG == "en" else f'{r["duration"]:.0f} min'
        rows.append(
            f'<tr><td class="tcell"><span class="tag tag-{cls}"><i></i>{tag}</span>'
            f'<strong>{title}</strong><span class="sub">{r["date"]}</span></td>'
            f'<td class="num">{fint(r["views"])}</td><td class="num">{fdec(r["ratio"])}×</td>'
            f'<td class="num">{length}</td></tr>')
    return "".join(rows)


def bottom_table():
    rows = []
    labels = {
        "EXISTE VIDA LA FORA mesmo com tudo congelado": "Mood label",
        "QUEBRA GELO": "Mood label",
        "Cores em Movimento": "Mood label",
        "café": "Mood label",
        "Caminhos de Outono": "Place label",
        "traga-me o horizonte": "Mood label",
        "LEI 15 | MÚSICA BOA NÃO SALVA VLOG RUIM": "Series",
        "VLOG 1019": "Serial number",
        "vlog com Ray-Ban Meta Gen 2 | vlog vertical": "Gear experiment",
        "287/365": "Serial number",
        "Primícias de Verão": "Mood label",
        "a vida que enxergamos": "Mood label",
    }
    label_names = {
        "en": {"Mood label": "Mood label", "Place label": "Place label", "Series": "Series",
               "Serial number": "Serial number", "Gear experiment": "Gear experiment", "Diary": "Diary"},
        "pt": {"Mood label": "Rótulo de clima", "Place label": "Rótulo de lugar", "Series": "Série",
               "Serial number": "Número de série", "Gear experiment": "Experimento de equipamento",
               "Diary": "Diário"},
    }[LANG]
    for r in SAMPLE["bottom"]:
        s = next(x for x in STATS if x["id"] == r["id"])
        title = esc(s["title"])
        label = label_names[labels.get(s["title"], "Diary")]
        length = f'{s["duration"]:.0f}m' if LANG == "en" else f'{s["duration"]:.0f} min'
        rows.append(
            f'<tr><td class="tcell"><span class="tag tag-label"><i></i>{label}</span>'
            f'<strong>{title}</strong><span class="sub">{s["date"]}</span></td>'
            f'<td class="num">{fint(s["views"])}</td><td class="num">{fdec(s["ratio"], 2)}×</td>'
            f'<td class="num">{length}</td></tr>')
    return "".join(rows)


def frames(ids, prefix):
    alt = {
        "en": {
            "4N9UMkzNTu4": "Ricardo in a blue cap holds an open MacBook with a red X over the lid.",
            "b6akAEW0F4k": "Ricardo in a blue cap holds a white mug in front of his face, with the words DOCUMENTE SUA VIDA across the frame.",
            "9kN0D0Uxg2Y": "Ricardo in a black cap sits at a table with a coffee mug and a plate in warm lamp light, no overlay text.",
            "Www-gU4q9lA": "Ricardo in sunglasses holds three DJI action cameras, with the text QUAL E A MELHOR.",
            "kZ8YSZt5SEw": "Ricardo in sunglasses holds a MacBook Air outdoors, with the text MacBook Air M5 para edicao de videos.",
            "qwu_d8aYZ80": "Ricardo in a blue cap holds a camera with the words documente sua vida across the frame.",
            "H6NBkGR3bWI": "An orange and blue twilight sky with a street lamp, no person and no text.",
            "E5xapLBlcHY": "Ricardo drinks from a dark glass in profile beside a woman with a white cup, indoors, no text.",
            "xWeZaDEbZys": "Three people walk away down an autumn path, seen from behind, no text.",
            "Zgp8LDMIXvI": "A man on crutches walks away down a city sidewalk, seen from behind, no text.",
            "BJpDGp1YY7k": "Three people cycle away down a green path, seen from behind, no text.",
            "j7lRoGTu0V0": "A family sits around a kitchen counter in warm light, wide shot, no text.",
        },
        "pt": {
            "4N9UMkzNTu4": "Ricardo, de boné azul, segura um MacBook aberto com um X vermelho sobre a tampa.",
            "b6akAEW0F4k": "Ricardo, de boné azul, segura uma caneca branca na frente do rosto, com a frase DOCUMENTE SUA VIDA atravessando o quadro.",
            "9kN0D0Uxg2Y": "Ricardo, de boné preto, senta-se à mesa com uma caneca de café e um prato sob luz quente de lâmpada, sem texto sobreposto.",
            "Www-gU4q9lA": "Ricardo, de óculos escuros, segura três câmeras de ação DJI, com o texto QUAL É A MELHOR.",
            "kZ8YSZt5SEw": "Ricardo, de óculos escuros, segura um MacBook Air ao ar livre, com o texto MacBook Air M5 para edição de vídeos.",
            "qwu_d8aYZ80": "Ricardo, de boné azul, segura uma câmera com a frase documente sua vida atravessando o quadro.",
            "H6NBkGR3bWI": "Céu crepuscular laranja e azul com um poste de luz, sem pessoa e sem texto.",
            "E5xapLBlcHY": "Ricardo bebe de um copo escuro, de perfil, ao lado de uma mulher com uma caneca branca, em ambiente interno, sem texto.",
            "xWeZaDEbZys": "Três pessoas caminham para longe por uma trilha de outono, vistas de costas, sem texto.",
            "Zgp8LDMIXvI": "Um homem de muletas caminha para longe por uma calçada da cidade, visto de costas, sem texto.",
            "BJpDGp1YY7k": "Três pessoas pedalam para longe por uma trilha verde, vistas de costas, sem texto.",
            "j7lRoGTu0V0": "Uma família senta-se ao redor de uma bancada de cozinha sob luz quente, plano aberto, sem texto.",
        },
    }[LANG]
    caption = ("{v} views · {r}× baseline · {d}" if LANG == "en"
               else "{v} views · {r}× a base · {d}")
    out = []
    for i, vid in enumerate(ids, 1):
        s = next(r for r in STATS if r["id"] == vid)
        sub = caption.format(v=fint(s["views"]), r=fdec(s["ratio"], 2), d=s["date"])
        out.append(
            f'<figure class="frame"><div class="frame-img"><span class="frame-no">{prefix}{i}</span>'
            f'<img src="{img_uri(vid)}" alt="{esc(alt.get(vid, ""))}" loading="eager"></div>'
            f'<figcaption><strong>{esc(s["title"])}</strong>'
            f'<span>{sub}</span></figcaption></figure>')
    return "".join(out)


def hero_strip():
    ids = ["4N9UMkzNTu4", "b6akAEW0F4k", "9kN0D0Uxg2Y", "Www-gU4q9lA", "mTxxFnRR_-o", "IdV8lyX5KQo"]
    out = []
    for vid in ids:
        out.append(f'<div class="hero-frame"><img src="{img_uri(vid, 360, 74)}" alt="" loading="eager"></div>')
    return "".join(out)


def kpi_row():
    if LANG == "en":
        cards = [
            ("Median views", "2,208", "3,416", "+55%", "up"),
            ("Median like rate", "15.6%", "6.0%", "−9.6 pp", "down"),
            ("Median comments", "47", "26", "−45%", "down"),
            ("Videos ≥ 5,000 views", "7%", "26%", "+19 pp", "up"),
        ]
    else:
        cards = [
            ("Mediana de views", "2.208", "3.416", "+55%", "up"),
            ("Taxa de like mediana", "15,6%", "6,0%", "−9,6 p.p.", "down"),
            ("Comentários medianos", "47", "26", "−45%", "down"),
            ("Vídeos com ≥ 5.000 views", "7%", "26%", "+19 p.p.", "up"),
        ]
    out = []
    for label, before, after, delta, direction in cards:
        out.append(
            f'<div class="kpi"><span class="kpi-label">{label}</span>'
            f'<span class="kpi-values">{before}<i>→</i>{after}</span>'
            f'<span class="kpi-delta {direction}">{delta}</span></div>')
    return "".join(out)


def timeline():
    if LANG == "en":
        items = [
            ("01 Jan", "The project begins", "“VLOG TODO DIA ATÉ 2026 ACABAR” — 500 videos, one a day."),
            ("03 Jan", "The first door", "“PARE DE TENTAR CRIAR CONTEÚDO” — 66,965 views, the year's biggest film."),
            ("27 Jan", "The essay finds its voice", "“o poder da insignificância” — 28,697 views and the year's longest comments."),
            ("Feb", "The LEI workshop", "27 videos in one month. The channel's highest like rate (17.3%) and lowest reach (1,397 views)."),
            ("23 Jul", "The object door", "“troquei meu MacBook PRO por um Air M5” — 32,789 views, 22.3× the previous median."),
            ("25–26 Aug", "The turn", "Backpack + MacBook Air 30 days. Median views double; the like rate falls from 15.6% to 6.0%."),
            ("01 Sep", "The essay returns", "“e se?” — 13,151 views. The format that balances reach and bond."),
            ("06 Nov", "The current cut", "414 public videos, 56,000 subscribers, 1,380,696 views in 2026."),
        ]
    else:
        items = [
            ("01 Jan", "O projeto começa", "“VLOG TODO DIA ATÉ 2026 ACABAR” — 500 vídeos, um por dia."),
            ("03 Jan", "A primeira porta", "“PARE DE TENTAR CRIAR CONTEÚDO” — 66.965 views, o maior vídeo do ano."),
            ("27 Jan", "O ensaio encontra a voz", "“o poder da insignificância” — 28.697 views e os comentários mais longos do ano."),
            ("Fev", "A oficina das LEI", "27 vídeos em um mês. A maior taxa de like do canal (17,3%) e o menor alcance (1.397 views)."),
            ("23 Jul", "A porta do objeto", "“troquei meu MacBook PRO por um Air M5” — 32.789 views, 22,3× a mediana anterior."),
            ("25–26 Ago", "A virada", "Mochila + MacBook Air 30 dias. A mediana de views dobra; a taxa de like cai de 15,6% para 6,0%."),
            ("01 Set", "O ensaio volta", "“e se?” — 13.151 views. O formato que equilibra alcance e vínculo."),
            ("06 Nov", "O corte atual", "414 vídeos públicos, 56.000 inscritos, 1.380.696 views em 2026."),
        ]
    out = []
    for d, t, n in items:
        out.append(f'<li><span class="tl-date">{d}</span><div><strong>{t}</strong><p>{n}</p></div></li>')
    return "".join(out)


def build(lang):
    global LANG
    LANG = lang
    template = TEMPLATES[lang].read_text(encoding="utf-8")
    replacements = {
        "{{HERO_STRIP}}": hero_strip(),
        "{{CHART_MONTHLY_VIEWS}}": monthly_svg("views"),
        "{{CHART_MONTHLY_LIKES}}": monthly_svg("likes"),
        "{{MONTHLY_TABLE}}": monthly_table(),
        "{{KPI_ROW}}": kpi_row(),
        "{{CHART_FORMAT}}": format_svg(),
        "{{FORMAT_LEGEND}}": format_legend(),
        "{{FORMAT_TABLE}}": format_table(),
        "{{TOP_TABLE}}": top_table(),
        "{{TOP_FRAMES}}": frames(["4N9UMkzNTu4", "b6akAEW0F4k", "9kN0D0Uxg2Y",
                                  "Www-gU4q9lA", "kZ8YSZt5SEw", "qwu_d8aYZ80"], "A"),
        "{{BOTTOM_TABLE}}": bottom_table(),
        "{{BOTTOM_FRAMES}}": frames(["H6NBkGR3bWI", "E5xapLBlcHY", "xWeZaDEbZys",
                                    "Zgp8LDMIXvI", "BJpDGp1YY7k", "j7lRoGTu0V0"], "B"),
        "{{TIMELINE}}": timeline(),
    }
    out = template
    for k, v in replacements.items():
        if k not in out:
            print("warning: placeholder missing", k)
        out = out.replace(k, v)
    path = OUTPUTS[lang]
    path.write_text(out, encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for lang in ("pt", "en"):
        build(lang)


if __name__ == "__main__":
    main()
