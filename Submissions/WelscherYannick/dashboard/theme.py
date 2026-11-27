"""Visual design of the dashboard: colour tokens, CSS and the Plotly template.

Look: deep-space navy with rounded glass cards and soft pastel accents,
loosely inspired by the base tones of Roberts Space Industries (approximated,
no official colour codes, no logo or name used). All colours live here.

Data colours were checked with a palette validator against the card surface
SURFACE (lightness band, chroma, colour-blind separation, contrast >= 3:1).
Lighter pastel tints are used only for UI accents, never for data marks.
"""

import plotly.graph_objects as go
import plotly.io as pio

# --- Tokens -------------------------------------------------------------------
BG_TOP = "#070D17"
BG_BOTTOM = "#0D1B2E"
SURFACE = "#101B2B"  # chart/card surface; data colours validated against it
INK = "#E8F1F8"  # primary text
INK_2 = "#9FB3C8"  # secondary text
INK_3 = "#6B7F95"  # muted text, axis labels
GRID = "rgba(159, 179, 200, 0.10)"
HAIRLINE = "rgba(166, 228, 242, 0.12)"

# Data colours, fixed order: follows the method, never its rank.
METHOD_COLORS = {
    "linear": "#B8892D",  # amber
    "binary": "#00A4C0",  # cyan
    "hash": "#CD718F",  # rose
}
# Pastel tints of the same hues, for chips and accents only.
TINTS = {
    "linear": "#F2D9A6",
    "binary": "#A6E4F2",
    "hash": "#F2BACB",
}
NEUTRAL_BAND = "rgba(159, 179, 200, 0.12)"  # e.g. measurement-noise band

# Version is encoded by line style (latest = solid) and, in the revision chart,
# by marker shape; colour stays with the method.
VERSION_DASH = {"v1": "dash", "v2": "dot", "v3": "solid"}
VERSION_LABELS = {"v1": "v1 (original, recursive)", "v2": "v2 (iterative)", "v3": "v3 (lower bound)"}
VERSION_SYMBOL = {"v2": "circle", "v3": "diamond"}
VERSION_MARKER = {"v2": TINTS["binary"], "v3": METHOD_COLORS["binary"]}
METHOD_LABELS = {"linear": "Linear search", "binary": "Binary search", "hash": "Hash set"}

FONT = '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Segoe UI", sans-serif'
MONO = '"SF Mono", ui-monospace, Menlo, monospace'


