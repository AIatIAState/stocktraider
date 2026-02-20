import os
from datetime import datetime, timedelta, date
from collections import OrderedDict
import joblib
import torch
from sklearn.preprocessing import StandardScaler
import torch.nn as nn
from torch import optim
from market_specs import get_market_specs
import pandas as pd


class NaiveNN:
    """
    Class for collecting training data through the feature extractor, training a simple neural network, and predicting samples
    """
    def __init__(self, load_dir=None):
        """
        Initializer for Naive NN to initialize the model architecture and ticker list for training
        :param tickers: list of strings containing tickers selected for training data
        :param load_dir: optional filepath for saved model pt and pkl files
        """
        self.scaler = None
        self.model = nn.Sequential(OrderedDict([
            ("dense1", nn.Linear(11, 64)),
            ("relu1", nn.ReLU()),
            ("dropout1", nn.Dropout(.3)),
            ("dense2", nn.Linear(64, 32)),
            ("relu2", nn.ReLU()),
            ("dropout2", nn.Dropout(.2)),
            ("dense3", nn.Linear(32, 16)),
            ("relu3", nn.ReLU()),
            ("dropout3", nn.Dropout(.1)),
            ("dense4", nn.Linear(16, 1))
        ]))
        if load_dir is not None:
            self.model.load_state_dict(torch.load(load_dir + '/model.pth'))
            self.scaler = joblib.load(load_dir + '/st_scaler.pkl')


    def train(self, tickers, start_date, dataset_length, epochs, print_progress=False):
        """
        Collects training data with the MarketSpecs function and labels according to the basic exit strategy
        Trains the neural network on the resulting training data
        :param start_date: The minimum date of the dataset's entries
        :param dataset_length: The number of days to sample for each stock ticker
        :param epochs: The number of epochs for training the neural network
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(f'model_save_{timestamp}')
        ticker_features = []
        for ticker in tickers:
            print(f"Beginning data collection for {ticker}")
            for i in range(dataset_length):
                current_date = start_date + timedelta(days=i)
                market_specs = get_market_specs(ticker, 28, current_date)

                if market_specs == -1:
                    continue

                ticker_features.append(market_specs)

        print(f"Collected {len(ticker_features)} samples.")

        df = pd.DataFrame(ticker_features)

        shuffled_df = df.sample(frac=1, random_state=42).reset_index(drop=True)

        labels = shuffled_df['label'].to_numpy().tolist()
        shuffled_df = shuffled_df.drop(columns=['label'])

        self.scaler = StandardScaler()
        scaled_df = self.scaler.fit_transform(shuffled_df)
        tensor = torch.FloatTensor(scaled_df)

        y = torch.FloatTensor(labels).reshape(-1, 1)

        best_loss = float('inf')

        print("Beginning Training")


        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        for epoch in range(epochs):
            self.model.train()

            # Forward pass
            outputs = self.model(tensor)
            loss = criterion(outputs, y)

            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            # Save best model
            if loss.item() < best_loss:
                best_loss = loss.item()
                torch.save(self.model.state_dict(), f"model_save_{timestamp}/model.pth")
                if print_progress:
                    print(f'Saved new best model at epoch {epoch + 1} with loss {best_loss:.4f}')

            if (epoch + 1) % 10 == 0 and print_progress:
                print(f'Epoch [{epoch + 1}/{epochs}], Loss: {loss.item():.4f}')

        joblib.dump(self.scaler, f'model_save_{timestamp}/st_scaler.pkl')

        print(f'Training complete. Best loss: {best_loss:.4f}')

    def predict(self, ticker, current_date):
        """
        Predicts the stock market conditions for a successful/failed trade
        :param ticker: The stock you would like to evaluate
        :param current_date: The date you would like to evaluate
        :return: True or False for Buy/Don't Buy
        """
        market_specs = get_market_specs(ticker, 28, current_date)
        if market_specs == -1:
            return False
        df = pd.DataFrame([market_specs])
        df = df.drop(columns=['label'])
        scaled_df = self.scaler.transform(df)
        tensor = torch.FloatTensor(scaled_df)

        self.model.eval()
        with torch.no_grad():
            prediction = self.model(tensor)
        prob = prediction.item()
        return prob > .3

    def predict_proba(self, ticker, current_date):
        """
        Predicts the stock market conditions for a successful trade
        :param ticker: The stock you would like to evaluate
        :param current_date: The date you would like to evaluate
        :return: Float value 0-1 for probability of a successful trade
        """
        market_specs = get_market_specs(ticker, 28, current_date)
        if market_specs == -1:
            return False
        df = pd.DataFrame([market_specs])
        df = df.drop(columns=['label'])
        scaled_df = self.scaler.transform(df)
        tensor = torch.FloatTensor(scaled_df)

        self.model.eval()
        with torch.no_grad():
            prediction = self.model(tensor)
        prob = prediction.item()
        return prob

    def market_conditions(self, ticker, current_date):
        """
        Returns the market conditions with a prediction
        :param ticker: The stock you would like to evaluate
        :param current_date: The date you would like to evaluate
        :return: MarketConditions, Buy
        """
        market_specs = get_market_specs(ticker, 28, current_date)
        if market_specs == -1:
            return False
        df = pd.DataFrame([market_specs])
        df = df.drop(columns=['label'])
        scaled_df = self.scaler.transform(df)
        tensor = torch.FloatTensor(scaled_df)

        self.model.eval()
        with torch.no_grad():
            prediction = self.model(tensor)
        prob = prediction.item()
        return market_specs, prob > .3


if __name__ == "__main__":
    tickers = [
        'AAPL.US',    # Apple
        'MSFT.US',    # Microsoft
        'NVDA.US',    # NVDIA
        'GOOGL.US',   # Google
        'AMZN.US',    # Amazon
        'META.US',    # Meta
        'BRK.B.US',   # Berkshire Hathaway
        'LLY.US',     # Eli Lilly
        'JPM.US',     # JPMorgan Chase
        'V.US',       # Visa
        'WMT.US',     # Walmart
        'UNH.US',     # UnitedHealth Group
        'MA.US',      # Mastercard
        'XOM.US',     # ExxonMobil
        'PG.US',      # Procter & Gamble
        'HD.US',      # Home Depot
        'CVX.US',     # Chevron
        'ABBV.US',    # AbbVie
        'PEP.US',     # PepsiCo
        'BAC.US',     # Bank of America
        'TMO.US',     # Thermo Fisher
        'MCD.US',     # McDonald's
        'DIS.US'      # Disney
    ]
    naive_nn = NaiveNN()
    naive_nn.train(tickers, date(2011, 1, 1), 3653, 100) #10 years of data, use preceeding 1 year for evaluation
    print(naive_nn.predict_proba('MSFT.US', date(2021, 1, 1)))