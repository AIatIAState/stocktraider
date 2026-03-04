import argparse
import os
import time
from datetime import date

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import RobustScaler
from torch import nn, optim
from torch.utils.data import TensorDataset, DataLoader
from tqdm import tqdm
from Features import build_full_features
from symbol_collector import get_sp500_at_date


def init_weights(m):
    """Initialize weights with proper scaling for Transformers"""
    if isinstance(m, nn.Linear):
        nn.init.xavier_uniform_(m.weight, gain=1.0)
        if m.bias is not None:
            nn.init.zeros_(m.bias)
    elif isinstance(m, nn.LayerNorm):
        nn.init.ones_(m.weight)
        nn.init.zeros_(m.bias)

class TransformerModel(nn.Module):
    def __init__(self, seq_length=20, num_features=47, d_model=64, num_heads=8, num_layers=2, d_ff=512, dropout=.1, gpu=False):
        super(TransformerModel, self).__init__()

        self.device = torch.device("cuda" if torch.cuda.is_available() and gpu else "cpu")

        self.seq_length = seq_length
        self.num_features = num_features
        self.input_projection = nn.Linear(num_features, d_model)
        self.input_norm = nn.LayerNorm(d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=num_heads,
            dim_feedforward=d_ff,
            dropout=dropout,
            batch_first=True,  # Input: (batch, seq, features)
            activation='relu',
            layer_norm_eps=1e-5
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers,
            enable_nested_tensor=False
        )
        self.transformer_norm = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 1)
        )
        self.input_projection.apply(init_weights)
        self.transformer_norm.apply(init_weights)
        self.mlp.apply(init_weights)

    def forward(self, x):
        batch_size = x.shape[0]
        x = x.to(self.device)

        if torch.isnan(x).any():
            print("⚠️  Input contains NaN!")
            return torch.zeros(batch_size, 1, device=self.device)

        x = self.input_projection(x)

        # Clip to prevent explosion
        x = torch.clamp(x, min=-5, max=5)
        x = self.input_norm(x)

        if torch.isnan(x).any():
            print("⚠️  NaN after input projection!")
            return torch.zeros(batch_size, 1, device=self.device, requires_grad=True)

        x = self.transformer_encoder(x)

        # Clamp after transformer
        x = torch.clamp(x, min=-5, max=5)
        x = self.transformer_norm(x)

        if torch.isnan(x).any():
            print("⚠️  NaN after transformer!")
            x = torch.nan_to_num(x, 0., posinf=5.0, neginf=-5.0)

        x = x.mean(dim=1)

        if torch.isnan(x).any():
            print("⚠️  NaN after pooling!")

        x = self.mlp(x)

        if torch.isnan(x).any():
            print("⚠️  NaN after MLP!")

        return x

    def predict(self, x):
        self.model.eval()

        X_test_tensor = torch.from_numpy(x).float()

        predictions_list = []

        with torch.no_grad():
            batch_size = 32
            for i in range(0, len(x), batch_size):
                X_batch = X_test_tensor[i:i + batch_size].to(self.device)
                predictions = self.model(X_batch)
                predictions_list.append(predictions.cpu().numpy())

        predictions = np.concatenate(predictions_list, axis=0)
        predictions = predictions.flatten()
        return predictions

