import io
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup
# DJIA components as of January 1, 2019
dow_2019 = [
    "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
    "DWDP", "XOM", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
    "MCD", "MRK", "MSFT", "NKE", "PFE", "PG", "TRV", "UNH",
    "UTX", "VZ", "V", "WBA", "WMT", "DIS"
]

# DJIA components as of January 1, 2020
# Change: DWDP → DOW (Apr 2, 2019 — DowDuPont split into Dow Inc.)
dow_2020 = [
    "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
    "DOW", "XOM", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
    "MCD", "MRK", "MSFT", "NKE", "PFE", "PG", "TRV", "UNH",
    "UTX", "VZ", "V", "WBA", "WMT", "DIS"
]

# DJIA components as of January 1, 2021
# Changes (Aug 31, 2020): XOM, PFE, RTX (formerly UTX) → AMGN, CRM, HON
dow_2021 = [
    "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
    "DOW", "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
    "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
    "HON", "VZ", "V", "WBA", "WMT", "DIS"
]

# DJIA components as of January 1, 2022
# No changes in 2021
dow_2022 = dow_2021.copy()

# DJIA components as of January 1, 2023
# No changes in 2022
dow_2023 = dow_2021.copy()

# DJIA components as of January 1, 2024
# No changes in 2023
dow_2024 = dow_2021.copy()

# DJIA components as of January 1, 2025
# Changes: WBA → AMZN (Feb 26, 2024), INTC → NVDA (Nov 1, 2024)
dow_2025 = [
    "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
    "DOW", "AMGN", "GS", "HD", "IBM", "NVDA", "JNJ", "JPM",
    "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
    "HON", "VZ", "V", "AMZN", "WMT", "DIS"
]
def get_all_dow_tickers():
    """Scrape the current DJIA components from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    tickers = []

    # Find the current components table
    for table in soup.find_all("table", class_="wikitable"):

        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("ticker" in h or "symbol" in h for h in headers):
            # skip header
            rows = table.find_all("tr")[1:]

            for row in rows:
                cols = row.find_all(["td", "th"])
                if len(cols) < 2:
                    continue
                texts = [c.get_text(strip=True) for c in cols]

                # Find ticker column
                ticker = None
                for i, h in enumerate(headers):
                    if ("ticker" in h or "symbol" in h) and i < len(texts):
                        ticker = texts[i]

                if ticker:
                    tickers.append(ticker)
    return tickers

# ---------------------------------------------------------
# S&P500
# ---------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _fetch_tables(link) -> list[pd.DataFrame]:
    """Fetch the S&P 500 Wikipedia page and return its HTML tables."""
    response = requests.get(link, headers=_HEADERS, timeout=15)
    response.raise_for_status()
    return pd.read_html(io.StringIO(response.text))


def _clean_ticker(raw) -> str | None:
    """Normalise a ticker string — returns None if invalid."""
    cleaned = str(raw).strip().replace('.', '-')
    return cleaned if cleaned and cleaned.lower() != 'nan' else None


def get_sp500_at_date(target_date: date) -> list[str]:
    """
    Reconstructs approximate S&P 500 membership at target_date by starting
    from the current list and unwinding Wikipedia's change log.
    Reliable post-2010; has minor gaps for earlier dates.
    """
    tables = _fetch_tables(_SP500_WIKI_URL)

    # Current members
    constituents = set(
        tables[0]['Symbol'].str.replace('.', '-', regex=False).tolist()
    )

    # Change log
    changes = tables[1].copy()
    # Flatten any MultiIndex columns Wikipedia sometimes produces
    changes.columns = [
        ' '.join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col)
        for col in changes.columns
    ]
    changes.rename(columns=lambda c: c.lower().replace(' ', '_'), inplace=True)

    date_col    = next(c for c in changes.columns if 'date' in c)
    added_col   = next((c for c in changes.columns if 'added'  in c and 'ticker' in c), None)
    removed_col = next((c for c in changes.columns if 'remov'  in c and 'ticker' in c), None)

    changes[date_col] = pd.to_datetime(changes[date_col], errors='coerce')
    changes = changes.dropna(subset=[date_col]).sort_values(date_col, ascending=False)

    for _, row in changes.iterrows():
        if row[date_col].date() <= target_date:
            break  # all remaining changes pre-date our target — stop

        # Undo this change: remove additions, restore removals
        if added_col:
            t = _clean_ticker(row.get(added_col, ''))
            if t:
                constituents.discard(t)
        if removed_col:
            t = _clean_ticker(row.get(removed_col, ''))
            if t:
                constituents.add(t)

    return sorted(constituents)


# --------------------------------------------------
# NASDAQ 100
# --------------------------------------------------

_NDX_WIKI_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"

# Wikipedia's Nasdaq-100 change-log uses varied column naming; we search
# for these substrings (lowercased) to locate the right columns.
_NDX_DATE_HINTS    = ("date",)
_NDX_ADDED_HINTS   = ("added", "addition")
_NDX_REMOVED_HINTS = ("removed", "deletion", "removal")
_NDX_TICKER_HINTS  = ("ticker", "symbol")


def _find_col(columns: list[str], *keyword_groups: tuple[str, ...]) -> str | None:
    """
    Return the first column name that contains at least one keyword from
    *every* group (all groups must match).  Groups are AND-ed; keywords within
    a group are OR-ed.
    """
    for col in columns:
        col_lower = col.lower()
        if all(any(kw in col_lower for kw in group) for group in keyword_groups):
            return col
    return None


def _parse_ndx_changes(changes_df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise the Nasdaq-100 change-log DataFrame so it has standardised
    columns: date, added_ticker, removed_ticker.

    Wikipedia's table layout for Nasdaq-100 has changed over time.  The most
    common layouts are handled here.
    """
    # Flatten MultiIndex columns
    changes_df = changes_df.copy()
    changes_df.columns = [
        " ".join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col)
        for col in changes_df.columns
    ]
    cols = list(changes_df.columns)

    # --- locate date column ---
    date_col = _find_col(cols, _NDX_DATE_HINTS)
    if date_col is None:
        raise ValueError(f"Cannot find a date column in {cols}")

    # --- locate added ticker ---
    # Try "Added Ticker" / "Addition Ticker" / "Added Symbol" etc.
    added_col = (
        _find_col(cols, _NDX_ADDED_HINTS, _NDX_TICKER_HINTS)
        or _find_col(cols, _NDX_ADDED_HINTS)
    )

    # --- locate removed ticker ---
    removed_col = (
        _find_col(cols, _NDX_REMOVED_HINTS, _NDX_TICKER_HINTS)
        or _find_col(cols, _NDX_REMOVED_HINTS)
    )

    # Build a clean frame
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(changes_df[date_col], errors="coerce")
    out["added_ticker"] = (
        changes_df[added_col].apply(_clean_ticker) if added_col else None
    )
    out["removed_ticker"] = (
        changes_df[removed_col].apply(_clean_ticker) if removed_col else None
    )
    return out.dropna(subset=["date"]).sort_values("date", ascending=False)


