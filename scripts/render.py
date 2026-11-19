#!/usr/bin/env python3
"""Dessine les cartes SVG animées du profil GitHub axolance.

Mise en page inspirée des cartes « éditoriales » (grand titre, tuiles, graphe mensuel,
heatmap), habillée avec la DA du portfolio : noir profond, un seul bleu #0055FF,
DM Sans + mono en capitales espacées, apparition flou → net, lueur bleue et étoiles.

Données : calendrier de contributions via l'API GraphQL (jeton dans GITHUB_TOKEN).
Sans jeton (ou avec OFFLINE=1), relit data/contributions.json.
STATIC=1 : état final de chaque animation (captures d'écran).

Règle du dépôt : profil ANONYME. Aucun nom réel, aucun nom de dépôt privé :
seuls des compteurs agrégés sortent de l'API.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import random
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
LOGIN = os.environ.get("PROFILE_LOGIN", "axolance")
STATIC = os.environ.get("STATIC") == "1"
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "cards"

# Jetons du portfolio (design-tokens.json).
BG, SURFACE, LINE = "#000000", "#0a0d14", "#1c2233"
FG, MUTED, ACCENT, SOFT, OK = "#f2f4f8", "#8a93a6", "#0055ff", "#8fb3ff", "#34d399"
HEAT = ["#151b2b", "#0b2a6b", "#0040c4", "#0055ff", "#8fb3ff"]
MONTHS = ["jan", "fév", "mar", "avr", "mai", "jun", "jul", "aoû", "sep", "oct", "nov", "déc"]

EYEBROW = ("HOMELAB", "Admin systèmes & cybersécurité")
INTRO = ["Infra, DevOps et sécurité offensive.", "Je monte des labs, je les casse, je documente."]
TERMINAL = [
    ("cmd", "nomad status"),
    ("ok", "consul", "Running"),
    ("ok", "vault", "Unsealed"),
    ("ok", "nomad", "Running"),
    ("ok", "proxmox", "3/3 nodes up"),
]
TILES = [
    ("infra", "INFRA", "Proxmox, Nomad", ["Consul, Vault, Firecracker,", "Docker. Tout en IaC."]),
    ("reseau", "RÉSEAU", "VLAN → WAN", ["Cisco, FortiGate, VyOS,", "Tailscale, PXE."]),
    ("secu", "SÉCU", "Hack The Box", ["Pentest, Active Directory,", "durcissement et logs."]),
]


# ---------------------------------------------------------------- données

QUERY = """query($login:String!){user(login:$login){
  createdAt
  repositories(ownerAffiliations:OWNER,privacy:PUBLIC){totalCount}
  contributionsCollection{contributionCalendar{totalContributions
    weeks{contributionDays{date contributionCount}}}}}}"""


def fetch() -> dict:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if os.environ.get("OFFLINE") == "1" or not token:
        if not DATA.exists():
            raise SystemExit("Pas de GITHUB_TOKEN et pas de data/contributions.json : rien à dessiner.")
        return json.loads(DATA.read_text())
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload or not (payload.get("data") or {}).get("user"):
        raise SystemExit(f"Réponse GraphQL inattendue : {payload.get('errors')}")
    u = payload["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    data = {
        "login": LOGIN,
        "createdAt": u["createdAt"],
        "publicRepos": u["repositories"]["totalCount"],
        "total": cal["totalContributions"],
        "days": [[d["date"], d["contributionCount"]] for w in cal["weeks"] for d in w["contributionDays"]],
    }
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(data, indent=1) + "\n")
    return data


def streaks(days: list) -> tuple[int, int]:
    longest = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        longest = max(longest, run)
    rev = list(reversed(days))
    if rev and rev[0][1] == 0:  # journée pas encore commencée : la série n'est pas cassée
        rev = rev[1:]
    current = 0
    for _, n in rev:
        if not n:
            break
        current += 1
    return current, longest


def by_month(days: list) -> list[tuple[str, int]]:
    acc: dict[str, int] = {}
    for d, n in days:
        acc[d[:7]] = acc.get(d[:7], 0) + n
    return [(k, acc[k]) for k in sorted(acc)[-12:]]


_METRICS: dict[str, tuple] = {}


def text_w(s: str, size: float, font: str = "sans-500", spacing: float = 0) -> float:
    """Largeur réelle d'un texte, lue dans la table hmtx de la police embarquée."""
    if font not in _METRICS:
        f = TTFont(ROOT / f"fonts/{font}.woff")
        _METRICS[font] = (f.getBestCmap(), f["hmtx"].metrics, f["head"].unitsPerEm)
    cmap, hmtx, upm = _METRICS[font]
    adv = sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upm * .5 for c in s)
    return adv * size / upm + spacing * len(s)


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