# --- Plotly template ------------------------------------------------------------
def _template():
    axis = dict(
        gridcolor=GRID, zeroline=False, showline=False, ticks="", automargin=True,
        tickfont=dict(color=INK_3, size=11), title=dict(font=dict(color=INK_2, size=12), standoff=10),
    )
    return go.layout.Template(layout=dict(
        font=dict(family=FONT, color=INK_2, size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=list(METHOD_COLORS.values()),
        xaxis=axis, yaxis=axis,
        margin=dict(l=12, r=16, t=10, b=12),
        hoverlabel=dict(bgcolor="#162438", bordercolor=HAIRLINE, font=dict(family=FONT, color=INK, size=12)),
        showlegend=False,
    ))


pio.templates["searchlab"] = _template()
TEMPLATE = "searchlab"


# --- CSS ------------------------------------------------------------------------
CSS = f"""
<style>
:root {{
  --ink: {INK}; --ink-2: {INK_2}; --ink-3: {INK_3};
  --surface: {SURFACE}; --hairline: {HAIRLINE};
  --cyan: {METHOD_COLORS['binary']}; --cyan-tint: {TINTS['binary']};
  --amber-tint: {TINTS['linear']}; --rose-tint: {TINTS['hash']};
}}
html, body, .stApp, button, input, textarea {{ font-family: {FONT} !important; }}
.stApp {{
  background:
    radial-gradient(1100px 520px at 8% -8%, rgba(0, 164, 192, 0.20), transparent 60%),
    radial-gradient(900px 480px at 100% 0%, rgba(205, 113, 143, 0.12), transparent 60%),
    radial-gradient(800px 600px at 50% 120%, rgba(184, 137, 45, 0.08), transparent 60%),
    linear-gradient(180deg, {BG_TOP} 0%, #0B1626 55%, {BG_BOTTOM} 100%);
  background-attachment: fixed;
}}
[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}

/* Hero */
.hero {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 18px; }}
.hero h1 {{ font-size: 2.6rem; font-weight: 700; letter-spacing: -0.03em; margin: 0; color: var(--ink);
  background: linear-gradient(90deg, #FFFFFF 0%, var(--cyan-tint) 55%, var(--rose-tint) 100%);
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; padding: 0; }}
.hero .sub {{ color: var(--ink-2); font-size: 1.02rem; margin-top: 4px; }}
.chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.chip {{ font-size: 0.78rem; color: var(--ink-2); padding: 6px 12px; border-radius: 999px;
  background: rgba(166, 228, 242, 0.06); border: 1px solid var(--hairline); white-space: nowrap; }}
.chip b {{ color: var(--ink); font-weight: 600; }}
.chip code {{ font-family: {MONO}; color: var(--cyan-tint); background: none; padding: 0; }}

/* KPI tiles */
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; margin: 6px 0 22px; }}
.kpi {{ position: relative; overflow: hidden; border-radius: 22px; padding: 18px 20px 16px;
  background: rgba(16, 27, 43, 0.72); border: 1px solid var(--hairline);
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04); }}
.kpi::before {{ content: ""; position: absolute; inset: 0 0 auto 0; height: 3px; background: var(--accent, var(--cyan)); opacity: .85; }}
.kpi .label {{ font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink-3); }}
.kpi .value {{ font-size: 1.9rem; font-weight: 650; letter-spacing: -0.02em; color: var(--ink); margin-top: 6px; }}
.kpi .note {{ font-size: 0.82rem; color: var(--ink-2); margin-top: 2px; }}

/* Glass cards: st.container(key="card-...") */
[class*="st-key-card"] {{
  border-radius: 24px; padding: 18px 20px 14px;
  background: rgba(16, 27, 43, 0.78); border: 1px solid var(--hairline);
  backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}}
.card-title {{ font-size: 1.02rem; font-weight: 620; color: var(--ink); margin: 0; }}
.card-sub {{ font-size: 0.82rem; color: var(--ink-3); margin: 2px 0 6px; }}

/* Legend */
.legend {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: center; font-size: 0.84rem; color: var(--ink-2); margin: 2px 0 12px; }}
.legend .sw {{ display: inline-block; width: 22px; height: 0; border-top: 2.5px solid; vertical-align: middle; margin-right: 7px; border-radius: 2px; }}
.legend .sw.dash {{ border-top-style: dashed; }}
.legend .sw.dot {{ border-top-style: dotted; }}
.legend .dot {{ display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 7px; vertical-align: middle; }}

/* Context line under the filters */
.context {{ font-size: 0.82rem; color: var(--ink-3); margin: 4px 0 16px; }}
.context b {{ color: var(--ink-2); font-weight: 600; }}

/* Tabs as a rounded segmented control */
.stTabs [role="tablist"] {{ gap: 6px; background: rgba(16, 27, 43, 0.6); padding: 6px; border-radius: 999px;
  border: 1px solid var(--hairline); width: fit-content; max-width: 100%; overflow-x: auto; margin-bottom: 14px; }}
.stTabs [role="tab"] {{ border-radius: 999px; padding: 6px 16px; height: auto; color: var(--ink-2);
  border: none !important; box-shadow: none !important; transition: background .2s ease; }}
.stTabs [role="tab"]::after, .stTabs [role="tab"]::before {{ display: none !important; }}
.stTabs [role="tab"][aria-selected="true"] {{ background: rgba(0, 164, 192, 0.20); color: var(--ink) !important; }}
.stTabs [role="tab"] p {{ font-size: 0.9rem; }}
.stAppDeployButton, [data-testid="stAppDeployButton"] {{ display: none !important; }}

/* Key-value rows on the environment tab */
.kv {{ display: grid; grid-template-columns: minmax(140px, 34%) 1fr; gap: 6px 14px; font-size: 0.88rem; }}
.kv .k {{ color: var(--ink-3); }}
.kv .v {{ color: var(--ink); font-family: {MONO}; font-size: 0.82rem; word-break: break-word; }}

.note-text {{ color: var(--ink-2); font-size: 0.9rem; line-height: 1.55; }}
.note-text code {{ color: var(--cyan-tint); background: rgba(166, 228, 242, 0.06); border-radius: 6px; }}
</style>
"""
