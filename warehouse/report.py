"""`python -m warehouse readme`: refresh the README's numbers and chart from SQL.

Everything here is read from the database, so the README can't drift from the
data: rerun after every update and commit the result.
"""

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
FIGURE = ROOT / "docs" / "figures" / "coverage.png"
START, END = "<!-- stats:start -->", "<!-- stats:end -->"

# Reference palette (dataviz skill): light surface, ink, and the blue sequential ramp.
SURFACE, INK, INK_2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
EXCLUDED_FILL = "#f0efec"
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def _stats(engine) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    with engine.connect() as conn:
        per_symbol = pd.read_sql(text("""
            SELECT s.slug, s.ticker, s.market, COUNT(d.date) AS rows,
                   MIN(d.date) AS first, MAX(d.date) AS last, s.analysis_from
            FROM symbols s LEFT JOIN daily_bars d USING (symbol_id)
            WHERE s.is_active
            GROUP BY s.symbol_id ORDER BY s.market DESC, s.slug
        """), conn)
        per_year = pd.read_sql(text("""
            SELECT s.slug, EXTRACT(YEAR FROM d.date)::int AS year, COUNT(*) AS days,
                   BOOL_AND(s.analysis_from IS NOT NULL AND d.date < s.analysis_from) AS excluded
            FROM daily_bars d JOIN symbols s USING (symbol_id)
            WHERE s.is_active
            GROUP BY s.slug, year
        """), conn)
        checks = pd.read_sql(text("""
            SELECT severity, COUNT(*) AS n FROM data_quality_log
            WHERE run_at = (SELECT MAX(run_at) FROM data_quality_log)
            GROUP BY severity
        """), conn).set_index("severity")["n"]
    return per_symbol, per_year, checks


def _chart(per_symbol: pd.DataFrame, per_year: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import Patch, Rectangle

    slugs = per_symbol.loc[per_symbol["rows"] > 0, "slug"].tolist()
    markets = per_symbol.set_index("slug")["market"]
    years = list(range(int(per_year["year"].min()), int(per_year["year"].max()) + 1))
    cmap = ListedColormap(BLUE_RAMP)
    norm = BoundaryNorm([1, 50, 100, 150, 200, 225, 245, 270], cmap.N)

    fig, ax = plt.subplots(figsize=(11, 0.42 * len(slugs) + 1.9), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    cells = per_year.set_index(["slug", "year"])
    for row, slug in enumerate(slugs):
        for col, year in enumerate(years):
            if (slug, year) not in cells.index:
                continue
            cell = cells.loc[(slug, year)]
            excluded = bool(cell["excluded"])
            ax.add_patch(Rectangle(
                (col, row), 1, 1,
                facecolor=EXCLUDED_FILL if excluded else cmap(norm(cell["days"])),
                hatch="////" if excluded else None, hatchcolor=MUTED,
                edgecolor=SURFACE, linewidth=2,  # 2px surface gap between cells
            ))

    ax.set_xlim(0, len(years))
    ax.set_ylim(len(slugs), 0)
    ax.set_yticks([i + 0.5 for i in range(len(slugs))],
                  [f"{s}  ({markets[s]})" for s in slugs], color=INK_2, fontsize=9)
    step = 2 if len(years) > 20 else 1
    ax.set_xticks([i + 0.5 for i in range(0, len(years), step)],
                  [str(y) for y in years[::step]], color=MUTED, fontsize=8)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)

    fig.suptitle("Stored trading days per symbol and year", x=0.01, ha="left",
                 color=INK, fontsize=12, fontweight="bold")
    ax.set_title("Blank = no data. Hatched = stored but before the symbol's analysis_from "
                 "(skipped by the views).", loc="left", color=INK_2, fontsize=9)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    bar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.01)
    bar.set_label("trading days in the year", color=INK_2, fontsize=8)
    bar.ax.tick_params(labelsize=7, colors=MUTED, length=0)
    bar.outline.set_visible(False)
    ax.legend(handles=[Patch(facecolor=EXCLUDED_FILL, edgecolor=MUTED, hatch="////",
                             label="stored, excluded from analysis")],
              loc="upper right", bbox_to_anchor=(1, -0.03), frameon=False,
              fontsize=8, labelcolor=INK_2)

    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def _block(per_symbol: pd.DataFrame, checks: pd.Series) -> str:
    loaded = per_symbol[per_symbol["rows"] > 0]
    first, last = loaded["first"].min(), loaded["last"].max()
    lines = [
        START,
        f"_Generated {date.today():%Y-%m-%d} by `python -m warehouse readme` from the database._",
        "",
        "| | |",
        "|---|---|",
        f"| Rows | {int(per_symbol['rows'].sum()):,} daily bars |",
        f"| Symbols | {len(per_symbol)} ({(per_symbol.market == 'TSE').sum()} TSE, "
        f"{(per_symbol.market == 'GLOBAL').sum()} global); {len(loaded)} with data |",
        f"| Date range | {first} to {last} ({last.year - first.year + 1} calendar years) |",
        f"| Last data quality run | {int(checks.get('ERROR', 0))} ERROR, "
        f"{int(checks.get('WARN', 0))} WARN |",
        "",
        "| symbol | ticker | market | rows | first | last | analysis from |",
        "|---|---|---|---:|---|---|---|",
    ]
    for r in per_symbol.itertuples():
        lines.append(
            f"| `{r.slug}` | {r.ticker} | {r.market} | {r.rows:,} | {r.first or '-'} | "
            f"{r.last or '-'} | {r.analysis_from or ''} |"
        )
    missing = per_symbol.loc[per_symbol["rows"] == 0, "slug"].tolist()
    if missing:
        lines += ["", f"No data yet for {', '.join(f'`{s}`' for s in missing)}: "
                      "TSE needs an Iranian IP for the first `update`."]
    lines += ["", "![Stored trading days per symbol and year](docs/figures/coverage.png)", END]
    return "\n".join(lines)


def refresh_readme(engine) -> Path:
    """Rewrite the block between the stats markers in README.md and the chart."""
    per_symbol, per_year, checks = _stats(engine)
    _chart(per_symbol, per_year)
    readme = README.read_text(encoding="utf-8")
    head, _, rest = readme.partition(START)
    _, _, tail = rest.partition(END)
    if not rest:
        raise ValueError(f"README.md has no {START} ... {END} block")
    README.write_text(head + _block(per_symbol, checks) + tail, encoding="utf-8")
    return FIGURE
