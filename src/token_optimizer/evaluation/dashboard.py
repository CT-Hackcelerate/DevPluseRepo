"""Self-contained HTML dashboard for the A/B validation results.

Runs the 8-case / 2-BU A/B suite and renders a single static HTML file with
inline-SVG charts — no plotting library, no server, no network. Open the file in
any browser for the before/after story the hackathon demo needs:

  * KPI tiles (hero = cost savings) — the headline numbers.
  * Cost per case: baseline vs optimised (grouped columns).
  * Quality per case: baseline vs optimised, on the 25-point scale.
  * Input tokens saved per case (single-hue columns).
  * A full data table (always present) so every value is available without color.

Colours are the validated data-viz reference palette: categorical slot 1 (blue)
for the baseline arm, slot 2 (aqua) for the optimised arm; a blue single-hue for
the magnitude chart. Both light and dark modes ship (OS setting + a toggle).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..skills.anchor.indexer import build_index
from ..skills.prd.compressor import compress_prd
from .ab_runner import ABSummary, run_ab_suite
from .datasets import sample_cases


@dataclass
class _CaseRow:
    name: str
    bu: str
    baseline_cost: float
    optimised_cost: float
    baseline_quality: int
    optimised_quality: int
    tokens_saved: int
    compression_pct: float


def _collect(repo: str) -> tuple[ABSummary, list[_CaseRow], float]:
    """Run the suite and gather per-case rows + overall compression."""
    index = build_index(repo)
    summary = run_ab_suite(sample_cases(), index)

    by_name = {c.name: c for c in sample_cases()}
    rows: list[_CaseRow] = []
    raw_total = comp_total = 0
    for r in summary.results:
        compression = compress_prd(by_name[r.name].prd)
        raw_total += compression.raw_tokens
        comp_total += compression.compressed_tokens
        rows.append(
            _CaseRow(
                name=r.name,
                bu=r.bu,
                baseline_cost=r.baseline.cost_usd,
                optimised_cost=r.optimised.cost_usd,
                baseline_quality=r.baseline.quality.total,
                optimised_quality=r.optimised.quality.total,
                tokens_saved=r.baseline.input_tokens - r.optimised.input_tokens,
                compression_pct=compression.reduction_pct,
            )
        )
    overall_compression = 100.0 * (raw_total - comp_total) / raw_total if raw_total else 0.0
    return summary, rows, overall_compression


# ── SVG column-chart primitives ──────────────────────────────────────────────

_W = 780
_H = 320
_ML, _MR, _MT, _MB = 52, 18, 18, 74
_PLOT_W = _W - _ML - _MR
_PLOT_H = _H - _MT - _MB
_BASE_Y = _MT + _PLOT_H


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _column_path(x: float, w: float, top_y: float) -> str:
    """A column with 4px-rounded top corners and a square base at the baseline."""
    r = min(4.0, w / 2, (_BASE_Y - top_y) / 2) if _BASE_Y - top_y > 0 else 0.0
    return (
        f"M{x:.2f},{_BASE_Y:.2f} "
        f"L{x:.2f},{top_y + r:.2f} "
        f"Q{x:.2f},{top_y:.2f} {x + r:.2f},{top_y:.2f} "
        f"L{x + w - r:.2f},{top_y:.2f} "
        f"Q{x + w:.2f},{top_y:.2f} {x + w:.2f},{top_y + r:.2f} "
        f"L{x + w:.2f},{_BASE_Y:.2f} Z"
    )


def _y_axis(y_max: float, ticks: int, fmt) -> str:
    parts: list[str] = []
    for i in range(ticks + 1):
        val = y_max * i / ticks
        y = _BASE_Y - (_PLOT_H * i / ticks)
        parts.append(
            f'<line x1="{_ML}" y1="{y:.2f}" x2="{_W - _MR}" y2="{y:.2f}" '
            f'class="grid" />'
        )
        parts.append(
            f'<text x="{_ML - 8}" y="{y + 3.5:.2f}" text-anchor="end" '
            f'class="tick">{_esc(fmt(val))}</text>'
        )
    return "".join(parts)


def _columns(
    categories: list[str],
    series: list[tuple[str, str, list[float]]],
    *,
    y_max: float,
    y_ticks: int,
    y_fmt,
    label_fmt,
) -> str:
    """Grouped vertical column chart. ``series`` = [(label, css-var, values)]."""
    n = len(series)
    band_w = _PLOT_W / len(categories)
    col_w = min(24.0, (band_w * 0.72 - (n - 1) * 2) / n)
    group_w = n * col_w + (n - 1) * 2

    body: list[str] = [_y_axis(y_max, y_ticks, y_fmt)]
    for i, cat in enumerate(categories):
        band_x0 = _ML + i * band_w
        gx0 = band_x0 + (band_w - group_w) / 2
        for s, (_, var, values) in enumerate(series):
            v = values[i]
            h = (v / y_max) * _PLOT_H if y_max else 0.0
            top = _BASE_Y - h
            x = gx0 + s * (col_w + 2)
            body.append(
                f'<path d="{_column_path(x, col_w, top)}" '
                f'fill="var({var})" />'
            )
            body.append(
                f'<text x="{x + col_w / 2:.2f}" y="{top - 4:.2f}" '
                f'text-anchor="middle" class="vlabel">{_esc(label_fmt(v))}</text>'
            )
        cx = band_x0 + band_w / 2
        body.append(
            f'<text x="{cx:.2f}" y="{_BASE_Y + 12:.2f}" '
            f'transform="rotate(-32 {cx:.2f} {_BASE_Y + 12:.2f})" '
            f'text-anchor="end" class="xlabel">{_esc(cat)}</text>'
        )
    return (
        f'<svg viewBox="0 0 {_W} {_H}" class="chart" role="img" '
        f'preserveAspectRatio="xMidYMid meet">{"".join(body)}</svg>'
    )


def _legend(series: list[tuple[str, str]]) -> str:
    items = "".join(
        f'<span class="key"><span class="swatch" '
        f'style="background:var({var})"></span>{_esc(label)}</span>'
        for label, var in series
    )
    return f'<div class="legend">{items}</div>'


# ── Page assembly ────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, *, hero: bool = False, good: bool = False) -> str:
    cls = "kpi hero" if hero else "kpi"
    vcls = "kpi-val good" if good else "kpi-val"
    return (
        f'<div class="{cls}"><div class="kpi-label">{_esc(label)}</div>'
        f'<div class="{vcls}">{_esc(value)}</div></div>'
    )


def _table(rows: list[_CaseRow]) -> str:
    head = (
        "<tr><th>Case</th><th>BU</th><th>PRD compression</th>"
        "<th>Baseline $</th><th>Optimised $</th><th>Cost saved</th>"
        "<th>Quality (base→opt)</th></tr>"
    )
    body: list[str] = []
    for r in rows:
        saved = 100.0 * (r.baseline_cost - r.optimised_cost) / r.baseline_cost if r.baseline_cost else 0.0
        body.append(
            f"<tr><td>{_esc(r.name)}</td><td>{_esc(r.bu)}</td>"
            f"<td>{r.compression_pct:.1f}%</td>"
            f"<td>${r.baseline_cost:.4f}</td><td>${r.optimised_cost:.4f}</td>"
            f"<td class='good'>-{saved:.1f}%</td>"
            f"<td>{r.baseline_quality} &rarr; {r.optimised_quality} / 25</td></tr>"
        )
    return f'<table class="data"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table>'


def build_dashboard(repo: str = "src") -> str:
    """Run the suite against ``repo`` and return a complete HTML document."""
    summary, rows, overall_compression = _collect(repo)

    names = [r.name for r in rows]
    cost_max = max(max(r.baseline_cost for r in rows), 1e-9)
    cost_y = cost_max * 1.15
    tokens_max = max(r.tokens_saved for r in rows)
    tokens_y = (int(tokens_max / 50) + 1) * 50

    cost_chart = _columns(
        names,
        [
            ("Baseline", "--series-1", [r.baseline_cost for r in rows]),
            ("Optimised", "--series-2", [r.optimised_cost for r in rows]),
        ],
        y_max=cost_y,
        y_ticks=4,
        y_fmt=lambda v: f"${v:.3f}",
        label_fmt=lambda v: f"${v:.4f}",
    )
    quality_chart = _columns(
        names,
        [
            ("Baseline", "--series-1", [float(r.baseline_quality) for r in rows]),
            ("Optimised", "--series-2", [float(r.optimised_quality) for r in rows]),
        ],
        y_max=25,
        y_ticks=5,
        y_fmt=lambda v: f"{v:.0f}",
        label_fmt=lambda v: f"{v:.0f}",
    )
    tokens_chart = _columns(
        names,
        [("Input tokens saved", "--series-1", [float(r.tokens_saved) for r in rows])],
        y_max=tokens_y,
        y_ticks=4,
        y_fmt=lambda v: f"{v:.0f}",
        label_fmt=lambda v: f"{v:.0f}",
    )

    kpis = "".join(
        [
            _kpi("Avg cost savings", f"{summary.avg_cost_savings_pct:.0f}%", hero=True, good=True),
            _kpi("Avg PRD compression", f"{overall_compression:.0f}%"),
            _kpi("Avg quality (optimised)", f"{summary.avg_optimised_quality:.1f} / 25", good=True),
            _kpi("Total input tokens saved", f"{summary.total_tokens_saved:,}"),
        ]
    )

    two_series = [("Baseline (raw PRD → premium model)", "--series-1"), ("Optimised (compressed → anchored → routed)", "--series-2")]

    return _HTML_TEMPLATE.format(
        kpis=kpis,
        num_tests=summary.num_tests,
        num_bus=len(summary.bus),
        legend=_legend(two_series),
        cost_chart=cost_chart,
        quality_chart=quality_chart,
        tokens_chart=tokens_chart,
        table=_table(rows),
        baseline_q=f"{summary.avg_baseline_quality:.1f}",
    )


def write_dashboard(path: str, repo: str = "src") -> str:
    """Build the dashboard and write it to ``path``; return the path."""
    html = build_dashboard(repo)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-palette="#2a78d6,#1baf7a">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>TokenOptimizer — A/B Validation Dashboard</title>
<style>
  .viz-root {{
    color-scheme: light;
    --page: #f9f9f7; --surface-1: #fcfcfb;
    --text-primary: #0b0b0b; --text-secondary: #52514e; --muted: #898781;
    --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
    --good: #006300;
    --series-1: #2a78d6; --series-2: #1baf7a;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) .viz-root {{
      color-scheme: dark;
      --page: #0d0d0d; --surface-1: #1a1a19;
      --text-primary: #ffffff; --text-secondary: #c3c2b7; --muted: #898781;
      --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
      --good: #0ca30c;
      --series-1: #3987e5; --series-2: #199e70;
    }}
  }}
  :root[data-theme="dark"] .viz-root {{
    color-scheme: dark;
    --page: #0d0d0d; --surface-1: #1a1a19;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --good: #0ca30c;
    --series-1: #3987e5; --series-2: #199e70;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .viz-root {{ background: var(--page); color: var(--text-primary);
    min-height: 100vh; padding: 32px clamp(16px, 5vw, 64px); }}
  header {{ display: flex; align-items: baseline; justify-content: space-between;
    gap: 16px; flex-wrap: wrap; margin-bottom: 8px; }}
  h1 {{ font-size: 22px; font-weight: 600; margin: 0; }}
  .sub {{ color: var(--text-secondary); font-size: 13px; margin: 2px 0 24px; }}
  .toggle {{ font: inherit; font-size: 12px; color: var(--text-secondary);
    background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 8px; padding: 6px 12px; cursor: pointer; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px; margin-bottom: 28px; }}
  .kpi {{ background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 18px; }}
  .kpi-label {{ color: var(--text-secondary); font-size: 12px; margin-bottom: 6px; }}
  .kpi-val {{ font-size: 30px; font-weight: 600; }}
  .kpi.hero .kpi-val {{ font-size: 48px; line-height: 1; }}
  .kpi-val.good {{ color: var(--good); }}
  .card {{ background: var(--surface-1); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px 20px 12px; margin-bottom: 22px; }}
  .card h2 {{ font-size: 15px; font-weight: 600; margin: 0 0 2px; }}
  .card .note {{ color: var(--text-secondary); font-size: 12px; margin: 0 0 8px; }}
  .chart {{ width: 100%; height: auto; display: block; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .tick {{ fill: var(--muted); font-size: 10px; font-variant-numeric: tabular-nums; }}
  .xlabel {{ fill: var(--text-secondary); font-size: 10.5px; }}
  .vlabel {{ fill: var(--text-secondary); font-size: 9px; font-variant-numeric: tabular-nums; }}
  .legend {{ display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 6px; }}
  .key {{ display: inline-flex; align-items: center; gap: 7px;
    color: var(--text-secondary); font-size: 12px; }}
  .swatch {{ width: 11px; height: 11px; border-radius: 3px; display: inline-block; }}
  table.data {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  table.data th, table.data td {{ text-align: right; padding: 7px 10px;
    border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }}
  table.data th:first-child, table.data td:first-child,
  table.data th:nth-child(2), table.data td:nth-child(2) {{ text-align: left;
    font-variant-numeric: normal; }}
  table.data th {{ color: var(--text-secondary); font-weight: 600; }}
  table.data td.good, table.data th.good {{ color: var(--good); }}
</style>
</head>
<body>
<div class="viz-root">
  <header>
    <div>
      <h1>Token Optimisation — A/B Validation</h1>
    </div>
    <button class="toggle" id="themeToggle" type="button">Toggle theme</button>
  </header>
  <p class="sub">Baseline (raw PRD &rarr; single premium model, no anchoring) vs
    optimised (compressed PRD &rarr; anchored plan &rarr; routed model),
    across {num_tests} feature requests in {num_bus} business units. Baseline
    quality averaged {baseline_q}/25.</p>

  <div class="kpis">{kpis}</div>

  <div class="card">
    <h2>Cost per feature request</h2>
    <p class="note">USD per planning call at list price. Lower is better.</p>
    {legend}
    {cost_chart}
  </div>

  <div class="card">
    <h2>Plan quality (25-point rubric)</h2>
    <p class="note">Correctness · completeness · anchoring · actionability ·
      no-hallucination. Higher is better; optimised is equal or better in every case.</p>
    {legend}
    {quality_chart}
  </div>

  <div class="card">
    <h2>Input tokens saved per feature request</h2>
    <p class="note">Raw PRD tokens minus compressed PRD tokens.</p>
    {tokens_chart}
  </div>

  <div class="card">
    <h2>All results</h2>
    <p class="note">Every value, available without relying on colour.</p>
    {table}
  </div>
</div>
<script>
  (function () {{
    var btn = document.getElementById("themeToggle");
    btn.addEventListener("click", function () {{
      var root = document.documentElement;
      var cur = root.getAttribute("data-theme");
      var next = cur === "dark" ? "light"
        : cur === "light" ? "dark"
        : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "light" : "dark");
      root.setAttribute("data-theme", next);
    }});
  }})();
</script>
</body>
</html>
"""
