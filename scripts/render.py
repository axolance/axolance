#!/usr/bin/env python3
"""Dessine les cartes SVG animées du profil GitHub axolance.

Données : calendrier de contributions via l'API GraphQL (jeton dans GITHUB_TOKEN).
Sans jeton (ou avec OFFLINE=1), relit data/contributions.json.
STATIC=1 : produit l'état final de chaque animation (captures d'écran).

Règle du dépôt : profil anonyme. Aucun nom réel, aucun nom de dépôt privé :
seuls des compteurs agrégés sortent de l'API.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
LOGIN = os.environ.get("PROFILE_LOGIN", "axolance")
STATIC = os.environ.get("STATIC") == "1"
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "cards"

# Palette de l'avatar : bleu nuit, branchies cyan → rose.
BG, PANEL, LINE = "#0b1020", "#10172e", "#1e2a50"
CYAN, PINK, TEXT, MUTED = "#5ee7ff", "#ff7ad9", "#e6ecff", "#8592c4"
LEVELS = ["#151d3a", "#1b4a6b", "#2c86a8", "#4fc3e0", "#5ee7ff"]

TAGLINE = "sysadmin · devops · homelab · ctf"
TILES = [
    ("infra", "infra", ["Proxmox · LXC · KVM", "Nomad · Consul · Vault", "Docker · Firecracker"], CYAN),
    ("reseau", "réseau", ["Cisco · FortiGate", "VLAN · VyOS · Tailscale", "DNS · DHCP · PXE"], "#9b8cff"),
    ("secu", "sécu", ["Hack The Box", "Linux · Active Directory", "durcissement · logs"], PINK),
]
TILE_LINK = f"https://github.com/{LOGIN}?tab=repositories"


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
    if "errors" in payload or not payload.get("data", {}).get("user"):
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
    current = 0
    rev = list(reversed(days))
    if rev and rev[0][1] == 0:  # aujourd'hui pas encore commencé : on ne casse pas la série
        rev = rev[1:]
    for _, n in rev:
        if not n:
            break
        current += 1
    return current, longest


def months(days: list) -> list[tuple[str, int]]:
    acc: dict[str, int] = {}
    for d, n in days:
        acc[d[:7]] = acc.get(d[:7], 0) + n
    keys = sorted(acc)[-12:]
    return [(k, acc[k]) for k in keys]


# ---------------------------------------------------------------- SVG

def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


FONTS = (
    "@font-face{font-family:'Mono';font-weight:400;src:url(data:font/woff;base64,%s)}"
    "@font-face{font-family:'Mono';font-weight:800;src:url(data:font/woff;base64,%s)}"
) % (b64(ROOT / "fonts/mono-400.woff"), b64(ROOT / "fonts/mono-800.woff"))

BASE_CSS = f"""
text{{font-family:'Mono',ui-monospace,monospace;fill:{TEXT}}}
.muted{{fill:{MUTED}}}
.rise{{animation:rise .7s cubic-bezier(.2,.8,.2,1) both}}
.pop{{animation:pop .5s cubic-bezier(.3,1.6,.5,1) both;transform-box:fill-box;transform-origin:center}}
.grow{{animation:grow .8s cubic-bezier(.2,.8,.2,1) both;transform-box:fill-box;transform-origin:bottom}}
.fade{{animation:fade .4s ease-out both}}
.pulse{{animation:pulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
.blink{{animation:blink 1s steps(1) infinite}}
@keyframes rise{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{from{{opacity:0;transform:scale(.6)}}to{{opacity:1;transform:none}}}}
@keyframes grow{{from{{transform:scaleY(0)}}to{{transform:none}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes pulse{{0%,100%{{opacity:1;transform:none}}50%{{opacity:.35;transform:scale(1.8)}}}}
@keyframes blink{{50%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""
STATIC_CSS = "*{animation:none!important}"


def svg(w: int, h: int, body: str, label: str) -> str:
    css = FONTS + BASE_CSS + (STATIC_CSS if STATIC else "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">'
        f"<title>{escape(label)}</title><style>{css}</style>"
        f'<defs><linearGradient id="gill" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{PINK}"/></linearGradient></defs>'
        f"{body}</svg>"
    )


def d(seconds: float) -> str:
    return f' style="animation-delay:{seconds:.2f}s"'


def frame(w: int, h: int) -> str:
    return (
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="14" fill="{BG}" stroke="{LINE}"/>'
        f'<rect x="24" y="0" width="{w-48}" height="2" rx="1" fill="url(#gill)" opacity=".9"/>'
    )


def hero(data: dict) -> str:
    w, h = 1000, 250
    name = LOGIN
    # Reflet cyan → rose qui traverse le pseudo (SMIL : background-clip:text n'existe pas en SVG).
    sweep = "" if STATIC else (
        '<animateTransform attributeName="gradientTransform" type="translate" '
        'values="-1 0;1 0" dur="4s" begin="1.2s" repeatCount="indefinite"/>'
    )
    # Frappe au clavier de la ligne de titre : un masque qui s'élargit par crans.
    chars = len(TAGLINE) + 2  # « $ » + espace
    cw = 13.2
    typing = "" if STATIC else (
        f'<animate attributeName="width" from="0" to="{chars*cw+4:.0f}" dur="{chars*0.055:.2f}s" '
        f'begin="1s" fill="freeze" calcMode="discrete" '
        f'values="{";".join(f"{i*cw:.1f}" for i in range(chars+1))}"/>'
    )
    start_w = f"{chars*cw+4:.0f}" if STATIC else "0"
    cursor_x = 250 + chars * cw + 4
    body = frame(w, h) + f"""
<defs>
  <linearGradient id="sheen" x1="0" x2="1" y1="0" y2="0">
    <stop offset="0" stop-color="{TEXT}"/><stop offset=".42" stop-color="{TEXT}"/>
    <stop offset=".5" stop-color="{CYAN}"/><stop offset=".56" stop-color="{PINK}"/>
    <stop offset=".64" stop-color="{TEXT}"/><stop offset="1" stop-color="{TEXT}"/>{sweep}
  </linearGradient>
  <clipPath id="av"><circle cx="128" cy="125" r="80"/></clipPath>
  <clipPath id="type"><rect x="248" y="140" width="{start_w}" height="30">{typing}</rect></clipPath>
</defs>
<g class="pop"{d(.1)}>
  <circle cx="128" cy="125" r="86" fill="none" stroke="url(#gill)" stroke-width="3"/>
  <image href="data:image/png;base64,{b64(ROOT / 'assets/avatar.png')}" x="48" y="45" width="160" height="160" clip-path="url(#av)"/>
</g>
<text x="248" y="118" font-size="64" font-weight="800" fill="url(#sheen)" class="rise"{d(.35)}>{escape(name)}</text>
<g clip-path="url(#type)"><text x="250" y="162" font-size="22" class="muted"><tspan fill="{CYAN}">$ </tspan>{escape(TAGLINE)}</text></g>
<rect x="{cursor_x:.0f}" y="144" width="11" height="22" fill="{PINK}" class="blink"/>
<g class="rise"{d(1.0 + chars*0.055)}>
  <circle cx="256" cy="200" r="5" fill="#3ee08f" class="pulse"/>
  <circle cx="256" cy="200" r="5" fill="#3ee08f"/>
  <text x="270" y="205" font-size="15" class="muted">en ligne · {data['total']} contribution{'s' if data['total'] > 1 else ''} cette année</text>
</g>"""
    return svg(w, h, body, f"{name} — {TAGLINE}")


def tile(key: str, title: str, lines: list[str], color: str, i: int) -> str:
    w, h = 324, 170
    base = .15 + i * .15
    rows = "".join(
        f'<text x="24" y="{86 + n*26}" font-size="15" class="muted rise"{d(base + .25 + n*.1)}>{escape(t)}</text>'
        for n, t in enumerate(lines)
    )
    body = frame(w, h) + f"""
<g class="pop"{d(base)}><rect x="24" y="26" width="10" height="10" rx="2" fill="{color}"/></g>
<text x="44" y="38" font-size="20" font-weight="800" fill="{color}" class="rise"{d(base + .05)}>{escape(title)}</text>
<rect x="24" y="54" width="276" height="1" fill="{LINE}"/>
{rows}"""
    return svg(w, h, body, f"{title} : " + ", ".join(lines))


def activity(data: dict) -> str:
    w, h = 1000, 330
    days = data["days"][-371:]
    cur, best = streaks(data["days"])
    mon = months(data["days"])
    # Compteurs
    stats = [
        ("contributions / an", data["total"]),
        ("série en cours", f"{cur} j"),
        ("meilleure série", f"{best} j"),
        ("dépôts publics", data["publicRepos"]),
    ]
    out = [frame(w, h)]
    for i, (lab, val) in enumerate(stats):
        x = 32 + i * 240
        out.append(
            f'<g class="rise"{d(.1 + i*.1)}><text x="{x}" y="58" font-size="30" font-weight="800" '
            f'fill="url(#gill)">{escape(str(val))}</text>'
            f'<text x="{x}" y="82" font-size="13" class="muted">{escape(lab)}</text></g>'
        )
    out.append(f'<rect x="32" y="102" width="936" height="1" fill="{LINE}"/>')

    # Heatmap : 53 semaines × 7 jours, apparition colonne par colonne.
    first = dt.date.fromisoformat(days[0][0])
    pad = (first.weekday() + 1) % 7  # semaines GitHub : dimanche en haut
    cells = [None] * pad + days
    peak = max((n for _, n in days), default=0) or 1
    size, gap = 11, 3
    x0, y0 = 32, 124
    for idx, c in enumerate(cells):
        if c is None:
            continue
        col, row = divmod(idx, 7)
        n = c[1]
        lvl = 0 if n == 0 else min(4, 1 + int(3 * n / peak + .5))
        out.append(
            f'<rect x="{x0 + col*(size+gap)}" y="{y0 + row*(size+gap)}" width="{size}" height="{size}" rx="2" '
            f'fill="{LEVELS[lvl]}" class="fade"{d(.4 + col*.015)}><title>{c[0]} : {n}</title></rect>'
        )

    # Barres mensuelles à droite de la heatmap.
    bx, by, bw, bh = 800, 124, 168, 98
    mpeak = max((v for _, v in mon), default=0) or 1
    step = bw / max(len(mon), 1)
    for i, (k, v) in enumerate(mon):
        hh = max(2, bh * v / mpeak)
        out.append(
            f'<rect x="{bx + i*step + 1:.1f}" y="{by + bh - hh:.1f}" width="{step-4:.1f}" height="{hh:.1f}" rx="2" '
            f'fill="url(#gill)" class="grow"{d(.9 + i*.05)}><title>{k} : {v}</title></rect>'
        )
    out.append(f'<text x="{bx}" y="{by + bh + 22}" font-size="12" class="muted">12 derniers mois</text>')

    # Légende
    ly = 250
    out.append(f'<text x="32" y="{ly + 10}" font-size="12" class="muted">moins</text>')
    for i, c in enumerate(LEVELS):
        out.append(f'<rect x="{80 + i*16}" y="{ly}" width="11" height="11" rx="2" fill="{c}"/>')
    out.append(f'<text x="{82 + 5*16}" y="{ly + 10}" font-size="12" class="muted">plus</text>')
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out.append(f'<text x="968" y="300" font-size="12" class="muted" text-anchor="end">mis à jour le {stamp}</text>')
    out.append(
        f'<text x="32" y="300" font-size="13" class="muted">'
        f'<tspan fill="{CYAN}">$</tspan> uptime --since {escape(data["createdAt"][:10])}</text>'
    )
    return svg(w, h, "".join(out), f"Activité GitHub : {data['total']} contributions sur un an")


def main() -> None:
    data = fetch()
    OUT.mkdir(exist_ok=True)
    files = {"hero.svg": hero(data), "activity.svg": activity(data)}
    for i, t in enumerate(TILES):
        files[f"{t[0]}.svg"] = tile(*t, i)
    for name, content in files.items():
        (OUT / name).write_text(content)
    print("cartes :", ", ".join(sorted(files)), "| static" if STATIC else "")


if __name__ == "__main__":
    main()
