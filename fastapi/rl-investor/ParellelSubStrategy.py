import numpy as np

class ParallelSubStrategy:
    def __init__(self, djia_close_prices, djia_open_prices, initial_cash=1e6, short_suspend_return=.05, short_expand_return=-.05, buy_reduce_return=-.05, initial_short_limit=1e4, reward_scaling=1.0):
        self.djia_close_prices = np.array(djia_close_prices)
        self.djia_open_prices = np.array(djia_open_prices)
        self.initial_cash = initial_cash
        self.reward_scaling = reward_scaling

        self.short_suspend_return = short_suspend_return
        self.short_expand_return = short_expand_return
        self.buy_reduce_return = buy_reduce_return
        self.initial_short_limit = initial_short_limit

        self.reset()

    def reset(self):
        self.current_step = 0
        self.cash = self.initial_cash
        self.shares = 0.0
        self.total_assets = self.initial_cash
        self.prev_assets = self.initial_cash
        self.cumulative_return = 0.0

        self.short_limit = self.initial_short_limit
        self.buy_limit = 1.0 #Can cahnge to .2 for adverse conditions

        return self._get_trend_index()

    def _get_trend_index(self):
        if self.total_assets == 0:
            return 0.0

        if self.current_step >= len(self.djia_close_prices):
            return 0.5 # Neutral if we run out of data

        price = self.djia_close_prices[self.current_step]
        position_value = self.shares * price

        return float(np.clip(position_value / self.total_assets, 0.0, 1.0))

    def _update_limits(self):
        if self.cumulative_return >= self.short_suspend_return:
            #Market is doing well, no need to short anything
            self.short_limit = 0.0
            self.buy_limit = 1.0

        elif self.cumulative_return <= self.short_expand_return:
            #Market is doing badly, open up shorting and restrict buying
            self.short_limit = 1e5
            self.buy_limit = .2

        else:
            #Market is chillin
            self.short_limit = self.initial_short_limit
            self.buy_limit = 1.0

    def step(self, action):
        if self.current_step >= len(self.djia_open_prices) - 1:
            return self._get_trend_index(), self.short_limit, self.buy_limit, 0.0

        price = self.djia_open_prices[self.current_step]
        self.prev_assets = self.total_assets

        #Process sells
        if action < 0:
            sell_amount = min(self.shares, -action)
            self.shares -= sell_amount
            self.cash += sell_amount * price

        #Process buys
        if action > 0:
            max_buy = (self.cash * self.buy_limit) / max(price, 1e-8)
            buy_amount = min(max_buy, action)

            self.shares += buy_amount
            self.cash -= buy_amount * price

        #Calculate total assets
        next_price = self.djia_close_prices[self.current_step + 1]
        self.total_assets = self.cash + self.shares * next_price

        #Calculate period return
        period_return = self.total_assets / max(self.prev_assets, 1e-8) - 1.0

        #Calculate reward
        reward = (self.total_assets - self.prev_assets) * self.reward_scaling

        #Update cumulative return for limits
        self.cumulative_return = self.total_assets / self.initial_cash - 1.0

        #Update the buy/short limits based on performance
        self._update_limits()

        #Advance
        self.current_step += 1

        trend_index = self._get_trend_index()
        return trend_index, self.short_limit, self.buy_limit, reward

    def get_status(self):
        return {
            "step":               self.current_step,
            "cash":               self.cash,
            "shares":             self.shares,
            "total_assets":       self.total_assets,
            "cumulative_return":  self.cumulative_return,
            "trend_index":        self._get_trend_index(),
            "short_limit":        self.short_limit,
            "buy_limit":          self.buy_limit,
        }