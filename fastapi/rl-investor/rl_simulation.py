import os
from datetime import date, timedelta
from rl_features import preprocess_data, get_opens, get_index
from RLInvestor import RL_Investor
from Metrics import compute_metrics, plot_portfolio_performance, plot_metrics_table
from symbol_collector import get_sp500_at_date

import argparse

training_ending_dates = [
    date(2018, 12, 31),
    date(2019, 12, 31),
    date(2020, 12, 31),
    date(2021, 12, 31),
    date(2022, 12, 31),
    date(2023, 12, 31),
    date(2024, 12, 31),
]

testing_start_dates = [day + timedelta(days=1) for day in training_ending_dates]

testing_end_dates = [
    date(2019, 12, 31),
    date(2020, 12, 31),
    date(2021, 12, 31),
    date(2022, 12, 31),
    date(2023, 12, 31),
    date(2024, 12, 31),
    date(2025, 12, 31)
]

dow_tickers = [
    #2019
    [
        "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
        "DD", "XOM", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
        "MCD", "MRK", "MSFT", "NKE", "PFE", "PG", "TRV", "UNH",
        "RTX", "VZ", "V", "WMT", "DIS"
    ],
    #2020
    [
        "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
        "DD", "XOM", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
        "MCD", "MRK", "MSFT", "NKE", "PFE", "PG", "TRV", "UNH",
        "RTX", "VZ", "V", "WMT", "DIS"
    ],
    #2021
    [
        "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
         "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
        "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
        "HON", "VZ", "V", "WMT", "DIS"
    ],
    #2022
    [
            "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
             "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
            "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
            "HON", "VZ", "V", "WMT", "DIS"
    ],
    #2023
    [
            "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
            "DOW", "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
            "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
            "HON", "VZ", "V", "WMT", "DIS"
    ],
    #2024
    [
            "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
            "DOW", "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
            "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
            "HON", "VZ", "V", "WMT", "DIS"
    ],
    #2025
    [
        "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
        "DOW", "AMGN", "GS", "HD", "IBM", "NVDA", "JNJ", "JPM",
        "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
        "HON", "VZ", "V", "AMZN", "WMT", "DIS"
    ]
]

def simulate(gpu=False, look_back_period=3, episodes=100, index="dow", save_dir="results"):

    all_results = []
    all_metrics = []
    dataset_labels = []

    if index == "dow":
        yearly_tickers = dow_tickers
    else:
        yearly_tickers = [get_sp500_at_date(training_end_date + timedelta(days=1)) for training_end_date in training_ending_dates]

    training_starting_dates = [training_ending_date - timedelta(days=look_back_period * 365) for training_ending_date in training_ending_dates]

    for training_start_date, training_end_date, testing_start_date, testing_end_date, tickers in zip(training_starting_dates, training_ending_dates, testing_start_dates, testing_end_dates, yearly_tickers):
        print(f"Collecting Training Data: {training_start_date} to {training_end_date}")
        preprocessed_training_data, publicly_available_tickers = preprocess_data(training_start_date, training_end_date, tickers)
        training_opens, _ = get_opens(training_start_date, training_end_date, publicly_available_tickers)
        training_index_opens, training_index_closes = get_index(index, training_start_date, training_end_date)

        print(f"{len(publicly_available_tickers)} tickers out of {len(tickers)} publicly available for training/testing")

        print(f"Training RL Agent: {training_start_date} to {training_end_date}")
        model = RL_Investor(len(publicly_available_tickers), gpu=gpu)
        model.train(preprocessed_training_data, training_opens, training_index_opens, training_index_closes, num_episodes=episodes)

        print(f"Collecting Testing Data: {testing_start_date} to {testing_end_date}")
        preprocessed_testing_data, _ = preprocess_data(testing_start_date, testing_end_date, publicly_available_tickers)
        testing_opens, _ = get_opens(testing_start_date, testing_end_date, publicly_available_tickers)
        testing_index_opens, testing_index_closes = get_index(index, testing_start_date, testing_end_date)

        print(f"Testing RL Agent: {testing_start_date} to {testing_end_date}")
        predictions = model.predict(preprocessed_testing_data, testing_opens, testing_index_opens, testing_index_closes)

        portfolio_values = [r['portfolio_value'] for r in predictions]
        metrics = compute_metrics(portfolio_values)

        all_results.append(predictions)
        all_metrics.append(metrics)
        dataset_labels.append(f"{testing_start_date.year}-{testing_end_date.year} Test")

        print(f"\nDataset {testing_end_date.year} Results:")
        print(f"  Cumulative Return: {metrics['cumulative_return']:.4f}")
        print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']:.4f}")
        print(f"  Omega Ratio:       {metrics['omega_ratio']:.4f}")
        print(f"  Sortino Ratio:     {metrics['sortino_ratio']:.4f}\n")


    #Create save directory
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # Generate plots
    plot_portfolio_performance(
        all_results,
        dataset_labels,
        save_path=f"{save_dir}/portfolio_performance.png"
    )
    plot_metrics_table(
        all_metrics,
        dataset_labels,
        save_path=f"{save_dir}/metrics_table.png"
    )

    return all_results, all_metrics
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=str, default="sp500")
    parser.add_argument("--lookback", type=int, default=3)
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--gpu", type=bool, default=True)
    parser.add_argument("--savedir", type=str, default="")
    args = parser.parse_args()

    simulate(args.gpu, look_back_period=args.lookback, episodes=args.episodes, index=args.index, save_dir = "results-" + args.savedir)
