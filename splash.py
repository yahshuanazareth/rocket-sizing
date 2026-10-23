"""
splash.py - the blueprint-style loading screen.

Used in two places so the loading screen looks the same from start to finish:
  - desktop.py shows it while the app's server starts up.
  - app.py shows it while the first calculations (NASA CEA, trade studies)
    run, then removes it once the page is ready.
"""

AUTHOR = "Yahshua Nazareth"

STAGES = [
    "Starting engine server",
    "Loading NASA CEA",
    "Sizing the thrust chamber",
    "Drawing the engine",
    "Running trade studies",
]

CSS = """
#res-splash {
  position: fixed; inset: 0; z-index: 2147483000;
  display: flex; align-items: center; justify-content: center;
  background-color: #0b3866;
  background-image:
    linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px),
    linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size: 120px 120px, 120px 120px, 24px 24px, 24px 24px;
  font-family: Menlo, "DejaVu Sans Mono", Consolas, monospace;
  color: #ffffff;
}
#res-splash .sheet {
  position: relative; width: min(640px, 86vw);
  border: 1.5px solid rgba(255,255,255,0.85);
  outline: 1px solid rgba(255,255,255,0.35); outline-offset: 6px;
  padding: 30px 36px 22px 36px; background: rgba(11,56,102,0.92);
}
#res-splash .title { font-size: 22px; font-weight: 700; letter-spacing: 0.14em; }
#res-splash .sub { margin-top: 6px; font-size: 11px; letter-spacing: 0.16em; color: #cfe3ff; }
#res-splash svg { display: block; width: 100%; height: auto; margin: 18px 0 14px 0; }
#res-splash .wall { fill: none; stroke: #ffffff; stroke-width: 2; }
#res-splash .cl { stroke: #8fd0ff; stroke-width: 1; stroke-dasharray: 14 4 3 4; }
#res-splash .flow {
  stroke: #8fd0ff; stroke-width: 2; stroke-dasharray: 10 14; fill: none;
  animation: res-flow 0.9s linear infinite;
}
@keyframes res-flow { to { stroke-dashoffset: -24; } }
#res-splash .bar { height: 6px; border: 1px solid rgba(255,210,63,0.7); margin: 4px 0 14px 0; }
#res-splash .fill { height: 100%; background: #ffd23f; transition: width 0.4s ease; }
#res-splash ol { list-style: none; margin: 0; padding: 0; font-size: 12px; letter-spacing: 0.08em; }
#res-splash li { padding: 3px 0; color: #ff6b6b; }
#res-splash li.done { color: #5fe08a; }
#res-splash li.now { color: #c39bff; font-weight: 700; }
#res-splash li .mark { display: inline-block; width: 22px; }
#res-splash li.now .mark { animation: res-blink 1s steps(2) infinite; }
@keyframes res-blink { 50% { opacity: 0; } }
#res-splash .foot {
  display: flex; justify-content: space-between; margin-top: 18px; padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.4);
  font-size: 10px; letter-spacing: 0.14em; color: #cfe3ff;
}
#res-splash .pct { color: #ffd23f; }
/* If the app hits an error, get out of the way so the message can be read. */
.stApp:has([data-testid="stException"]) #res-splash { display: none; }
#res-splash .err { margin-top: 14px; color: #ffd27f; font-size: 12px; letter-spacing: 0.06em; }
"""

# A small conical thrust chamber: chamber, converging section, throat, bell.
ENGINE_SVG = """
<svg viewBox="0 0 560 150" aria-hidden="true">
  <line class="cl" x1="10" y1="75" x2="550" y2="75"/>
  <path class="wall" d="M40 30 H250 L320 58 L520 22"/>
  <path class="wall" d="M40 120 H250 L320 92 L520 128"/>
  <path class="wall" d="M40 30 V120"/>
  <path class="flow" d="M60 60 H250 L320 70 L520 50"/>
  <path class="flow" d="M60 75 H540"/>
  <path class="flow" d="M60 90 H250 L320 80 L520 100"/>
</svg>
"""


def splash_html(stage: int, error: str = "") -> str:
    """The loading screen's markup, with stages before `stage` ticked off."""
    stage = max(0, min(stage, len(STAGES)))
    items = []
    for i, name in enumerate(STAGES):
        if i < stage:
            items.append(f'<li class="done"><span class="mark">✓</span>{name}</li>')
        elif i == stage and not error:
            items.append(f'<li class="now"><span class="mark">▸</span>{name}…</li>')
        else:
            items.append(f'<li><span class="mark">·</span>{name}</li>')
    pct = int(100 * stage / len(STAGES))
    err = f'<div class="err">{error}</div>' if error else ""
    return (
        f'<div id="res-splash"><div class="sheet">'
        f'<div class="title">ROCKET ENGINE SIZING TOOL</div>'
        f'<div class="sub">PRELIMINARY THRUST CHAMBER DESIGN · NASA CEA</div>'
        f'{ENGINE_SVG}'
        f'<div class="bar"><div class="fill" style="width:{pct}%"></div></div>'
        f'<ol>{"".join(items)}</ol>{err}'
        f'<div class="foot"><span>PROGRAM BY {AUTHOR.upper()}</span><span class="pct">LOADING {pct}%</span></div>'
        f'</div></div>'
    )


def splash_page(stage: int = 0, error: str = "") -> str:
    """A complete HTML page, for desktop.py to show before the app is ready."""
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        'html,body{margin:0;height:100%;background:#0b3866;}' + CSS +
        f'</style></head><body>{splash_html(stage, error)}</body></html>'
    )
