from datetime import date, timedelta
from connector import get_connection
from naive_nn import NaiveNN


def general_exit_strategy(symbol, investment_day, current_day) -> bool:
    """
    :param symbol: symbol of the stock to invest in
    :param investment_day: date of the stock purchase
    :param current_day: current date to decide on
    :return: True if the investment needs to be sold (1% less than or 2% more than original value)
    """

    conn = get_connection(readonly=True)
    where = "(symbol = ? AND timeframe = ? AND date = ?)"
    params: list[object] = [symbol, "daily", investment_day.strftime("%Y%m%d")]

    sql = f"""
        SELECT date, close, open, time, volume
        FROM bars
        WHERE {where}
        ORDER BY date ASC
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    rows = [dict(row) for row in rows]
    if len(rows) == 0:
        return False

    purchase_price = rows[0]['close']
    winning_price = purchase_price * 1.02
    losing_price = purchase_price * .99

    conn = get_connection(readonly=True)
    where = "(symbol = ? AND timeframe = ? AND date = ?) AND (close >= ? OR close <= ?)"
    params: list[object] = [symbol, "daily", current_day.strftime("%Y%m%d"), winning_price, losing_price]

    sql = f"""
        SELECT date, close, open, time, volume
        FROM bars
        WHERE {where}
        ORDER BY date ASC
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    rows = [dict(row) for row in rows]

    if len(rows) == 0:
        return False

    if rows[0]['close'] >= winning_price or rows[0]['close'] <= losing_price:
        return True
    else:
        return False


def update_earnings(symbol, investment_date, closing_date):
    """
    Returns the purchase price and selling price for a given investment
    :param symbol: The ticker of the stock investment
    :param investment_date: The date of the investment purchase
    :param closing_date: The date of the selling of stock
    :return: purchase price, selling price
    """
    start_date = (investment_date - timedelta(days=5))
    end_date = (closing_date + timedelta(days=5))


    where = ["symbol = ?", "timeframe = ?", "date >= ?", "date <= ?"]
    params: list[object] = [symbol, "daily", start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")]

    sql = f"""
        SELECT date, close
        FROM bars
        WHERE {' AND '.join(where)}
    """

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    start_price = None
    end_price = None

    for row in rows:
        if dict(row)['date'] == int(investment_date.strftime("%Y%m%d")):
            start_price = dict(row)['close']

        if dict(row)['date'] == int(closing_date.strftime("%Y%m%d")):
            end_price = dict(row)['close']

    if start_price is None or end_price is None:
        print(f"Unable to update earnings for trade: {investment_date}-{closing_date}. 0 earnings returned.")
        return 0, 0

    return start_price, end_price

def simulate(symbol, start_date, end_date, invest_strategy, exit_strategy, print_result=True, update_interval=1):
    """
    Simulates a series of days using the given investment and exit strategy (skips market closures)
    :param symbol: The ticker of the stock you would like to simulate
    :param start_date: The date of the start of the simulation
    :param end_date: The end date of the simulation
    :param invest_strategy: Function defining the investing strategy
    :param exit_strategy: Function defining the exit strategy
    :param print_result: Boolean to print the results in the terminal on simulation end
    :param update_interval: The amount of days in between each simulation cycle (default 1)
    :return:
    """
    investment_made = False
    investment_date = None
    transactions = []
    investments = []
    total_invested = 0
    wallet = 0

    current_day = start_date

    while current_day < end_date or (investment_made is False and current_day < date.today()):

        if investment_made is False:
            if invest_strategy(symbol, current_day) is True:
                investment_made = True
                investment_date = current_day

        if investment_made is True:
            if exit_strategy(symbol, investment_date, current_day) is True:
                investment_made = False
                purchase_price, selling_price = update_earnings(symbol, investment_date, current_day)
                transactions.append({"date": investment_date, "transaction": purchase_price, "transaction_type": "buy"})
                transactions.append({"date": current_day, "transaction": selling_price, "transaction_type": "sell"})
                completed_investment = {"purchase_date": investment_date, "selling_date": current_day,
                                "purchase_price": purchase_price, "selling_price": selling_price}
                investments.append(completed_investment)
        current_day = current_day + timedelta(days=update_interval)

    sorted_transactions = sorted(transactions, key=lambda x: x['date'])
    for transaction in sorted_transactions:
        if transaction['transaction_type'] == "sell":
            wallet += transaction['transaction']
        else:
            if wallet < transaction['transaction']:
                total_invested += transaction['transaction'] - wallet
                wallet = 0
            else:
                wallet -= transaction['transaction']

    if wallet == 0:
        return investments, 0

    earnings_count = wallet
    expense_count = total_invested
    investments = investments
    roi = (earnings_count / expense_count * 100)

    if print_result:
        print_results(symbol, earnings_count, expense_count, investments, start_date, end_date, True)

    return roi, investments

def print_results(symbol, earnings_count, expense_count, investments, start_date, end_date, show_investments=False):
    print("----------------------------------------------------")
    print(f"Simulation Results for {symbol}:")
    print(f"\tRanging from {start_date.strftime("%m-%d-%Y")} to {end_date.strftime("%m-%d-%Y")}")
    print("----------------------------------------------------")
    print(f"\tEarnings (Sold): {earnings_count:.2f}")
    print(f"\tExpense (Bought): {expense_count:.2f}")
    print(f"\tReturn on investment: {(earnings_count / expense_count * 100):.2f}%")
    print(f"\tNumber of investments: {len(investments)}")
    if show_investments:
        print(f"\tInvestments")
        for investment in investments:
            print(f"\t\t{investment['purchase_date']} --> {investment['selling_date']}      {investment['purchase_price']} --> {investment['selling_price']}")


if __name__ == "__main__":

    start = date(year=2022, month=1, day=1)
    end = date(year=2024, month=12, day=31)
    tickers = ['AAPL.US','MSFT.US','NVDA.US','GOOGL.US','AMZN.US','META.US', 'SPY.US']
    naive_nn = NaiveNN(load_dir='model_v0')
    for ticker in tickers:
        simulate(ticker, start, end, naive_nn.predict, general_exit_strategy, True)