class TransformerInvestor:
    def __init__(self, seq_length=20, num_features=None, num_heads=8,
                 d_ff=512, num_layers=2, dropout=0.1, gpu=False):
        self.seq_length = seq_length
        self.num_features = num_features
        self.num_heads = num_heads
        self.d_ff = d_ff
        self.num_layers = num_layers
        self.dropout = dropout
        self.gpu = gpu

        self.model = None
        self.scaler = RobustScaler()
        self.target_scaler = RobustScaler()
        self.device = torch.device('cuda' if torch.cuda.is_available() and gpu else 'cpu')
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'best_epoch': 0,
            'best_val_loss': float('inf')
        }

        print(f"TransformerInvestor initialized")
        print(f"Device: {self.device}")

    def prepare_data(self, features_df, target_series, batch_size=32, val_size=.1):
        print("\n" + "=" * 80)
        print("DATA PREPARATION (TICKER-AWARE)")
        print("=" * 80)

        if 'ticker' not in features_df.columns:
            raise ValueError("features_df must contain a 'ticker' column!")

        # ===== RESET INDICES FIRST TO ENSURE ALIGNMENT =====
        features_df = features_df.reset_index(drop=True)
        target_series = target_series.reset_index(drop=True)

        # ===== REMOVE NaN TARGETS BEFORE PROCESSING =====
        valid_mask = ~target_series.isna()
        features_df = features_df[valid_mask.values].reset_index(drop=True)  # .values prevents index alignment issues
        target_series = target_series[valid_mask].reset_index(drop=True)

        print(f"   Removed {(~valid_mask).sum()} rows with NaN targets")


        ticker_col = features_df['ticker'].copy()
        features_only = features_df.drop(columns=['ticker'])

        #Forward Fill NaNs
        features_only = features_only.reset_index(drop=True)
        for ticker in ticker_col.unique():
            mask = ticker_col == ticker
            indices = np.where(mask)[0]
            features_only.loc[indices] = features_only.loc[indices].fillna(method='ffill').fillna(method='bfill')

        # If still any NaN (at start of series), drop those rows
        still_nan_mask = features_only.isna().any(axis=1)
        features_only = features_only[~still_nan_mask.values].reset_index(drop=True)
        ticker_col = ticker_col[~still_nan_mask.values].reset_index(drop=True)
        target_series = target_series[~still_nan_mask.values].reset_index(drop=True)

        print(f"   {features_only.isna().sum().sum()} total NaN values in features (AFTER handling)")
        print(f"   Remaining samples: {len(target_series)}")
        print(f"   {target_series.isna().sum()} total NaN values in targets")
        print(f"   {np.isinf(features_only.values).sum()} total inf values in features")
        print(f"   {np.isinf(target_series.values).sum()} total inf values in targets")

        ticker_col = ticker_col.reset_index(drop=True)
        target_series = target_series.reset_index(drop=True)

        ticker_counts = ticker_col.value_counts().sort_index()
        print(f"  Samples per ticker:")
        for ticker, count in ticker_counts.items():
            print(f"    {ticker}: {count:,}")

        if self.num_features is None:
            self.num_features = features_only.shape[1]
            print(f"  Features detected: {self.num_features}")

        features_scaled = self.scaler.fit_transform(features_only)
        features_scaled = np.clip(features_scaled, -5, 5)

        # NEW: Scale targets to [-1, 1] range
        target_values = target_series.values.reshape(-1, 1)
        target_scaled = self.target_scaler.fit_transform(target_values)
        target_scaled = np.clip(target_scaled, -5, 5)
        target_scaled = target_scaled.flatten()

        X, y, ticker_sequence = self._create_sequences_per_ticker(
            features_scaled,
            target_scaled,
            ticker_col.values
        )

        total = len(X)
        train_size = int(total * (1 - val_size))

        X_train = X[:train_size]
        y_train = y[:train_size]
        ticker_train = ticker_sequence[:train_size]

        X_val = X[train_size:]
        y_val = y[train_size:]
        ticker_val = ticker_sequence[train_size:]


        X_train_tensor = torch.from_numpy(X_train).float()
        y_train_tensor = torch.from_numpy(y_train).float().unsqueeze(1)

        X_val_tensor = torch.from_numpy(X_val).float()
        y_val_tensor = torch.from_numpy(y_val).float().unsqueeze(1)

        # Create datasets
        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        val_dataset = TensorDataset(X_val_tensor, y_val_tensor)

        # Create dataloaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
        )

        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
        )

        print(f"  ✓ DataLoaders created")
        print(f"    Batch size: {batch_size}")
        print(f"    Train batches: {len(train_loader)}")
        print(f"    Val batches: {len(val_loader)}")
        print(f"    Target range (scaled): [{target_scaled.min():.4f}, {target_scaled.max():.4f}]")


        print("\n" + "=" * 80)

        return train_loader, val_loader

    def _create_sequences_per_ticker(self, features, targets, tickers):
        X = []
        y = []
        ticker_sequence = []

        unique_tickers = pd.Series(tickers).unique()

        for ticker in unique_tickers:
            ticker_mask = tickers == ticker
            ticker_indices = np.where(ticker_mask)[0]

            ticker_features = features[ticker_indices]
            ticker_targets = targets[ticker_indices]

            for i in range(self.seq_length, len(ticker_features)):
                seq_features = ticker_features[i - self.seq_length:i]
                seq_target = ticker_targets[i]

                X.append(seq_features)
                y.append(seq_target)
                ticker_sequence.append(ticker)

        return np.array(X), np.array(y), np.array(ticker_sequence)

    def build_model(self):
        print("\n" + "=" * 80)
        print("BUILDING TRANSFORMER MODEL")
        print("=" * 80)

        self.model = TransformerModel(
            seq_length=self.seq_length,
            num_features=self.num_features,
            num_heads=self.num_heads,
            d_ff=self.d_ff,
            num_layers=self.num_layers,
            dropout=self.dropout,
            gpu=self.gpu
        )

        self.model.to(self.device)

        # Count parameters
        total_params = sum(p.numel() for p in self.model.parameters())
        trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)

        print(f"\nModel Architecture:")
        print(f"  Input: ({self.seq_length}, {self.num_features})")
        print(f"  Transformer Blocks: {self.num_layers}")
        print(f"  Attention Heads: {self.num_heads}")
        print(f"  Feed-Forward Dim: {self.d_ff}")
        print(f"  Dropout: {self.dropout}")
        print(f"\nModel Parameters:")
        print(f"  Total: {total_params:,}")
        print(f"  Trainable: {trainable_params:,}")
        print("=" * 80)

    def train(self, train_loader, val_loader, epochs=15, learning_rate=5e-5, patience=3, save_best=True, warmup_epochs=2):
        if self.model is None:
            self.build_model()

        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        loss_fn = nn.MSELoss()

        # Learning rate warmup scheduler
        def lr_lambda(current_step):
            if current_step < warmup_epochs * len(train_loader):
                return float(current_step) / float(max(1, warmup_epochs * len(train_loader)))
            return 1.0

        warmup_scheduler = optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

        plateau_scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode='min',
            factor=0.5,
            patience=2,
            min_lr=1e-7,
        )

        print("\n" + "=" * 80)
        print("TRAINING TRANSFORMER MODEL")
        print("=" * 80)
        print(f"Device: {self.device}")
        print(f"Epochs: {epochs}")
        print(f"Learning Rate: {learning_rate}")
        print(f"Warmup Epochs: {warmup_epochs}")
        print(f"Weight Decay: 1e-5")
        print(f"Early Stopping Patience: {patience}")
        print(f"Train batches: {len(train_loader)}")
        print(f"Val batches: {len(val_loader)}")
        print("=" * 80 + "\n")


        best_val_loss = float('inf')
        patience_counter = 0
        start_time = time.time()

        for epoch in range(epochs):
            epoch_start = time.time()

            # Train epoch
            train_loss = self._train_epoch(self.model, train_loader, optimizer, loss_fn, warmup_scheduler)

            # Validate epoch
            val_loss = self._validate_epoch(self.model, val_loader, loss_fn)

            # Store metrics
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)

            if epoch >= warmup_epochs:
                plateau_scheduler.step(val_loss)

            epoch_time = time.time() - epoch_start

            # Print progress
            print(f"Epoch {epoch + 1:3d}/{epochs} | "
                  f"Train Loss: {train_loss:.6f} | "
                  f"Val Loss: {val_loss:.6f} | "
                  f"Time: {epoch_time:.1f}s")

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                self.history['best_epoch'] = epoch + 1
                self.history['best_val_loss'] = val_loss

                # Save best model
                if save_best:
                    self._save_model('./best_transformer_model.pth')
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"\nEarly stopping at epoch {epoch + 1} "
                          f"(no improvement for {patience} epochs)")
                    break

        total_time = time.time() - start_time

        if save_best:
            self._load_model('./best_transformer_model.pth')

        print("\n" + "=" * 80)
        print("TRAINING COMPLETE")
        print("=" * 80)
        print(f"Total Training Time: {total_time / 60:.1f} minutes")
        print(f"Best Epoch: {self.history['best_epoch']}")
        print(f"Best Validation Loss: {self.history['best_val_loss']:.6f}")
        print("=" * 80 + "\n")

        return self.history

    def _train_epoch(self, model, train_loader, optimizer, loss_fn, warmup_scheduler):
        model.train()
        total_loss = 0
        batch_count = 0

        for X_batch, y_batch in tqdm(train_loader, desc="Training", leave=False):

            #Move to GPU
            X_batch = X_batch.to(self.device)
            y_batch = y_batch.to(self.device)


            #Do a forward pass
            predictions = model(X_batch)

            if torch.isnan(predictions).any():
                print(f"⚠️  NaN in predictions at batch {batch_count}")
                continue

            loss = loss_fn(predictions, y_batch)

            if torch.isnan(loss).any():
                print(f"⚠️  NaN in loss at batch {batch_count}")
                continue

            #Do a backward pass
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            # Warmup scheduler step
            if warmup_scheduler is not None:
                warmup_scheduler.step()

            total_loss += loss.item()
            batch_count += 1

        avg_loss = total_loss / max(1, batch_count) if batch_count > 0 else float('inf')
        return avg_loss

    def _validate_epoch(self, model, val_loader, loss_fn):
        model.eval()
        total_loss = 0
        batch_count = 0

        with torch.no_grad():
            for X_batch, y_batch in tqdm(val_loader, desc="Validating", leave=False):
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                predictions = model(X_batch)

                if torch.isnan(predictions).any():
                    continue

                loss = loss_fn(predictions, y_batch)

                if torch.isnan(loss).any():
                    continue

                total_loss += loss.item()
                batch_count += 1

        avg_loss = total_loss / max(1, batch_count) if batch_count > 0 else float('inf')
        return avg_loss

    def _save_model(self, filepath):
        """Save model state dict."""
        torch.save(self.model.state_dict(), filepath)

    def _load_model(self, filepath):
        """Load model state dict."""
        if self.model is None:
            self.build_model()
        self.model.load_state_dict(torch.load(filepath))

    def save(self, filepath):
        """Save entire model for later use."""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'scaler': self.scaler,
            'target_scaler': self.target_scaler,
            'config': {
                'seq_length': self.seq_length,
                'num_features': self.num_features,
                'num_heads': self.num_heads,
                'd_ff': self.d_ff,
                'num_layers': self.num_layers,
                'dropout': self.dropout
            }
        }, filepath)

    def load(self, filepath):
        """Load entire model from checkpoint."""
        checkpoint = torch.load(filepath)
        config = checkpoint['config']

        self.seq_length = config['seq_length']
        self.num_features = config['num_features']
        self.num_heads = config['num_heads']
        self.d_ff = config['d_ff']
        self.num_layers = config['num_layers']
        self.dropout = config['dropout']
        self.scaler = checkpoint['scaler']
        self.target_scaler = checkpoint.get('target_scaler', self.target_scaler)


        self.build_model()
        self.model.load_state_dict(checkpoint['model_state_dict'])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--episodes", type=int, default=15)
    parser.add_argument("--gpu", type=bool, default=True)
    parser.add_argument("--use-precomputed-df", type=bool, default=False)
    args = parser.parse_args()

    if args.use_precomputed_df:
        features = pd.read_csv('target_series.csv')
        target = pd.read_csv('feature_dataset.csv')
    else:
        tickers = get_sp500_at_date(date(2025, 1, 1))

        features, target = build_full_features(tickers, start_date=date(2019, 1, 1), end_date=date(2025, 1, 1))
        features = features.sort_values(['ticker', 'Date']).reset_index(drop=True)
        features = features.drop(columns=['Date'])
        target.to_csv("target_series.csv")
        features.to_csv("feature_dataset.csv")

    model = TransformerInvestor(gpu=True)

    train_dataloader, val_dataloader= model.prepare_data(features, target)
    history = model.train(train_dataloader, val_dataloader, epochs=15, patience=3)
    #predictions = model.predict(X_test)
    model.save('./transformer_investor_ticker_aware.pth')