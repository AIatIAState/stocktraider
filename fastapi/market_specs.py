import datetime
import math
from connector import get_connection

class Bar:
    def __init__(self, open, close, volume, date, time):
        self.open = open
        self.close = close
        self.volume = volume
        if time == 0:
            time = "000000"
        self.date = datetime.datetime.strptime(str(date) + " " + str(time), "%Y%m%d %H%M%S")

def get_bars(symbol, days_before, end_date=datetime.date.today()):
    conn = get_connection(readonly=True)
    start_date = end_date - datetime.timedelta(days=days_before)
    where = ["symbol = ?", "timeframe = ?", "date >= ?", "date <= ?"]
    params: list[object] = [symbol, "daily", start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")]

    sql = f"""
        SELECT date, close, open, time, volume
        FROM bars
        WHERE {' AND '.join(where)}
        ORDER BY date ASC
    """
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    rows = [dict(row) for row in rows]
    bars = []
    for row in rows:
        bars.append(Bar(row['open'], row['close'], row['volume'], row['date'], row['time']))
    return bars

def get_label(symbol, starting_date, todays_price, max_trading_days=15):
    """
    Improved labeling strategy with a time horizon cap and 3-class output.

    Walks forward up to max_trading_days (~3 calendar weeks) one day at a time.
    The first threshold hit within the window determines the label.
    If neither threshold is hit, the sample is discarded (returns -1).

    Labels
    ──────
    2  — Strong buy:  close rose ≥ 3% within the window          (high-conviction win)
    1  — Weak buy:    close rose ≥ 1.5% but < 3% within window   (modest win)
    0  — Loss:        close fell ≥ 1.5% within the window         (loss)
   -1  — Discard:     neither threshold hit — ambiguous, skip

    Why this is better than the original binary label
    ──────────────────────────────────────────────────
    • Time cap prevents a 5-month slow crawl from being treated the same
      as a 2-day breakout — speed of the move is encoded implicitly.
    • Symmetric thresholds (±1.5%) eliminate the drift bias that caused
      the original labels to skew heavily toward the positive class.
    • 3 classes let the model distinguish strong opportunities from weak
      ones, rather than collapsing everything into buy / don't-buy.
    • Discarding ambiguous samples keeps the training signal clean —
      flat-moving stocks are noise, not signal.

    Compatibility note
    ──────────────────
    The simulation exit strategy (general_exit_strategy in simulation.py)
    still uses its own +2% / -1% thresholds for live trading decisions.
    This label is only used during training to teach the model which
    market conditions tend to precede good outcomes.
    """

    # Symmetric thresholds — eliminates drift bias toward label=1
    strong_win_price = todays_price * 1.03    # +3%
    weak_win_price   = todays_price * 1.015   # +1.5%
    loss_price       = todays_price * 0.985   # -1.5%

    # Fetch the next ~max_trading_days * 1.5 calendar days to account
    # for weekends and public holidays without over-fetching
    lookahead_days = max_trading_days * 2
    end_date = starting_date + datetime.timedelta(days=lookahead_days)

    conn = get_connection(readonly=True)
    sql = """
        SELECT date, close
        FROM bars
        WHERE symbol = ? AND timeframe = ? AND date > ? AND date <= ?
        ORDER BY date ASC
    """
    params: list[object] = [
        symbol,
        "daily",
        starting_date.strftime("%Y%m%d"),
        end_date.strftime("%Y%m%d"),
    ]
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    rows = [dict(r) for r in rows]
    if not rows:
        return -1

    # Walk forward day by day and stop at the first threshold hit
    trading_days_seen = 0
    for row in rows:
        if trading_days_seen >= max_trading_days:
            break

        close = row['close']

        if close >= strong_win_price:
            return 2   # strong buy — hit +3% quickly
        if close >= weak_win_price:
            return 1   # weak buy  — hit +1.5% but not +3%
        if close <= loss_price:
            return 0   # loss      — fell 1.5% before rising

        trading_days_seen += 1

    # Neither threshold hit within the window — discard
    return -1

def get_market_specs(symbol, days, starting_date):
    bars = get_bars(symbol, days, starting_date)

    if len(bars) == 0 or (bars[-1].date.date() - starting_date).days != 0:
        return -1

    todays_price = bars[-1].close
    label = get_label(symbol, starting_date, todays_price, max_trading_days=15)
    if label == -1:
        return -1

    return {
        "rsi_simple_moving_average": get_rsi_simple_moving_average(bars), #0-100
        "rsi_wilders_smoothing": get_rsi_wilders_smoothing(bars,int(days/2)), #0-100
        "rsi_exponential_smoothing": get_rsi_exponential_moving_average(bars,int(days/2)), #0-100
        "annualized_return": get_annualized_return(bars), #-100-100
        "log_returns": get_log_returns(bars), #-100 - infinity
        "volatility": get_volatility(bars), #0-100
        "downside_volatility": get_downside_volatility(bars), #0-100
        #"maximum_drawdown": get_maximum_drawdown(bars)['max_drawdown'], #0-100
        "avg_drawdown": get_avg_drawdown(bars), #0-100
        "sharpe_ratio": get_sharpe_ratio(bars), #-inf - inf
        #"calmar_ratio": get_calmar_ratio(bars), #-inf - inf
        "simple_momentum": get_simple_momentum(bars, int(days/2)), #-100 - inf
        "slope_of_log_price": get_slope_of_log_price(bars), #-inf - inf
        "label": label
    }
def get_rsi_simple_moving_average(bars):
    period = len(bars)
    if period == 0:
        return 0

    # Sort bars by date to ensure chronological order
    sorted_bars = sorted(bars, key=lambda x: x.date)

    # Calculate price changes
    changes = []
    for i in range(1, len(sorted_bars)):
        change = sorted_bars[i].close - sorted_bars[i - 1].close
        changes.append(change)

    # Separate gains and losses
    gains = [change if change > 0 else 0 for change in changes]
    losses = [-change if change < 0 else 0 for change in changes]

    # Calculate average gain and loss
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Calculate RS and RSI
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

    return rsi

def get_rsi_wilders_smoothing(bars, period):

    # Sort bars by date to ensure chronological order
    sorted_bars = sorted(bars, key=lambda x: x.date)

    # Calculate price changes
    changes = []
    for i in range(1, len(sorted_bars)):
        change = sorted_bars[i].close - sorted_bars[i - 1].close
        changes.append(change)

    if len(changes) < period:
        return 0

    # Separate initial gains and losses for the first period
    initial_gains = [change if change > 0 else 0 for change in changes[:period]]
    initial_losses = [-change if change < 0 else 0 for change in changes[:period]]

    # Calculate initial average (simple average for first period)
    avg_gain = sum(initial_gains) / period
    avg_loss = sum(initial_losses) / period

    # Apply exponential smoothing for remaining periods
    for i in range(period, len(changes)):
        change = changes[i]
        gain = change if change > 0 else 0
        loss = -change if change < 0 else 0

        # Wilder's smoothing
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    # Calculate final RSI
    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

def get_rsi_exponential_moving_average(bars,days):
    sorted_bars = sorted(bars, key=lambda x: x.date)
    period = days

    changes = []
    for i in range(1, len(sorted_bars)):
        change = sorted_bars[i].close - sorted_bars[i - 1].close
        changes.append(change)

    if len(changes) < period:
        return 0

    # Alpha for standard EMA
    alpha = 2 / (period + 1)

    # Initial values
    initial_gains = [change if change > 0 else 0 for change in changes[:period]]
    initial_losses = [-change if change < 0 else 0 for change in changes[:period]]

    avg_gain = sum(initial_gains) / period
    avg_loss = sum(initial_losses) / period

    # Apply standard EMA smoothing
    for i in range(period, len(changes)):
        change = changes[i]
        gain = change if change > 0 else 0
        loss = -change if change < 0 else 0

        # Standard EMA formula
        avg_gain = alpha * gain + (1 - alpha) * avg_gain
        avg_loss = alpha * loss + (1 - alpha) * avg_loss

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

def get_annualized_return(bars):
    if len(bars) < 2:
        return 0

    # Sort bars by date to ensure chronological order
    sorted_bars = sorted(bars, key=lambda x: x.date)

    # Get first and last closing prices
    initial_price = sorted_bars[0].close
    final_price = sorted_bars[-1].close

    if initial_price <= 0:
        return 0

    # Calculate total return
    total_return = (final_price - initial_price) / initial_price

    # Calculate time period in years
    start_date = sorted_bars[0].date
    end_date = sorted_bars[-1].date
    days = (end_date - start_date).days

    if days <= 0:
        return 0

    years = days / 365.25  # Account for leap years

    # Calculate annualized return using compound growth formula
    # Annualized Return = (1 + Total Return)^(1/years) - 1
    annualized_return = ((1 + total_return) ** (1 / years) - 1) * 100

    return annualized_return

def get_log_returns(bars):
    if len(bars) < 2:
        return 0

    sorted_bars = sorted(bars, key=lambda x: x.date)

    initial_price = sorted_bars[0].close
    final_price = sorted_bars[-1].close

    if initial_price <= 0 or final_price <= 0:
        return 0

    # Cumulative log return
    cumulative_log_return = math.log(final_price / initial_price)

    return cumulative_log_return


def get_volatility(bars):
    if len(bars) < 2:
        return 0

    sorted_bars = sorted(bars, key=lambda x: x.date)

    log_returns = []
    for i in range(1, len(sorted_bars)):
        previous_close = sorted_bars[i - 1].close
        current_close = sorted_bars[i].close

        if previous_close <= 0 or current_close <= 0:
            continue

        log_return = math.log(current_close / previous_close)
        log_returns.append(log_return)

    if len(log_returns) < 2:
        return 0

    mean_return = sum(log_returns) / len(log_returns)
    variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
    std_dev = math.sqrt(variance)

    # Return as percentage per period
    return std_dev * 100

def get_downside_volatility(bars):
    if len(bars) < 2:
        return 0

    # Sort bars by date to ensure chronological order
    sorted_bars = sorted(bars, key=lambda x: x.date)

    # Calculate log returns
    log_returns = []
    for i in range(1, len(sorted_bars)):
        previous_close = sorted_bars[i - 1].close
        current_close = sorted_bars[i].close

        if previous_close <= 0 or current_close <= 0:
            continue

        log_return = math.log(current_close / previous_close)
        log_returns.append(log_return)

    if len(log_returns) < 2:
        return 0

    # Filter only negative returns (downside)
    downside_returns = [r for r in log_returns if r < 0]

    if len(downside_returns) < 2:
        return 0

    # Calculate downside deviation
    # Using 0 as the target (measuring deviation from break-even)
    mean_downside = sum(downside_returns) / len(downside_returns)
    variance = sum((r - mean_downside) ** 2 for r in downside_returns) / (len(downside_returns) - 1)
    downside_std_dev = math.sqrt(variance)

    # Return as percentage (per period)
    return downside_std_dev * 100

def get_maximum_drawdown(bars):
    if len(bars) < 2:
        return {"max_drawdown": 0, "peak_date": None, "trough_date": None}

    sorted_bars = sorted(bars, key=lambda x: x.date)

    max_drawdown = 0
    peak_price = sorted_bars[0].close
    peak_date = sorted_bars[0].date
    max_dd_peak_date = None
    max_dd_trough_date = None

    for bar in sorted_bars:
        current_price = bar.close

        # Update peak if we've reached a new high
        if current_price > peak_price:
            peak_price = current_price
            peak_date = bar.date

        # Calculate drawdown from peak
        if peak_price > 0:
            drawdown = ((peak_price - current_price) / peak_price) * 100

            # Update maximum drawdown
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_dd_peak_date = peak_date
                max_dd_trough_date = bar.date

    return {
        "max_drawdown": max_drawdown,
        "peak_date": max_dd_peak_date,
        "trough_date": max_dd_trough_date
    }

def get_avg_drawdown(bars):
    if len(bars) < 2:
        return 0

    sorted_bars = sorted(bars, key=lambda x: x.date)

    peak_price = sorted_bars[0].close
    drawdowns = []

    for bar in sorted_bars:
        current_price = bar.close

        if current_price > peak_price:
            peak_price = current_price

        if peak_price > 0:
            drawdown = ((peak_price - current_price) / peak_price) * 100
            # Only include non-zero drawdowns
            if drawdown > 0:
                drawdowns.append(drawdown)

    if len(drawdowns) == 0:
        return 0

    avg_drawdown = sum(drawdowns) / len(drawdowns)

    return avg_drawdown

def get_sharpe_ratio(bars, risk_free_rate=0.0):
    if len(bars) < 2:
        return 0

        # Sort bars by date to ensure chronological order
    sorted_bars = sorted(bars, key=lambda x: x.date)

    # Calculate log returns
    log_returns = []
    for i in range(1, len(sorted_bars)):
        previous_close = sorted_bars[i - 1].close
        current_close = sorted_bars[i].close

        if previous_close <= 0 or current_close <= 0:
            continue

        log_return = math.log(current_close / previous_close)
        log_returns.append(log_return)

    if len(log_returns) < 2:
        return 0

    # Calculate mean return
    mean_return = sum(log_returns) / len(log_returns)

    # Calculate standard deviation
    variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
    std_dev = math.sqrt(variance)

    if std_dev == 0:
        return 0

    # Calculate Sharpe ratio (non-annualized)
    sharpe_ratio = (mean_return - risk_free_rate) / std_dev

    return sharpe_ratio

def get_calmar_ratio(bars):
    if len(bars) < 2:
        return 0

        # Calculate annualized return using existing function
    annualized_return = get_annualized_return(bars)

    # Calculate maximum drawdown using existing function
    max_drawdown = get_maximum_drawdown(bars)

    # Calculate Calmar ratio
    if max_drawdown == 0:
        return 0  # Avoid division by zero

    calmar_ratio = annualized_return / max_drawdown['max_drawdown']

    return calmar_ratio
def get_simple_momentum(bars, lookback_periods=10):

    if len(bars) < lookback_periods + 1:
        return 0

    # Sort bars by date to ensure chronological order
    sorted_bars = sorted(bars, key=lambda x: x.date)

    # Get price from lookback_periods ago and current price
    past_price = sorted_bars[-lookback_periods - 1].close
    current_price = sorted_bars[-1].close

    if past_price <= 0:
        return 0

    # Calculate simple momentum as percentage change
    momentum = ((current_price - past_price) / past_price) * 100

    return momentum

def get_slope_of_log_price(bars):
    if len(bars) < 2:
        return 0

    # Sort bars by date to ensure chronological order
    sorted_bars = sorted(bars, key=lambda x: x.date)

    # Calculate log prices
    log_prices = []
    for bar in sorted_bars:
        if bar.close <= 0:
            continue
        log_prices.append(math.log(bar.close))

    if len(log_prices) < 2:
        return 0

    n = len(log_prices)

    # Create x values (time indices: 0, 1, 2, ..., n-1)
    x_values = list(range(n))

    # Calculate means
    mean_x = sum(x_values) / n
    mean_y = sum(log_prices) / n

    # Calculate slope using least squares regression
    # slope = sum((x - mean_x) * (y - mean_y)) / sum((x - mean_x)^2)
    numerator = sum((x_values[i] - mean_x) * (log_prices[i] - mean_y) for i in range(n))
    denominator = sum((x_values[i] - mean_x) ** 2 for i in range(n))

    if denominator == 0:
        return 0

    slope = numerator / denominator

    return slope




if __name__ == "__main__":
    print(get_market_specs("AAPL.US", 24, datetime.date(2023, 2, 20)))