import numpy as np
from RiskModule import RiskModule


class PortfolioEnvironment:
    def __init__(self, indicators, opens, tickers, initial_cash=1e6, transaction_cost=0, lambda_risk=.5, alpha=.05, short_sell_limit=1e4):
        self.indicators = indicators
        self.opens = opens
        self.tickers = sorted(tickers)
        self.num_stocks = len(tickers)
        self.initial_cash = initial_cash
        self.transaction_cost = transaction_cost
        self.lambda_risk = lambda_risk
        self.short_sell_limit = short_sell_limit

        self.risk_module = RiskModule(alpha=alpha)

        self.trading_days = sorted(list(indicators[self.tickers[0]].index))
        self.num_days = len(self.trading_days)
        self.reset()

    def reset(self):
        self.current_step = 0
        self.cash = self.initial_cash
        self.shares = np.zeros(self.num_stocks)
        self.portfolio_value = self.initial_cash

        self.risk_module.reset()

        return self._get_state()

    def _get_closing_prices(self, day):
        #Get the closing price vector for all tickers on a given day
        prices = []
        for ticker in self.tickers:
            df = self.indicators[ticker]
            if day in df.index:
                prices.append(df.loc[day, 'close'])
            else:
                prices.append(0.0)
        return np.array(prices)

    def _get_opening_prices(self, day):
        #Get the opening price vector for all tickers on a given day
        prices = []
        for ticker in self.tickers:
            day_opens = self.opens[(self.opens['ticker'] == ticker) & (self.opens['date'] == day)]
            if not day_opens.empty:
                prices.append(day_opens['open'].values[0])
            else:
                prices.append(0.0)
        return np.array(prices)

    def _get_state(self):
        if self.current_step >= self.num_days:
            return None

        # Build the state vector
        day = self.trading_days[self.current_step]
        feature_columns = ['close', 'boll_upper', 'boll_lower', 'cci', 'rsi', 'tr', 'dmi', 'macd', 'mfi']
        state = [self.cash]

        for i, ticker in enumerate(self.tickers):
            df = self.indicators[ticker]
            if day in df.index:
                features = df.loc[day, feature_columns].fillna(0).values
            else:
                features = np.zeros(len(feature_columns))

            #State vector for each ticker includes the number of shares held and the financial indicators for that day, concatenated together
            f_tk = np.concatenate([[self.shares[i]], features])
            state.extend(f_tk)
        return np.array(state, dtype=np.float32)

    def _execute_trades(self, action, open_prices, trend_index, short_limit, buy_limit):
        sells = np.zeros(self.num_stocks)
        buys = np.zeros(self.num_stocks)

        # Convert portfolio weights to target share counts
        target_shares_counts = np.array([
            (action[i] * self.portfolio_value) / max(open_prices[i], 1e-8)
            for i in range(self.num_stocks)
        ])

        #Process sells first
        for i in range(self.num_stocks):
            current_shares = float(self.shares[i])
            target_shares = float(target_shares_counts[i])

            if target_shares < current_shares:
                # Find how many to sell, ensuring we don't go below the short sell limit
                max_short = (short_limit * (1 - trend_index) / max(open_prices[i], 1e-8))
                sell_amount = min(max(current_shares, 0) + max_short, current_shares - target_shares)
                sells[i] = sell_amount

                #Update shares and cash after selling
                self.shares[i] -= sells[i]
                self.cash += open_prices [i] * sells[i] * (1 - self.transaction_cost)

        #Process buys
        for i in range(self.num_stocks):
            target_shares = float(target_shares_counts[i])

            if target_shares > self.shares[i]:

                #Create a buying limit
                max_buy = (self.cash * buy_limit * max(trend_index, .1) / max(open_prices[i], 1e-8))
                buy_amount = min(max_buy, target_shares - self.shares[i])
                buys[i] = buy_amount

                #Update shares and cash after buying
                self.shares[i] += buys[i]
                self.cash -= open_prices[i] * buys[i] * (1 + self.transaction_cost)
        return sells, buys

    def _compute_reward(self, delta_P, P_prev):
        if P_prev == 0:
            return 0.0

        # Reward function calculating the percentage change in total assets considering risk
        X_t = delta_P / P_prev
        icvaR = self.risk_module.update(X_t)
        return delta_P - self.lambda_risk * icvaR

    def step(self, action, trend_index=1.0, short_limit=1e4, buy_limit=1.0):

        if self.current_step >= self.num_days - 1:
            return None, 0.0, True

        next_day = self.trading_days[self.current_step + 1]
        opening_prices = self._get_opening_prices(next_day)

        #Store the previous portfolio value for return calculations
        P_prev = self.portfolio_value

        #Execute the trades based on the action and update cash and shares
        sells, buys = self._execute_trades(action, opening_prices, trend_index, short_limit, buy_limit)

        #Advance to the next day
        self.current_step += 1
        closing_prices = self._get_closing_prices(next_day)

        stock_value = np.dot(self.shares, closing_prices)
        self.portfolio_value = self.cash + stock_value
        delta_P = self.portfolio_value - P_prev

        reward = self._compute_reward(delta_P, P_prev)

        done = self.current_step >= self.num_days - 1

        return self._get_state(), reward, done

    def get_portfolio_summary(self):
        return {
            "step": self.current_step,
            "cash": self.cash,
            "portfolio_value": self.portfolio_value,
            "shares": dict(zip(self.tickers, self.shares))
        }
