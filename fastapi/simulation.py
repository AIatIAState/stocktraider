import os
from datetime import date, timedelta, datetime

import pandas as pd
from matplotlib import pyplot as plt

from advanced_nn import AdvancedNN
from connector import get_connection
from naive_nn import NaiveNN
from symbol_collector import get_symbols


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

    roi = (end_price / start_price)
    return 100, 100 * roi

def simulate(predictive_model, exit_strategy, training_epochs=100, training_sample_years=4):

    start_date = date(year=2017, month=1, day=1)
    training_length = 365 * training_sample_years + 1

    complete_testing_tickers = []

    # Prepare stock-specific simulation trackers
    transactions = {}
    open_investments = {}
    completed_investments = {}


    # Prepare market simulation trackers
    market_transactions = []
    market_investments = []

    while start_date < date(year=2020, month=12, day=1):

        #Train the model on the training symbols for 4 years
        print(f"----------------------------------------------------")
        print("Beginning Training for period starting: " + start_date.strftime("%Y-%m-%d"))
        print(f"----------------------------------------------------")
        model = predictive_model()

        tickers = []

        for i in range(10):
            train_symbols, test_symbols = get_symbols(start_date + timedelta(days=365 * i))
            tickers.extend([s + '.US' for s in train_symbols])
        tickers = set(tickers)
        print(f"----------------------------------------------------")
        print(f"Training model on {len(tickers)} symbols")
        print(f"----------------------------------------------------")

        model.train(list(tickers), start_date, 365 * 10 + 2, training_epochs)

        #Run the simulation for the test symbols for the proceeding 1 year, 1 day at a time
        current_date = start_date + timedelta(days=training_length)
        end_date = current_date + timedelta(days=365)
        train_symbols, test_symbols = get_symbols(current_date)
        test_symbols = [s + '.US' for s in test_symbols]

        for symbol in test_symbols:
            if symbol not in complete_testing_tickers:
                complete_testing_tickers.append(symbol)
            if symbol not in transactions:
                transactions[symbol] = []
                open_investments[symbol] = []
                completed_investments[symbol] = []
        print("----------------------------------------------------")
        print(f"Beginning Simulation for period: " + current_date.strftime("%Y-%m-%d") + " - " + end_date.strftime("%Y-%m-%d"))
        print("----------------------------------------------------")
        while current_date < end_date:
            print(f"Simulating for date: {current_date.strftime('%Y-%m-%d')}")
            for symbol in test_symbols:

                #Check to sell open investments
                for open_investment in open_investments[symbol]:
                    if exit_strategy(symbol, open_investment, current_date) is True:

                        #Sell the investment and update trackers
                        purchase_price, selling_price = update_earnings(symbol, open_investment, current_date)

                        transactions[symbol].append({"date": open_investment, "transaction": purchase_price, "transaction_type": "buy"})
                        transactions[symbol].append({"date": current_date, "transaction": selling_price, "transaction_type": "sell"})
                        market_transactions.append(
                            {"date": open_investment, "transaction": purchase_price, "transaction_type": "buy"})
                        market_transactions.append(
                            {"date": current_date, "transaction": selling_price, "transaction_type": "sell"})

                        completed_investment = {"purchase_date": open_investment, "selling_date": current_date,
                                        "purchase_price": purchase_price, "selling_price": selling_price}
                        completed_investments[symbol].append(completed_investment)
                        market_investments.append(completed_investment)
                        open_investments[symbol].remove(open_investment)

                #Check if a new investment should be made, only if there isn't an active investment for the stock
                if model.predict(symbol, current_date) is True and len(open_investments[symbol]) == 0:
                    open_investments[symbol].append(current_date)

            #increment for the next day of predictions
            current_date = current_date + timedelta(days=1)


        #Increment the start date by 1 year and repeat the process
        start_date = start_date + timedelta(days=365)

    #Create charts and print results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_dir = f'simulation_results_{timestamp}'
    os.makedirs(save_dir)
    for test_symbol in complete_testing_tickers:
        generate_charts(test_symbol, transactions[test_symbol], completed_investments[test_symbol], save_dir)
    generate_charts("Market", market_transactions, market_investments, save_dir)

