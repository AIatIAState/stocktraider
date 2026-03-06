
import io
import requests
import pandas as pd
from datetime import date, timedelta

# Wikipedia blocks the default urllib User-Agent with a 403.
# Sending a browser-like header fixes this.
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


def get_symbols(target_date: date) -> tuple[list[str], list[str]]:
    """
    Returns (train_symbols, test_symbols) for a given date.
    """
    tables = _fetch_wiki_tables()

    sp500_at_date = get_sp500_at_date(target_date)

    # ── Recently removed companies (past 5 years) ─────────────────────────
    # Stocks dropped from the index are often underperformers — including them
    # gives the model genuine loss examples that the current S&P 500 can't provide.
    changes = tables[1].copy()
    changes.columns = [
        ' '.join(str(c) for c in col).strip() if isinstance(col, tuple) else str(col)
        for col in changes.columns
    ]
    changes.rename(columns=lambda c: c.lower().replace(' ', '_'), inplace=True)

    date_col    = next(c for c in changes.columns if 'date' in c)
    removed_col = next((c for c in changes.columns if 'remov' in c and 'ticker' in c), None)
    changes[date_col] = pd.to_datetime(changes[date_col], errors='coerce')

    recent_removals = set()
    if removed_col:
        cutoff = pd.Timestamp(target_date - timedelta(days=365 * 5))
        mask   = (
            (changes[date_col] >= cutoff) &
            (changes[date_col] <= pd.Timestamp(target_date))
        )
        for raw in changes.loc[mask, removed_col].dropna():
            t = _clean_ticker(raw)
            if t:
                recent_removals.add(t)


    train_symbols = sorted(set(sp500_at_date) | recent_removals)

    # ── Test symbols: ~100, sector-balanced from current S&P 500 ─────────
    current = tables[0][['Symbol', 'GICS Sector']].copy()
    current['Symbol'] = current['Symbol'].str.replace('.', '-', regex=False)

    test_symbols = (
        current
        .groupby('GICS Sector', group_keys=False)
        .apply(lambda g: g.head(9))
        .sort_values('GICS Sector')['Symbol']
        .tolist()
    )

    sector_counts = (
        current[current['Symbol'].isin(test_symbols)]
        .groupby('GICS Sector')['Symbol'].count()
    )

    return train_symbols, test_symbols


if __name__ == "__main__":
    target = date(2022, 1, 1)
    train, test = get_symbols(target)

    print(f"\n── Training symbols ({len(train)}) ──")
    print(', '.join(train[:20]), '...')

    print(f"\n── Test symbols ({len(test)}) ──")
    print(', '.join(test))

    with open(f"train_symbols_{target}.txt", "w") as f:
        f.write('\n'.join(train))
    with open(f"test_symbols_{target}.txt", "w") as f:
        f.write('\n'.join(test))

    print(f"\nSaved to train_symbols_{target}.txt and test_symbols_{target}.txt")