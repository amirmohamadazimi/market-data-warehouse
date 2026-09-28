"""Warehouse app: explore prices, see data health, manage symbols.

Run from the repo root:  streamlit run app.py

Reads only from SQL (views and tables), never from raw files, so it can never
show unadjusted prices by accident.
"""

import contextlib
import io
from datetime import timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import text

from warehouse.db import get_engine

st.set_page_config(page_title="Market Data Warehouse", layout="wide")


@st.cache_resource
def engine():
    return get_engine()


@st.cache_data(ttl=300)
def q(sql: str, **params) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def refresh():
    q.clear()
    st.rerun()


st.title("Market Data Warehouse")
explore, health, symbols = st.tabs(["Explore", "Health", "Symbols"])

# --------------------------------------------------------------------- Explore
with explore:
    universe = q("SELECT slug, market FROM symbols WHERE is_active ORDER BY market DESC, slug")
    bounds = q("SELECT MIN(date) AS lo, MAX(date) AS hi FROM daily_bars").iloc[0]
    if pd.isna(bounds.lo):
        st.info("No data yet. Run `python -m warehouse init` and `python -m warehouse update`.")
        st.stop()

    c1, c2 = st.columns([2, 1])
    picked = c1.multiselect(
        "Symbols", universe["slug"].tolist(),
        default=[s for s in ("foolad", "spy") if s in set(universe["slug"])],
        format_func=lambda s: f"{s} ({universe.set_index('slug').at[s, 'market']})",
    )
    start, end = c2.date_input(
        "Dates", value=(max(bounds.lo, bounds.hi - timedelta(days=3 * 365)), bounds.hi),
        min_value=bounds.lo, max_value=bounds.hi,
    )
    if not picked:
        st.stop()

    prices = q("""
        SELECT s.slug, p.date, p.price::float AS price
        FROM v_adjusted_prices p JOIN symbols s USING (symbol_id)
        WHERE s.slug = ANY(:slugs) AND p.date BETWEEN :start AND :end
        ORDER BY p.date
    """, slugs=picked, start=start, end=end)
    wide = prices.pivot(index="date", columns="slug", values="price")

    st.subheader("Adjusted price, first day = 100")
    st.caption("TSE trades Sat-Wed and the US Mon-Fri, so days one market is closed "
               "are carried forward in this chart only.")
    st.line_chart(wide.ffill().div(wide.bfill().iloc[0]).mul(100))

    vol = q("""
        SELECT s.slug, v.date, v.vol_20d::float AS vol_20d
        FROM v_rolling_vol v JOIN symbols s USING (symbol_id)
        WHERE s.slug = ANY(:slugs) AND v.date BETWEEN :start AND :end
    """, slugs=picked, start=start, end=end)
    st.subheader("20-day volatility (annualised)")
    st.line_chart(vol.pivot(index="date", columns="slug", values="vol_20d").ffill())

    if len(picked) > 1:
        corr = q("""
            SELECT * FROM correlation_matrix(:start, :end)
            WHERE slug_a = ANY(:slugs) AND slug_b = ANY(:slugs)
        """, slugs=picked, start=start, end=end)
        st.subheader("Correlation of daily log returns")
        st.caption("Only days where both symbols traded; a TSE/US pair shares Mon-Wed "
                   "only, and same-day TSE/US correlation understates the real link.")
        m1, m2 = st.columns([3, 2])
        m1.dataframe(corr.pivot(index="slug_a", columns="slug_b", values="corr").round(2))
        m2.dataframe(corr.pivot(index="slug_a", columns="slug_b", values="n_days"))
        m2.caption("Days used per pair")

    st.subheader("Rows per symbol")
    st.dataframe(prices.groupby("slug")["date"].agg(rows="count", first="min", last="max"))

# ---------------------------------------------------------------------- Health
with health:
    last = q("SELECT MAX(run_at) AS run_at FROM data_quality_log").iloc[0].run_at
    top1, top2 = st.columns([3, 1])
    if top2.button("Run checks now"):
        from warehouse.quality import run_all

        run_all(engine())
        refresh()
    if pd.isna(last):
        top1.info("No quality run yet.")
    else:
        found = q("""
            SELECT l.severity, l.check_name, s.slug, l.date, l.detail
            FROM data_quality_log l LEFT JOIN symbols s USING (symbol_id)
            WHERE l.run_at = :run_at
            ORDER BY l.severity, l.check_name, s.slug, l.date
        """, run_at=last)
        n_err = int((found.severity == "ERROR").sum())
        top1.markdown(f"Last run **{last:%Y-%m-%d %H:%M} UTC**: "
                      f"{':red[' if n_err else ''}**{n_err} ERROR**{']' if n_err else ''}, "
                      f"**{int((found.severity == 'WARN').sum())} WARN**")
        st.dataframe(found.groupby(["severity", "check_name"]).size().rename("findings"))
        st.dataframe(found, hide_index=True, width="stretch")

# --------------------------------------------------------------------- Symbols
with symbols:
    st.dataframe(q("""
        SELECT s.slug, s.ticker, s.market, s.name, s.vendor_id, s.is_active,
               COUNT(d.date) AS rows, MIN(d.date) AS first, MAX(d.date) AS last,
               s.analysis_from
        FROM symbols s LEFT JOIN daily_bars d USING (symbol_id)
        GROUP BY s.symbol_id ORDER BY s.market DESC, s.slug
    """), hide_index=True, width="stretch")

    with st.form("add"):
        st.markdown("**Add a symbol** (written to symbols.csv first, then the database)")
        a1, a2, a3 = st.columns(3)
        ticker = a1.text_input("Ticker", placeholder="فملی or GLD")
        market = a2.selectbox("Market", ["TSE", "GLOBAL"])
        slug = a3.text_input("Slug", placeholder="fameli")
        b1, b2 = st.columns(2)
        name = b1.text_input("Name (TSE: looked up if empty)")
        sector = b2.text_input("Sector (optional)")
        if st.form_submit_button("Add"):
            from warehouse.symbols import SYMBOLS_CSV, add_symbol

            try:
                row = add_symbol(engine(), SYMBOLS_CSV, ticker=ticker, market=market,
                                 slug=slug.strip(), name=name or None, sector=sector or None)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success(f"Added {row['slug']} ({row['vendor_id']}, {row['name']}). "
                           "Run an update to fetch its data.")
                q.clear()

    st.markdown("**Update** (fetch, load, check). TSE needs an Iranian IP; "
                "each blocked TSE symbol waits for a timeout, so pick GLOBAL to skip them.")
    u1, u2 = st.columns([1, 3])
    which = u1.selectbox("Markets", ["ALL", "GLOBAL", "TSE"])
    if u2.button("Run update"):
        from warehouse.fetch import fetch_all
        from warehouse.load import load_all
        from warehouse.quality import report, run_all

        out = io.StringIO()
        with st.spinner("Updating..."), contextlib.redirect_stdout(out):
            fetch_all(engine(), which)
            load_all(engine())
            report(run_all(engine()))
        st.code(out.getvalue())
        q.clear()