def generate_charts(symbol, transactions, investments, save_dir):
    total_invested = 0
    wallet = 0
    sorted_transactions = sorted(transactions, key=lambda x: x['date'])
    dates = []
    earnings_data = []
    expenses_data = []
    wallet_data = []
    roi_data = []
    number_of_investments_data = []
    total_invest_data = []


    for transaction in sorted_transactions:
        dates.append(transaction['date'])

        if transaction['transaction_type'] == "sell":
            wallet += transaction['transaction']
            earnings_data.append(transaction['transaction'] if len(earnings_data) == 0 else earnings_data[-1] + transaction['transaction'])
            expenses_data.append(0 if len(expenses_data) == 0 else expenses_data[-1])
            number_of_investments_data.append(0 if len(number_of_investments_data) == 0 else number_of_investments_data[-1])
            roi_data.append((wallet / total_invested * 100) - 100 if total_invested > 0 else 0)

        else:
            number_of_investments_data.append(1 if len(number_of_investments_data) == 0 else number_of_investments_data[-1] + 1)
            if wallet < transaction['transaction']:
                total_invested += transaction['transaction'] - wallet
                wallet = 0
            else:
                wallet -= transaction['transaction']

            earnings_data.append(0 if len(earnings_data) == 0 else earnings_data[-1])
            expenses_data.append(transaction['transaction'] if len(expenses_data) == 0 else expenses_data[-1] + transaction['transaction'])
            roi_data.append(0 if len(roi_data) == 0 else roi_data[-1])

        wallet_data.append(wallet)
        total_invest_data.append(total_invested)

    roi = (wallet / total_invested * 100) - 100 if total_invested > 0 else 0
    show_investments = False

    #Print Results
    print("----------------------------------------------------")
    print(f"Simulation Results for {symbol}:")
    print("----------------------------------------------------")
    print(f"\tWallet: {wallet:.2f}")
    print(f"\tTotal Invested: {total_invested:.2f}")
    print(f"\tEarnings (Sold): {0 if len(earnings_data) == 0 else earnings_data[-1]:.2f}")
    print(f"\tExpense (Bought): {0 if len(earnings_data) == 0 else expenses_data[-1]:.2f}")
    print(f"\tReturn on investment: {roi:.2f}%")
    print(f"\tNumber of investments: {len(investments)}")
    if show_investments:
        print(f"\tInvestments")
        for investment in investments:
            print(f"\t\t{investment['purchase_date']} --> {investment['selling_date']}      {investment['purchase_price']} --> {investment['selling_price']}")

    #Save Charts
    fig, ax1 = plt.subplots()
    ax1.plot(dates, earnings_data, label='Earnings', color='green')
    ax1.plot(dates, expenses_data, label='Expenses', color='red')
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Amount ($)')
    ax1.legend(loc='upper left')
    fig.suptitle(f'{symbol} Earnings and Expenses Over Time')
    plt.savefig(f'./{save_dir}/simulation_results_{symbol}_earnings_expenses.png')
    plt.show()

    fig2, ax2 = plt.subplots()
    ax2.plot(dates, roi_data, label='ROI', color='blue')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Return on Investment (%)')
    ax2.legend(loc='upper left')
    fig2.suptitle(f'{symbol} Return on Investment Over Time')
    plt.savefig(f'./{save_dir}/simulation_results_{symbol}_roi.png')
    plt.show()

    fig3, ax3 = plt.subplots()
    ax3.plot(dates, number_of_investments_data, label='Number of Investments', color='purple')
    ax3.set_xlabel('Date')
    ax3.set_ylabel('Number of Investments')
    ax3.legend(loc='upper left')
    fig3.suptitle(f'{symbol} Number of Investments Over Time')
    plt.savefig(f'{save_dir}/simulation_results_{symbol}_number_of_investments.png')
    plt.show()

    fig4, ax4 = plt.subplots()
    ax4.plot(dates, wallet_data, label='Wallet', color='orange')
    ax4.plot(dates, total_invest_data, label='Total Invested', color='blue')
    ax4.set_xlabel('Date')
    ax4.set_ylabel('USD ($)')
    ax4.legend(loc='upper left')
    fig4.suptitle(f'{symbol} Wallet Over Time')
    plt.savefig(f'./{save_dir}/simulation_results_{symbol}_wallet.png')
    plt.show()

    simulation_data = pd.DataFrame({"date": dates, "earnings": earnings_data, "expenses": expenses_data, "roi": roi_data, "number_of_investments": number_of_investments_data, "wallet": wallet_data})
    simulation_data.to_csv(f'./{save_dir}/simulation_results_{symbol}_data.csv', index=False)

    investment_data = pd.DataFrame(investments)
    investment_data.to_csv(f'./{save_dir}/simulation_results_{symbol}_investments.csv', index=False)

if __name__ == "__main__":
    naive_nn = NaiveNN
    simulate(naive_nn, general_exit_strategy)