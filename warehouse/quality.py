"""Data-quality checks run after every load (and by `python -m warehouse check`).

ERROR = impossible data (a bug or a broken source). WARN = suspicious but can be
real (a halt, a special trading day). Checks never change or delete data; they
only report, and every finding is written to data_quality_log.

Duplicate (symbol_id, date) rows have no check: the primary key makes them
impossible, and tests/test_idempotency.py proves Postgres refuses one.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import text

PRICE_LIMITS_CSV = Path(__file__).resolve().parent.parent / "tse_price_limits.csv"

# A normal day follows the previous bar by at most this many calendar days
# (weekend + holiday). Longer gaps are halts: the day after gets a wider limit.
NORMAL_GAP_DAYS = 6
# Gaps longer than this are reported. Nowruz alone can reach ~9 days on the TSE.
MAX_GAP_DAYS = 10
# An active symbol with no new bar for this long has probably stopped reporting.
STALE_DAYS = 7


def seed_price_limits(engine, csv_path: Path) -> int:
    """Make tse_price_limits match tse_price_limits.csv exactly (the csv is the truth).

    Rows are upserted on start_date. Rows no longer in the csv are deleted, since
    a stale limit would silently apply the wrong rule. Nothing references this
    table, so deleting is safe (unlike symbols). Returns the number of csv rows.
    """
    df = pd.read_csv(csv_path, dtype={"evidence": str}, parse_dates=["start_date"])
    df["start_date"] = df["start_date"].dt.date
    df = df.astype(object).where(df.notna(), None)  # empty limit -> NULL, not NaN

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM tse_price_limits WHERE NOT (start_date = ANY(:dates))"),
            {"dates": list(df["start_date"])},
        )
        conn.execute(text("""
            INSERT INTO tse_price_limits (start_date, price_limit, evidence)
            VALUES (:start_date, :price_limit, :evidence)
            ON CONFLICT (start_date) DO UPDATE SET
                price_limit = EXCLUDED.price_limit,
                evidence    = EXCLUDED.evidence
            WHERE (tse_price_limits.price_limit, tse_price_limits.evidence)
                IS DISTINCT FROM (EXCLUDED.price_limit, EXCLUDED.evidence)
        """), df.to_dict("records"))

    return len(df)


# (check_name, severity, SQL). Every query returns symbol_id, date, detail.
CHECKS = [
    ("bad_price", "ERROR", """
        SELECT symbol_id, date, 'a price is missing, zero or negative' AS detail
        FROM daily_bars
        WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
           OR LEAST(open, high, low, close, final_price, prev_final) <= 0
    """),
    ("high_below_low", "ERROR", """
        SELECT symbol_id, date, format('high %s < low %s', high, low)
        FROM daily_bars WHERE high < low
    """),
    ("open_close_outside_range", "ERROR", """
        SELECT symbol_id, date,
               format('open %s / close %s outside [low %s, high %s]', open, close, low, high)
        FROM daily_bars
        WHERE open NOT BETWEEN low AND high OR close NOT BETWEEN low AND high
    """),
    # TSE base-volume rule: on a thin day the final price only moves part of the
    # way from the base price toward the traded prices, so it may sit outside
    # [low, high] (285 real foolad days) but never outside [base .. low-high].
    ("final_outside_range", "ERROR", """
        SELECT symbol_id, date,
               format('final %s outside [%s, %s]', final_price,
                      LEAST(low, prev_final), GREATEST(high, prev_final))
        FROM daily_bars
        WHERE final_price NOT BETWEEN LEAST(low, prev_final) AND GREATEST(high, prev_final)
    """),
    ("negative_volume", "ERROR", """
        SELECT symbol_id, date, format('volume %s', volume)
        FROM daily_bars WHERE volume < 0
    """),
    # The views use k = 1 - dividend / previous close and take LN(k), so a
    # dividend <= 0 or >= the previous close (k <= 0) would crash every view.
    ("bad_dividend", "ERROR", """
        SELECT a.symbol_id, a.date,
               format('dividend %s vs previous close %s', a.amount, p.close)
        FROM corporate_actions a
        LEFT JOIN LATERAL (
            SELECT close FROM daily_bars b
            WHERE b.symbol_id = a.symbol_id AND b.date < a.date
            ORDER BY b.date DESC
            LIMIT 1
        ) p ON TRUE
        WHERE a.action_type = 'dividend'
          AND (a.amount IS NULL OR a.amount <= 0 OR a.amount >= p.close)
    """),
    # symbols.csv is normalised to Persian ک/ی on load (D11); the Arabic forms
    # normalize_fa converts (ك, ي, ى) mean something bypassed that, and text
    # searches would silently miss the row.
    ("arabic_letters", "ERROR", """
        SELECT symbol_id, NULL::date, format('Arabic ك/ي/ى in %s', slug)
        FROM symbols
        WHERE ticker ~ '[كيى]' OR name ~ '[كيى]' OR sector ~ '[كيى]'
    """),
    # Skips event days (base reset) and the first day after a halt: TSE gives
    # both a wider limit. Also skips eras with an unknown (NULL) limit.
    ("price_limit_break", "WARN", f"""
        WITH b AS (
            SELECT d.symbol_id, d.date, d.high, d.low, d.prev_final,
                   LAG(d.final_price) OVER w AS last_final,
                   d.date - LAG(d.date) OVER w AS gap
            FROM daily_bars d
            JOIN symbols s USING (symbol_id)
            WHERE s.market = 'TSE'
            WINDOW w AS (PARTITION BY d.symbol_id ORDER BY d.date)
        ), normal AS (
            SELECT symbol_id, date,
                   GREATEST(high / prev_final - 1, 1 - low / prev_final) AS move
            FROM b
            WHERE prev_final = last_final AND gap <= {NORMAL_GAP_DAYS}
        )
        SELECT n.symbol_id, n.date,
               format('move %s%% vs limit %s%%', round(100 * n.move, 2), round(100 * l.price_limit, 1))
        FROM normal n
        JOIN LATERAL (
            SELECT price_limit FROM tse_price_limits
            WHERE start_date <= n.date
            ORDER BY start_date DESC
            LIMIT 1
        ) l ON TRUE
        WHERE l.price_limit IS NOT NULL
          AND n.move > l.price_limit + 0.0005   -- half a tick of rounding room
    """),
    ("long_gap", "WARN", f"""
        SELECT symbol_id, date, format('%s days since the previous bar', gap)
        FROM (
            SELECT symbol_id, date,
                   date - LAG(date) OVER (PARTITION BY symbol_id ORDER BY date) AS gap
            FROM daily_bars
        ) g
        WHERE gap > {MAX_GAP_DAYS}
    """),
    # pytse leaves halted days out, so today this is 0; kept in case a source
    # starts sending halted days as zero-volume rows.
    ("zero_volume", "WARN", """
        SELECT symbol_id, date, 'volume 0' FROM daily_bars WHERE volume = 0
    """),
    ("stale_symbol", "WARN", f"""
        SELECT s.symbol_id, MAX(d.date),
               format('no new bar for %s days', CURRENT_DATE - MAX(d.date))
        FROM symbols s
        JOIN daily_bars d USING (symbol_id)
        WHERE s.is_active
        GROUP BY s.symbol_id
        HAVING CURRENT_DATE - MAX(d.date) > {STALE_DAYS}
    """),
]


def run_all(engine) -> pd.DataFrame:
    """Run every check, write the findings to data_quality_log, and return them.

    Columns: check_name, severity, symbol_id, slug, date, detail. All rows of one
    run share one run_at, since they are inserted in one transaction.
    """
    frames = []
    with engine.begin() as conn:
        for name, severity, sql in CHECKS:
            rows = conn.execute(text(sql)).all()
            frames.append(pd.DataFrame(rows, columns=["symbol_id", "date", "detail"])
                          .assign(check_name=name, severity=severity))
        found = pd.concat(frames, ignore_index=True)
        if not found.empty:
            records = (found[["check_name", "severity", "symbol_id", "date", "detail"]]
                       .astype(object).where(found.notna(), None).to_dict("records"))
            conn.execute(text("""
                INSERT INTO data_quality_log (check_name, severity, symbol_id, date, detail)
                VALUES (:check_name, :severity, :symbol_id, :date, :detail)
            """), records)
        slugs = dict(conn.execute(text("SELECT symbol_id, slug FROM symbols")).all())

    found["slug"] = found["symbol_id"].map(slugs)
    return found[["check_name", "severity", "symbol_id", "slug", "date", "detail"]]


def report(found: pd.DataFrame) -> int:
    """Print a summary and every finding, ERRORs first. Return the ERROR count."""
    n_err = int((found["severity"] == "ERROR").sum())
    n_warn = int((found["severity"] == "WARN").sum())
    print(f"\nquality check: {n_err} ERROR, {n_warn} WARN (logged to data_quality_log)")
    for severity in ("ERROR", "WARN"):
        part = found[found["severity"] == severity].sort_values(["check_name", "slug", "date"])
        for check_name, group in part.groupby("check_name", sort=False):
            print(f"\n{severity} {check_name} ({len(group)})")
            for r in group.itertuples():
                print(f"  {r.slug:<8} {str(r.date or ''):<10}  {r.detail}")
    return n_err
