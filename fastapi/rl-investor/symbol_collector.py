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
if __name__ == "__main__":
    print("Fetching all historical DOW tickers...\n")
    tickers = get_all_dow_tickers()
    print(f"Fetched {len(tickers)} tickers : {tickers}")