# ---------------------------------------------------------------- briques SVG

def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


FONTS = "".join(
    f"@font-face{{font-family:'{fam}';font-weight:{w};src:url(data:font/woff;base64,{b64(ROOT / f'fonts/{f}.woff')})}}"
    for fam, w, f in [("Sans", 400, "sans-400"), ("Sans", 500, "sans-500"), ("Mono", 400, "mono-400")]
)

EASE = "cubic-bezier(.22,1,.36,1)"  # proche du ressort 200/60 du portfolio
BASE_CSS = f"""
text{{font-family:'Sans',system-ui,sans-serif;fill:{FG}}}
.mono{{font-family:'Mono',ui-monospace,monospace;letter-spacing:.25em}}
.code{{font-family:'Mono',ui-monospace,monospace}}
.muted{{fill:{MUTED}}}
.appear{{animation:appear .9s {EASE} both}}
.fade{{animation:fade .5s ease-out both}}
.grow{{animation:grow 1s {EASE} both;transform-box:fill-box;transform-origin:bottom}}
.span{{animation:span 1.2s {EASE} both;transform-box:fill-box;transform-origin:center}}
.drift{{animation:drift 14s ease-in-out infinite alternate}}
.drift2{{animation:drift 18s ease-in-out infinite alternate-reverse}}
.twinkle{{animation:twinkle 3s ease-in-out infinite}}
.pulse{{animation:pulse 2.4s ease-out infinite;transform-box:fill-box;transform-origin:center}}
.blink{{animation:blink 1s steps(1) infinite}}
@keyframes appear{{from{{opacity:0;filter:blur(10px);transform:translateY(10px)}}to{{opacity:1;filter:blur(0);transform:none}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:none}}}}
@keyframes span{{from{{transform:scaleX(0);opacity:0}}to{{transform:none;opacity:1}}}}
@keyframes drift{{from{{transform:translate(-30px,10px)}}to{{transform:translate(40px,-14px)}}}}
@keyframes twinkle{{0%,100%{{opacity:.15}}50%{{opacity:.9}}}}
@keyframes pulse{{0%{{opacity:.8;transform:scale(1)}}100%{{opacity:0;transform:scale(3)}}}}
@keyframes blink{{50%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
STATIC_CSS = "*{animation:none!important}"

DEFS = f"""
<linearGradient id="card" x1="0" y1="1" x2="0" y2="0">
  <stop offset="0" stop-color="{ACCENT}" stop-opacity=".15"/><stop offset="1" stop-color="#616161" stop-opacity=".09"/>
</linearGradient>
<linearGradient id="hl" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0"/>
  <stop offset=".5" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT}" stop-opacity="0"/></linearGradient>
<linearGradient id="sep" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>
  <stop offset=".5" stop-color="#fff" stop-opacity=".15"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<linearGradient id="shine" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>
  <stop offset=".5" stop-color="#fff" stop-opacity=".07"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<filter id="blur40" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
