from math import exp

import pandas as pd
from dtaidistance import dtw
import datetime
import threading
import time
import numpy as np

from connector import get_connection

PATTERNS_CACHE_TTL_SECONDS = 86400  # 24 hours
PATTERNS_CACHE_LOCK = threading.Lock()
PATTERNS_CACHE: dict[str, dict] = {}

def directional_accuracy(actual, predicted):
    actual_direction = np.sign(actual)
    pred_direction = np.sign(predicted)
    return np.mean(actual_direction == pred_direction)

def normalize(series):
    series = np.array(series, dtype=float)
    std = np.std(series)
    if std == 0:
        return np.zeros_like(series)
    return (series - np.mean(series)) / std


def get_dtw_patterns(symbol, timeframe, trend_segment_length=7, min_similarity_score=0, lookup_date=datetime.date.today(), lookback_length=365*5):
    cache_key = f"{symbol}:{timeframe}:{trend_segment_length}:{min_similarity_score}"
    with PATTERNS_CACHE_LOCK:
        cached = PATTERNS_CACHE.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < PATTERNS_CACHE_TTL_SECONDS:
            return cached["payload"]

    where = ["symbol = ?", "timeframe = ?", "date <= ?", "date >= ?"]
    sql = f"""
        SELECT date, close
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY date ASC, time DESC
    """
    end_date = lookup_date - datetime.timedelta(lookback_length)
    params: list[object] = [symbol, timeframe, lookup_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")]
    conn = get_connection(readonly=True)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    rows = [dict(row) for row in rows]

    closes = [row["close"] for row in rows if row["close"] is not None]
    closes = np.diff(closes) / closes[:-1]
    dates = [row["date"] for row in rows if row["close"] is not None][1:]

    if len(closes) < trend_segment_length * 2:
        return {"results": []}

    current_segment = closes[-trend_segment_length:]
    past_segment = closes[:-trend_segment_length]

    current_norm = normalize(current_segment)

    similar_paths = []

    for i in range(len(past_segment) - trend_segment_length - 1):
        candidate = past_segment[i:i + trend_segment_length]
        candidate_norm = normalize(candidate)

        distance = dtw.distance(current_norm, candidate_norm, use_c=True)

        similar_paths.append({
            "starting_date": dates[i],
            "distance": float(distance),
            "similarity_score": float(100 * exp(-2 * distance))
        })

    # Sort best matches first
    similar_paths.sort(key=lambda x: x["distance"], reverse=False)

    # Remove overlapping segments
    filtered_paths = []
    for path in similar_paths:
        starting_date = datetime.datetime.strptime(str(path['starting_date']), "%Y%m%d")
        ending_date = starting_date + datetime.timedelta(days=trend_segment_length)

        has_overlap = False
        for filtered_path in filtered_paths:
            f_start = datetime.datetime.strptime(str(filtered_path['starting_date']), "%Y%m%d")
            f_end = f_start + datetime.timedelta(days=trend_segment_length)

            if (f_start <= starting_date <= f_end) or (f_start <= ending_date <= f_end):
                has_overlap = True
                break

        if not has_overlap:
            filtered_paths.append(path)

    result = {"results": filtered_paths}
    with PATTERNS_CACHE_LOCK:
        PATTERNS_CACHE[cache_key] = {"timestamp": time.time(), "payload": result}
    return result

if __name__ == "__main__":
    intervals = [5, 10, 15, 20]
    years = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    dow_jones_tickers = {
        2019: [
            "AAPL", "AXP", "BA", "CAT", "CSCO", "CVX", "DIS", "DWDP", "XOM", "GS",
            "HD", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK", "MSFT",
            "NKE", "PFE", "PG", "TRV", "UNH", "UTX", "VZ", "V", "WBA", "WMT"
        ],
        2020: [
            "AAPL", "AXP", "BA", "CAT", "CSCO", "CVX", "DIS", "DOW", "XOM", "GS",
            "HD", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK", "MSFT",
            "NKE", "PFE", "PG", "TRV", "UNH", "UTX", "VZ", "V", "WBA", "WMT"
        ],
        2021: [
            "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "VZ", "V", "WBA", "WMT"
        ],
        2022: [
            "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "VZ", "V", "WBA", "WMT"
        ],
        2023: [
            "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "VZ", "V", "WBA", "WMT"
        ],
        2024: [
            "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "VZ", "V", "WBA", "WMT"
        ],
        2025: [
            "AAPL", "AMGN", "AXP", "AMZN", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "DOW",
            "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", "MMM",
            "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "VZ", "V", "WMT"
        ]
    }
    start_dates = {
        2019: datetime.date(2019, 1, 1),
        2020: datetime.date(2020, 1, 1),
        2021: datetime.date(2021, 1, 1),
        2022: datetime.date(2022, 1, 1),
        2023: datetime.date(2023, 1, 1),
        2024: datetime.date(2024, 1, 1),
        2025: datetime.date(2025, 1, 1)
    }
    end_dates = {
        2019: datetime.date(2019, 12, 31),
        2020: datetime.date(2020, 12, 31),
        2021: datetime.date(2021, 12, 31),
        2022: datetime.date(2022, 12, 31),
        2023: datetime.date(2023, 12, 31),
        2024: datetime.date(2024, 12, 31),
        2025: datetime.date(2025, 12, 31)
    }
    output_data = None


    for year in years:
        current_date = start_dates[year]
        end_date = end_dates[year]
        intervalDateSaves = {}

        while current_date <= end_date:
            #Check if its not a weekend or a holiday
            holidays = {(1, 1),(12, 25),(7, 4),(11, 28),(11, 29),(1, 17),(2, 20),(3, 17),(5, 26), (9, 2),(11, 27)}

            is_tradable = current_date.weekday() < 5 and (current_date.month, current_date.day) not in holidays

            if not is_tradable:
                current_date += datetime.timedelta(1)
                continue

            print(f"RUNNING DATE {current_date.strftime("%m-%d-%Y")}")
            for ticker in dow_jones_tickers[year]:
                for interval in intervals:
                    if interval not in intervalDateSaves:
                        intervalDateSaves[interval] = []

                    results = get_dtw_patterns(ticker + ".US", "daily", trend_segment_length=interval, min_similarity_score=0, lookup_date=current_date)["results"]
                    if len(results) == 0:
                        continue

                    most_similar_dates = [pattern['starting_date'] for pattern in results[:20]]
                    distance_scores = [pattern['distance'] for pattern in results[:20]]

                    where = ["symbol = ?", "timeframe = ?", "date > ?"]
                    sql = f"""
                        SELECT date, close
                        FROM bars
                        WHERE {' AND '.join(where)}
                        ORDER BY date ASC
                        LIMIT ?
                    """

                    params: list[object] = [ticker + ".US", "daily", current_date.strftime("%Y%m%d"), interval]
                    conn = get_connection(readonly=True)
                    try:
                        target_rows = conn.execute(sql, params).fetchall()
                    finally:
                        conn.close()

                    target_rows = [dict(row)['close'] for row in target_rows]
                    target_rows = np.diff(target_rows) / target_rows[:-1]

                    where = ["symbol = ?", "timeframe = ?", "date <= ?"]
                    sql = f"""
                        SELECT date, close
                        FROM bars
                        WHERE {' AND '.join(where)}
                        ORDER BY date DESC
                        LIMIT ?
                    """

                    params: list[object] = [ticker + ".US", "daily", current_date.strftime("%Y%m%d"), interval]
                    conn = get_connection(readonly=True)
                    try:
                        past_segment_rows = conn.execute(sql, params).fetchall()
                    finally:
                        conn.close()

                    past_segment = [dict(row)['close'] for row in past_segment_rows]
                    past_segment.reverse()
                    past_segment = np.diff(past_segment) / past_segment[:-1]

                    similar_sequences = []
                    for most_similar_date in most_similar_dates:
                        where = ["symbol = ?", "timeframe = ?", "date >= ?"]
                        sql = f"""
                            SELECT date, close
                            FROM bars
                            WHERE {' AND '.join(where)}
                            ORDER BY date ASC
                            LIMIT ?
                        """

                        params: list[object] = [ticker + ".US", "daily", most_similar_date, interval]
                        conn = get_connection(readonly=True)
                        try:
                            similar_rows = conn.execute(sql, params).fetchall()
                        finally:
                            conn.close()

                        similar_rows = [dict(row)['close'] for row in similar_rows]
                        similar_rows = np.diff(similar_rows) / similar_rows[:-1]
                        similar_sequences.append(similar_rows)

                    temperature = np.median(distance_scores)
                    weights = np.exp(-np.array(distance_scores) / temperature)
                    weights /= np.sum(weights)

                    actual, pred = np.array(target_rows), np.average(similar_sequences, axis=0, weights=weights)

                    #MSE
                    mse =  np.square(np.subtract(actual, pred)).mean()


                    # Baseline MSE (comparing actual to mean)
                    baseline_mse = np.square(np.subtract(actual, np.mean(past_segment))).mean()

                    # Directional Accuracy
                    actual_direction = np.sign(actual)
                    pred_direction = np.sign(pred)
                    directional_acc = np.mean(actual_direction == pred_direction)

                    # 1-d Directional Accuracy
                    one_day_actual_direction = np.sign(actual[0])
                    one_day_pred_direction = np.sign(pred[0])
                    one_day_directional_acc = 1 if one_day_actual_direction == one_day_pred_direction else 0




                    new_row = pd.DataFrame([{"mse": mse, "1d_directional_accuracy": one_day_directional_acc, "directional_accuracy": directional_acc, "mse_baseline": baseline_mse, "min_distance": distance_scores[0], "ticker": ticker, "interval": interval, "date": current_date.strftime("%Y%m%d")}])
                    if output_data is None:
                        output_data = pd.DataFrame(new_row)
                    else:
                        output_data = pd.concat([output_data, new_row], ignore_index=True)




            current_date += datetime.timedelta(1)

    output_data.to_csv(f"pattern_recognition_backtesting_no_norm.csv", index=False)

    output_data = pd.read_csv(f"pattern_recognition_backtesting_no_norm.csv")

    for year in years:
        print(f"TESTING YEAR {year}")
        for interval in intervals:
            print("\n\n")
            interval_data = output_data[
                (output_data["interval"] == interval) &
                (output_data["date"] >= int(start_dates[year].strftime("%Y%m%d"))) &
                (output_data["date"] <= int(end_dates[year].strftime("%Y%m%d")))
                ]
            interval_mse = interval_data['mse']
            total_mse = sum(interval_mse)
            mean_mse = total_mse / len(interval_mse)
            print(f"Average MSE for {interval} day interval: {mean_mse}")

            interval_mse_baseline = interval_data['mse_baseline']
            total_mse_baseline = sum(interval_mse_baseline)
            mean_mse_baseline = total_mse_baseline / len(interval_mse_baseline)
            print(f"Average MSE Baseline for {interval} day interval: {mean_mse_baseline}")

            interval_directional_acc = interval_data['directional_accuracy']
            total_directional_acc = sum(interval_directional_acc)
            mean_directional_acc = total_directional_acc / len(interval_directional_acc)
            print(f"Average Directional Accuracy for {interval} day interval: {mean_directional_acc}")

            interval_1d_directional_acc = interval_data['1d_directional_accuracy']
            total_1d_directional_acc = sum(interval_1d_directional_acc)
            mean_1d_directional_acc = total_1d_directional_acc / len(interval_1d_directional_acc)
            print(f"Average 1-Day Directional Accuracy for {interval} day interval: {mean_1d_directional_acc}")

            interval_distance = interval_data['min_distance']
            total_distance = sum(interval_distance)
            mean_distance = total_distance / len(interval_distance)
            print(f"Average Min Distance for {interval} day interval: {mean_distance}")

    print("TESTING TOTAL BACKTEST SPAN")
    for interval in intervals:
        print("\n\n")
        interval_data = output_data[output_data["interval"] == interval]

        interval_mse = interval_data['mse']
        total_mse = sum(interval_mse)
        mean_mse = total_mse / len(interval_mse)
        print(f"Average MSE for {interval} day interval: {mean_mse}")

        interval_mse_baseline = interval_data['mse_baseline']
        total_mse_baseline = sum(interval_mse_baseline)
        mean_mse_baseline = total_mse_baseline / len(interval_mse_baseline)
        print(f"Average MSE Baseline for {interval} day interval: {mean_mse_baseline}")

        interval_directional_acc = interval_data['directional_accuracy']
        total_directional_acc = sum(interval_directional_acc)
        mean_directional_acc = total_directional_acc / len(interval_directional_acc)
        print(f"Average Directional Accuracy for {interval} day interval: {mean_directional_acc}")

        interval_1d_directional_acc = interval_data['1d_directional_accuracy']
        total_1d_directional_acc = sum(interval_1d_directional_acc)
        mean_1d_directional_acc = total_1d_directional_acc / len(interval_1d_directional_acc)
        print(f"Average 1-Day Directional Accuracy for {interval} day interval: {mean_1d_directional_acc}")

        interval_distance = interval_data['min_distance']
        total_distance = sum(interval_distance)
        mean_distance = total_distance / len(interval_distance)
        print(f"Average Min Distance for {interval} day interval: {mean_distance}")