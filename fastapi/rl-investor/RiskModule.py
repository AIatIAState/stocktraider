import numpy as np

class RiskModule:
    def __init__(self, alpha=.05):
        self.alpha = alpha
        self.return_history = []
        self.previous_VaR= 0.0
        self.previous_CVaR = 0.0
        self.previous_ICVaR = 0.0

    def update(self, return_value):
        self.return_history.append(return_value)

        if len(self.return_history) > 252:
            self.return_history = self.return_history[-252:]

        if len(self.return_history) < 2:
            self.previous_icvar = 0.0
            return 0.0

        X = np.array(self.return_history)

        #Find the minimum value of the cumulative distribution where the probability exceeds alpha
        vaR = -np.nanpercentile(X, self.alpha * 100)

        #Find out how much our loss exceeded the threshold at that timestep
        excess_loss = np.maximum(-X - vaR, 0)

        #Calculate the CVaR (Conditional Value at Risk) showing how bad the risk gets on average when we exceed the VaR threshold with alpha scaling
        cvaR = vaR + (1 / (self.alpha * len(X))) * np.sum(excess_loss)

        #ICVaR: the change in tail risk since the last period — positive means risk is growing
        icvaR = cvaR - self.previous_CVaR

        self.previous_VaR = vaR
        self.previous_CVaR = cvaR
        self.previous_ICVaR = icvaR
        return icvaR


    def reset(self):
        self.return_history = []
        self.previous_VaR= 0.0
        self.previous_CVaR = 0.0
        self.previous_ICVaR = 0.0
