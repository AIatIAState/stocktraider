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
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _fetch_wiki_tables() -> list[pd.DataFrame]:
    """Fetch the S&P 500 Wikipedia page and return its HTML tables."""
    response = requests.get(_WIKI_URL, headers=_HEADERS, timeout=15)
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
    tables = _fetch_wiki_tables()

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

if __name__ == "__main__":
    print("Fetching all historical DOW tickers...\n")
    tickers = get_all_dow_tickers()
    print(f"Fetched {len(tickers)} tickers : {tickers}")