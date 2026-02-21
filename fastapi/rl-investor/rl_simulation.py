from datetime import date, timedelta
from rl_features import preprocess_data, get_opens, get_djia
from RLInvestor import RL_Investor
from Metrics import compute_metrics, plot_portfolio_performance, plot_metrics_table

training_starting_dates = [
    date(2016, 1, 1),
    date(2017, 1, 1),
    date(2018, 1, 1),
    date(2019, 1, 1),
    date(2020, 1, 1),
    date(2021, 1, 1),
    date(2022, 1, 1)
]

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
        "RTX", "VZ", "V", "CVS", "WMT", "DIS"
    ],
    #2020
    [
        "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
        "DD", "XOM", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
        "MCD", "MRK", "MSFT", "NKE", "PFE", "PG", "TRV", "UNH",
        "RTX", "VZ", "V", "CVS", "WMT", "DIS"
    ],
    #2021
    [
        "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
        "DOW", "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
        "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
        "HON", "VZ", "V", "CVS", "WMT", "DIS"
    ],
    #2022
    [
            "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
            "DOW", "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
            "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
            "HON", "VZ", "V", "WBA", "WMT", "DIS"
    ],
    #2023
    [
            "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
            "DOW", "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
            "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
            "HON", "VZ", "V", "CVS", "WMT", "DIS"
    ],
    #2024
    [
            "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
            "DOW", "AMGN", "GS", "HD", "IBM", "INTC", "JNJ", "JPM",
            "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
            "HON", "VZ", "V", "CVS", "WMT", "DIS"
    ],
    #2025
    [
        "MMM", "AXP", "AAPL", "BA", "CAT", "CVX", "CSCO", "KO",
        "DOW", "AMGN", "GS", "HD", "IBM", "NVDA", "JNJ", "JPM",
        "MCD", "MRK", "MSFT", "NKE", "CRM", "PG", "TRV", "UNH",
        "HON", "VZ", "V", "AMZN", "WMT", "DIS"
    ]
]

def simulate(rl_model):

    all_results = []
    all_metrics = []
    dataset_labels = []

    for training_start_date, training_end_date, testing_start_date, testing_end_date, tickers in zip(training_starting_dates, training_ending_dates, testing_start_dates, testing_end_dates, dow_tickers):
        print(f"Collecting Training Data: {training_start_date} to {training_end_date}")
        preprocessed_training_data, _ = preprocess_data(training_start_date, training_end_date, tickers)
        training_opens = get_opens(training_start_date, training_end_date, tickers)
        training_djia_opens, training_djia_closes = get_djia(training_start_date, training_end_date)

        print(f"Training RL Agent: {training_start_date} to {training_end_date}")
        model = rl_model(len(tickers))
        model.train(preprocessed_training_data, training_opens, training_djia_opens, training_djia_closes)

        print(f"Collecting Testing Data: {testing_start_date} to {testing_end_date}")
        preprocessed_testing_data, _ = preprocess_data(testing_start_date, testing_end_date, tickers)
        testing_opens = get_opens(testing_start_date, testing_end_date, tickers)
        testing_djia_opens, testing_djia_closes = get_djia(training_start_date, training_end_date)

        print(f"Testing RL Agent: {testing_start_date} to {testing_end_date}")
        predictions = model.predict(preprocessed_testing_data, testing_opens, testing_djia_opens, testing_djia_closes)

        portfolio_values = [r['portfolio_value'] for r in predictions]
        metrics = compute_metrics(portfolio_values)

        all_results.append(predictions)
        all_metrics.append(metrics)
        dataset_labels.append(f"{training_start_date.year}-{training_end_date.year} Train / {testing_start_date.year}-{testing_end_date.year} Test")

        print(f"\nDataset {testing_end_date.year} Results:")
        print(f"  Cumulative Return: {metrics['cumulative_return']:.4f}")
        print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']:.4f}")
        print(f"  Omega Ratio:       {metrics['omega_ratio']:.4f}")
        print(f"  Sortino Ratio:     {metrics['sortino_ratio']:.4f}\n")

        # Generate plots
        plot_portfolio_performance(
            all_results,
            dataset_labels,
            save_path="results/portfolio_performance.png"
        )
        plot_metrics_table(
            all_metrics,
            dataset_labels,
            save_path="results/metrics_table.png"
        )

        return all_results, all_metrics
if __name__ == "__main__":
    simulate(RL_Investor)