def get_nasdaq100_at_date(target_date: date) -> list[str]:
    """
    Reconstructs approximate Nasdaq-100 membership at *target_date* by
    starting from the current list and unwinding Wikipedia's change log.
    Reliable post ~2012; earlier dates have limited change-log coverage.

    Parameters
    ----------
    target_date:
        The date for which you want the index composition.

    Returns
    -------
    list[str]
        Sorted list of ticker symbols that were in the Nasdaq-100 on
        *target_date*.
    """
    tables = _fetch_tables(_NDX_WIKI_URL)

    # ------------------------------------------------------------------
    # 1. Locate the current-constituents table
    #    Wikipedia's Nasdaq-100 page typically has a table whose columns
    #    include "Company", "Ticker" / "Symbol" and "GICS Sector".
    # ------------------------------------------------------------------
    constituents_df: pd.DataFrame | None = None
    for tbl in tables:
        flat_cols = [
            " ".join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col)
            for col in tbl.columns
        ]
        ticker_col = next(
            (c for c in flat_cols if any(kw in c.lower() for kw in ("ticker", "symbol"))),
            None,
        )
        if ticker_col and len(tbl) >= 90:  # NDX has 101 members
            tbl.columns = flat_cols
            constituents_df = tbl
            break

    if constituents_df is None:
        raise RuntimeError(
            "Could not locate the Nasdaq-100 constituents table on Wikipedia. "
            "The page layout may have changed."
        )

    ticker_col = next(
        c for c in constituents_df.columns
        if any(kw in c.lower() for kw in ("ticker", "symbol"))
    )
    constituents: set[str] = set(
        constituents_df[ticker_col]
        .dropna()
        .astype(str)
        .str.strip()
        .str.replace(".", "-", regex=False)
        .tolist()
    )
    constituents.discard("nan")

    # ------------------------------------------------------------------
    # 2. Locate the change-log table
    #    It is usually the table that contains both an "added" and a
    #    "removed" column, or columns mentioning "date" together with
    #    ticker-like columns, and has far fewer rows than the main table.
    # ------------------------------------------------------------------
    changes_df: pd.DataFrame | None = None
    for tbl in tables:
        if tbl is constituents_df:
            continue
        flat_cols = [
            " ".join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col)
            for col in tbl.columns
        ]
        col_lower = " ".join(flat_cols).lower()
        has_date = any(kw in col_lower for kw in _NDX_DATE_HINTS)
        has_add = any(kw in col_lower for kw in _NDX_ADDED_HINTS)
        has_rem = any(kw in col_lower for kw in _NDX_REMOVED_HINTS)
        if has_date and (has_add or has_rem) and len(tbl) >= 5:
            changes_df = tbl
            break

    if changes_df is None:
        # No change log found — return current members as best guess
        return sorted(constituents)

    # ------------------------------------------------------------------
    # 3. Unwind changes that post-date the target
    # ------------------------------------------------------------------
    changes = _parse_ndx_changes(changes_df)

    for _, row in changes.iterrows():
        if row["date"].date() <= target_date:
            break  # all remaining changes pre-date our target — stop

        # Undo the addition (discard the ticker that was added)
        added = _clean_ticker(row["added_ticker"])
        if added:
            constituents.discard(added)

        # Undo the removal (restore the ticker that was removed)
        removed = _clean_ticker(row["removed_ticker"])
        if removed:
            constituents.add(removed)

    return sorted(constituents)
if __name__ == "__main__":
    print("Fetching all tickers...\n")
    tickers = get_nasdaq100_at_date(date(2022, 3, 7))
    print(f"Fetched {len(tickers)} tickers : {tickers}")