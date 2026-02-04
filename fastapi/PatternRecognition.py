from dtaidistance import dtw
import datetime
import numpy as np
from Connector import get_connection


def normalize(series):
    series = np.array(series, dtype=float)
    std = np.std(series)
    if std == 0:
        return np.zeros_like(series)
    return (series - np.mean(series)) / std


def get_dtw_patterns(symbol, timeframe, trend_segment_length=7, min_similarity_score=95):
    where = ["symbol = ?", "timeframe = ?"]
    sql = f"""
        SELECT symbol, per, date, time, open, high, low, close, volume, openint, timeframe
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY date ASC, time DESC
    """

    params: list[object] = [symbol, timeframe]
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    rows = [dict(row) for row in rows]

    opens = [row["open"] for row in rows if row["open"] is not None]
    dates = [row["date"] for row in rows if row["open"] is not None]

    if len(opens) < trend_segment_length * 2:
        return {"results": []}

    current_segment = opens[-trend_segment_length:]
    past_segment = opens[:-trend_segment_length]

    current_norm = normalize(current_segment)

    similar_paths = []

    # Controls how strict similarity is (larger = harsher penalty)
    alpha = 1 / trend_segment_length

    for i in range(len(past_segment) - trend_segment_length - 1):
        candidate = past_segment[i:i + trend_segment_length]
        candidate_norm = normalize(candidate)

        distance = dtw.distance(current_norm, candidate_norm, use_c=False)

        # Convert distance → similarity (0–100 scale)
        similarity_score = 100 * np.exp(-alpha * distance)

        if similarity_score >= min_similarity_score:
            similar_paths.append({
                "starting_date": dates[i],
                "similarity_score": float(similarity_score)
            })

    # Sort best matches first
    similar_paths.sort(key=lambda x: x["similarity_score"], reverse=True)

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

    return {"results": filtered_paths}