"""


def svg(w: int, h: int, body: str, label: str, pad: int = 0) -> str:
    """pad : marge transparente autour de la carte, pour l'espacer des voisines dans le README."""
    css = FONTS + BASE_CSS + (STATIC_CSS if STATIC else "")
    W, H = w + 2 * pad, h + 2 * pad
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="{-pad} {-pad} {W} {H}" '
        f'role="img" aria-label="{escape(label)}"><title>{escape(label)}</title><style>{css}</style>'
        f"<defs>{DEFS}</defs>{body}</svg>"
    )


def dl(s: float) -> str:
    return f' style="animation-delay:{s:.2f}s"'


def panel(x: float, y: float, w: float, h: float, cid: str) -> str:
    """Carte du portfolio : surface, dégradé bleu par le bas, bord blanc 7 %, rayon 20."""
    return (
        f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20"/></clipPath>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="{SURFACE}"/>'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="url(#card)"/>'
        f'<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" rx="19.5" fill="none" stroke="#fff" stroke-opacity=".07"/>'
    )


def highlighter(x: float, y: float, w: float, delay: float) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="1.5" fill="url(#hl)" class="span"{dl(delay)}/>'


def shine(cid: str, x: float, y: float, w: float, h: float, begin: float) -> str:
    if STATIC:
        return ""
    return (
        f'<g clip-path="url(#{cid})"><rect x="{x - 160}" y="{y}" width="160" height="{h}" fill="url(#shine)" '
        f'transform="skewX(-18)"><animateTransform attributeName="transform" type="translate" additive="sum" '
        f'values="0 0;{w + 320} 0;{w + 320} 0" keyTimes="0;.35;1" dur="7s" begin="{begin}s" repeatCount="indefinite"/></rect></g>'
    )


def counter(x: float, y: float, value: int, attrs: str, begin: float) -> str:
    """Compte depuis zéro avec des <set> SMIL (une valeur par image)."""
    if STATIC or value <= 0:
        return f'<text x="{x}" y="{y}" {attrs}>{escape(fmt(value))}</text>'
    frames = 16
    out = []
    for k in range(frames + 1):
        v = round(value * (1 - (1 - k / frames) ** 3))
        t0 = begin + k * 0.05
        end = "" if k == frames else f' end="{t0 + 0.05:.2f}s"'
        fill = ' fill="freeze"' if k == frames else ""
        out.append(
            f'<text x="{x}" y="{y}" {attrs} opacity="0">{escape(fmt(v))}'
            f'<set attributeName="opacity" to="1" begin="{t0:.2f}s"{end}{fill}/></text>'
        )
    return "".join(out)


def stars(w: int, h: int, n: int, seed: int) -> str:
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        x, y, r = rnd.uniform(0, w), rnd.uniform(0, h), rnd.choice([.6, .8, 1, 1.2])
        cls = ' class="twinkle"' + dl(rnd.uniform(0, 3)) if rnd.random() < .5 else ""
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#fff" opacity=".5"{cls}/>')
    return "".join(out)


# ---------------------------------------------------------------- cartes

def hero(data: dict) -> str:
    w, h = 1000, 400
    tag, label = EYEBROW
    tag_w = len(tag) * 7.6 + 16
    pill_w = tag_w + len(label) * 6.9 + 26
    # Lueur « soie » : ellipses bleues floutées qui dérivent lentement.
    silk = (
        f'<g clip-path="url(#hc)"><g filter="url(#blur40)" opacity=".55">'
        f'<g class="drift"><ellipse cx="760" cy="90" rx="360" ry="70" fill="{ACCENT}" transform="rotate(-14 760 90)"/></g>'
        f'<g class="drift2"><ellipse cx="560" cy="330" rx="420" ry="46" fill="#0a2fa0" transform="rotate(-10 560 330)"/></g>'
        f"</g></g>"
    )
    title = f'<text x="44" y="214" font-size="108" font-weight="500" letter-spacing="-2" class="appear"{dl(.35)}>{escape(LOGIN)}</text>'
    intro = "".join(
        f'<text x="48" y="{262 + i * 26}" font-size="17" class="muted appear"{dl(.6 + i * .08)}>{escape(t)}</text>'
        for i, t in enumerate(INTRO)
    )
    ax, ay, aw, ah = 650, 44, 300, 300
    photo = (
        f'<g class="appear"{dl(.5)}>'
        f'<clipPath id="ph"><rect x="{ax}" y="{ay}" width="{aw}" height="{ah}" rx="22"/></clipPath>'
        f'<image href="data:image/jpeg;base64,{b64(ROOT / "assets/avatar.jpg")}" x="{ax}" y="{ay}" width="{aw}" height="{ah}" clip-path="url(#ph)" preserveAspectRatio="xMidYMid slice"/>'
        f'<rect x="{ax+.5}" y="{ay+.5}" width="{aw-1}" height="{ah-1}" rx="21.5" fill="none" stroke="#fff" stroke-opacity=".12"/>'
        f'<rect x="{ax+10}" y="{ay+10}" width="98" height="28" rx="14" fill="#000" fill-opacity=".55" stroke="#fff" stroke-opacity=".1"/>'
        f'<circle cx="{ax+27}" cy="{ay+24}" r="4" fill="{OK}" class="pulse"/><circle cx="{ax+27}" cy="{ay+24}" r="4" fill="{OK}"/>'
        f'<text x="{ax+39}" y="{ay+29}" font-size="13">en ligne</text></g>'
    )
    tx, ty, tw, th = 560, 236, 300, 150
    term = [
        f'<g class="appear"{dl(.9)}>',
        f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="12" fill="#0d1018" fill-opacity=".96" stroke="#fff" stroke-opacity=".1"/>',
        f'<rect x="{tx}" y="{ty+28}" width="{tw}" height="1" fill="#fff" fill-opacity=".08"/>',
    ]
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        term.append(f'<circle cx="{tx+16+i*14}" cy="{ty+14}" r="4.5" fill="{c}"/>')
    term.append(f'<text x="{tx+66}" y="{ty+18}" font-size="11" class="code muted">{LOGIN}@lab:~/infra</text></g>')
    for i, line in enumerate(TERMINAL):
        y = ty + 50 + i * 19
        d0 = 1.4 + i * .32
        if line[0] == "cmd":
            body = f'<tspan fill="{FG}">$ {escape(line[1])}</tspan>'
        else:
            body = f'<tspan fill="{OK}">✔ </tspan><tspan fill="{SOFT}">{escape(line[1]):<8}</tspan><tspan fill="{OK}"> {escape(line[2])}</tspan>'
        term.append(f'<text x="{tx+14}" y="{y}" font-size="12" class="code fade" xml:space="preserve"{dl(d0)}>{body}</text>')
    cy = ty + 50 + len(TERMINAL) * 19
    term.append(
        f'<g class="fade"{dl(1.4 + len(TERMINAL) * .32)}><text x="{tx+14}" y="{cy}" font-size="12" class="code">$</text>'
        f'<rect x="{tx+28}" y="{cy-10}" width="7" height="13" fill="{FG}" class="blink"/></g>'
    )
    body = (
        f'<clipPath id="hc"><rect width="{w}" height="{h}" rx="20"/></clipPath>'
        f'<rect width="{w}" height="{h}" rx="20" fill="{BG}"/>{silk}'
        f'<g clip-path="url(#hc)">{stars(w, h, 70, 7)}</g>'
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="19.5" fill="none" stroke="#fff" stroke-opacity=".07"/>'
        f'<g class="appear"{dl(.15)}>'
        f'<rect x="48" y="56" width="{pill_w:.0f}" height="30" rx="10" fill="#fff" fill-opacity=".06" stroke="#fff" stroke-opacity=".08"/>'
        f'<rect x="53" y="61" width="{tag_w:.0f}" height="20" rx="6" fill="{ACCENT}"/>'
        f'<text x="{53 + tag_w/2:.0f}" y="75" font-size="10" font-weight="500" text-anchor="middle" letter-spacing=".6">{tag}</text>'
        f'<text x="{63 + tag_w:.0f}" y="76" font-size="13" class="muted">{escape(label)}</text>'
        f"</g>{highlighter(56, 85, pill_w - 16, .6)}"
        f"{title}{intro}{photo}{''.join(term)}"
    )
    return svg(w, h, body, f"{LOGIN}. {EYEBROW[1]}. {' '.join(INTRO)}", pad=6)


def heatmap(data: dict) -> str:
    w, h = 1000, 210
    days = data["days"][-371:]
    first = dt.date.fromisoformat(days[0][0])
    pad = (first.weekday() + 1) % 7  # semaines GitHub : dimanche en haut
    cells = [None] * pad + days
    peak = max((n for _, n in days), default=0) or 1
    size, gap = 13, 4
    cols = (len(cells) + 6) // 7
    x0 = (w - (cols * (size + gap) - gap)) / 2
    y0 = 66
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%d.%m.%Y")
    out = [panel(0, 0, w, h, "hm"),
           f'<text x="48" y="44" font-size="11" class="mono muted appear"{dl(.1)}>CONTRIBUTIONS</text>',
           f'<text x="{w-48}" y="44" font-size="11" class="mono muted appear" text-anchor="end"{dl(.15)}>MAJ {stamp}</text>']
    for idx, c in enumerate(cells):
        if c is None:
            continue
        col, row = divmod(idx, 7)
        n = c[1]
        lvl = 0 if n == 0 else min(4, 1 + int(3 * n / peak + .5))
        x, y = x0 + col * (size + gap), y0 + row * (size + gap)
        if lvl == 4:
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{size}" height="{size}" rx="3" fill="{ACCENT}" opacity=".7" filter="url(#glow)" class="fade"{dl(.3 + col*.022)}/>')
        out.append(
            f'<rect x="{x:.1f}" y="{y}" width="{size}" height="{size}" rx="3" '
            f'fill="{HEAT[lvl]}" class="fade"{dl(.3 + col*.022)}><title>{c[0]} : {n}</title></rect>'
        )
    return svg(w, h, "".join(out), "Graphe des contributions GitHub, mis à jour chaque jour", pad=6)


def activity(data: dict) -> str:
    w, h = 1000, 340
    days = data["days"]
    mon = by_month(days)
    cur, best = streaks(days)
    active = sum(1 for _, n in days if n)
    busiest = max((n for _, n in days), default=0)
    out = [panel(0, 0, w, h, "ac")]
    out.append(f'<text x="48" y="56" font-size="11" class="mono muted appear"{dl(.1)}>LES 12 DERNIERS MOIS SUR GITHUB</text>')
    unit = "contribution" + ("s" if data["total"] > 1 else "")
    big = 'font-size="58" font-weight="500" letter-spacing="-2"'
    out.append(f'<g class="appear"{dl(.2)}>{counter(46, 116, data["total"], big, .3)}</g>')
    num_w = 46 + text_w(fmt(data["total"]), 58, spacing=-2) + 16
    out.append(f'<text x="{num_w}" y="116" {big} fill="{SOFT}" class="appear"{dl(.3)}>{unit}</text>')

    bx, by, bw, bh = 48, 148, 560, 130
    peak = max((v for _, v in mon), default=0) or 1
    best_i = max(range(len(mon)), key=lambda i: mon[i][1]) if mon else -1
    step = bw / max(len(mon), 1)
    for i, (k, v) in enumerate(mon):
        hh = max(4, bh * v / peak)
        x = bx + i * step
        top = i == best_i and v > 0
        op = "1" if top else (".1" if i == len(mon) - 1 else ".18")
        out.append(
            f'<rect x="{x+4:.1f}" y="{by + bh - hh:.1f}" width="{step-10:.1f}" height="{hh:.1f}" rx="4" '
            f'fill="{ACCENT if top else "#fff"}" fill-opacity="{op}" class="grow"{dl(.4 + i*.06)}><title>{k} : {v}</title></rect>'
        )
        if top:
            out.append(f'<rect x="{x+4:.1f}" y="{by + bh - hh:.1f}" width="{step-10:.1f}" height="{hh:.1f}" rx="4" fill="{ACCENT}" opacity=".5" filter="url(#glow)" class="fade"{dl(1.1)}/>')
            out.append(f'<text x="{x + step/2 - 1:.1f}" y="{by + bh - hh - 10:.1f}" font-size="11" class="code fade" fill="{SOFT}" text-anchor="middle"{dl(1.2)}>{fmt(v)}</text>')
        out.append(f'<text x="{x + step/2 - 1:.1f}" y="{by + bh + 24}" font-size="11" class="code muted" text-anchor="middle">{MONTHS[int(k[5:]) - 1]}</text>')

    sx = 680
    stats = [
        (cur, f" jour{'s' if cur > 1 else ''}", f"série en cours, record : {best}"),
        (active, f" / {len(days)}", "jours avec une contribution"),
        (busiest, "", "le jour le plus actif"),
    ]
    num = 'font-size="40" font-weight="500" letter-spacing="-1"'
    for i, (v, suf, lab) in enumerate(stats):
        y = 110 + i * 82
        d0 = .5 + i * .15
        out.append(f'<g class="appear"{dl(d0)}>{counter(sx, y, v, num, d0 + .1)}'
                   f'<text x="{sx + text_w(fmt(v), 40, spacing=-1) + 6:.1f}" y="{y}" {num} fill="{MUTED}" xml:space="preserve">{escape(suf)}</text>'
                   f'<text x="{sx}" y="{y + 24}" font-size="13" class="muted">{escape(lab)}</text></g>')
        if i < 2:
            out.append(f'<rect x="{sx}" y="{y + 44}" width="272" height="1" fill="url(#sep)"/>')
    out.append(highlighter(48, h - 1.5, w - 96, 1.0))
    return svg(w, h, "".join(out), f"{data['total']} contributions sur les 12 derniers mois", pad=6)


def tile(key: str, cap: str, big: str, lines: list[str], i: int) -> str:
    w, h = 333, 236
    x, y, cw, ch = 6, 6, w - 12, h - 12
    d0 = .15 + i * .12
    out = [panel(x, y, cw, ch, f"t{key}")]
    out.append(f'<text x="{x+26}" y="{y+40}" font-size="11" class="mono muted appear"{dl(d0)}>{escape(cap)}</text>')
    out.append(f'<text x="{x+cw-26}" y="{y+41}" font-size="14" fill="{SOFT}" text-anchor="end" class="appear"{dl(d0 + .05)}>↗</text>')
    out.append(f'<text x="{x+24}" y="{y+108}" font-size="34" font-weight="500" letter-spacing="-1" class="appear"{dl(d0 + .12)}>{escape(big)}</text>')
    for n, t in enumerate(lines):
        out.append(f'<text x="{x+26}" y="{y+146 + n*21}" font-size="14" class="muted appear"{dl(d0 + .22 + n*.06)}>{escape(t)}</text>')
    out.append(shine(f"t{key}", x, y, cw, ch, 2 + i * .8))
    out.append(highlighter(x + 30, y + ch - 1.5, cw - 60, d0 + .5))
    return svg(w, h, "".join(out), f"{cap} : {big}. {' '.join(lines)}")


def main() -> None:
    data = fetch()
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    files = {"hero.svg": hero(data), "heatmap.svg": heatmap(data), "activity.svg": activity(data)}
    for i, t in enumerate(TILES):
        files[f"{t[0]}.svg"] = tile(*t, i)
    for name, content in files.items():
        (OUT / name).write_text(content)
    print("cartes :", ", ".join(sorted(files)), "| static" if STATIC else "")


if __name__ == "__main__":
    main()
