import numpy as np
import torch

from MultiHeadAttention import TimeAwareMultiHeadAttention
from TimeFeatureEmbedding import TimeFeatureEmbedding
from PortfolioEnvironment import PortfolioEnvironment
from ParellelSubStrategy import ParallelSubStrategy
from PPO import PPO, Transition

class RL_Investor:
    def __init__(self, num_tickers, num_features=9, sequence_length=30, output_dim=64, num_heads=4, lambda_risk=.5, alpha=.5, gpu=False):
        self.sequence_length = sequence_length
        self.num_tickers = num_tickers
        self.num_features = num_features
        self.output_dim = output_dim
        self.num_heads = num_heads
        self.lambda_risk = lambda_risk

        self.time_embedding = TimeFeatureEmbedding(output_dim, sequence_length)
        self.time_features = self.time_embedding.forward()

        self.time_feature_dim = self.time_features.shape[-1]
        self.input_dim = self.num_features + self.time_feature_dim
        self.flattened_input_dim = self.num_tickers * self.input_dim

        self.attention = TimeAwareMultiHeadAttention(input_dim=self.flattened_input_dim,
                                                     output_dim=output_dim,
                                                     num_heads=num_heads,
                                                     head_dim=output_dim // num_heads,
                                                     sequence_length=sequence_length,
                                                     memory_length=50)

        if gpu:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device("cpu")

        print(f"Running on device: {self.device}")
        self.attention.to(self.device)

    def _prepare_inputs(self, data):
        # Create tensor
        tickers = sorted(data.keys())
        frames = []
        for ticker in tickers:
            df = data[ticker]

            df = df.ffill()
            df = df.bfill()
            df = df.fillna(0)

            # Clip extreme values that could destabilise training
            df = df.clip(
                lower=df.quantile(0.001),
                upper=df.quantile(0.999),
                axis=1
            )
            frames.append(df)
        tensor = np.stack(frames, axis=1)
        return torch.tensor(tensor, dtype=torch.float32).to(self.device)

    def _attach_time_features(self, data):
        num_days = data.shape[0]

        full_embedding = TimeFeatureEmbedding(output_dim=self.output_dim, sequence_length=num_days)
        tf_array = full_embedding.forward()

        #Trim time features to match the number of days in the input data and convert to tensor
        tf = torch.tensor(tf_array, dtype=torch.float32).to(self.device)

        #Expand time features to match the number of tickers and concatenate with input data
        tf = tf.unsqueeze(1).expand(-1, data.shape[1], -1)

        return torch.cat([data, tf], dim=-1)

    def train(self, training_data, training_opens, djia_opens, djia_closes, num_episodes=10, rollout_length=256):

        tickers = sorted(training_data.keys())

        ppo = PPO(input_dim=self.output_dim, num_tickers=len(tickers), device=self.device, epochs=20)

        #Rebuilt optimizer to include attention parameters in gradient updates
        all_params = list(ppo.actor_critic.parameters()) + list(self.attention.parameters())
        ppo.optimizer = torch.optim.Adam(all_params, lr=3e-4)
        env = PortfolioEnvironment(training_data, training_opens, tickers=tickers, lambda_risk=self.lambda_risk)
        parallel = ParallelSubStrategy(djia_closes, djia_opens)

        training_tensor = self._prepare_inputs(training_data)
        x = self._attach_time_features(training_tensor)

        for episode in range(num_episodes):
            state = env.reset()
            parallel.reset()
            done = False

            transitions = []
            ep_reward = 0.0

            while not done:
                step = env.current_step

                #Get windowed input for attention
                start = max(0, step - self.sequence_length)
                x_window = x[start: step+1].unsqueeze(0)

                #Flatten tickers into feature dim for attention
                batch_size, seq_len, num_tickers, feature_dim = x_window.shape
                x_flat = x_window.reshape(batch_size, seq_len, num_tickers * feature_dim).to(self.device)

                #Forward pass through attention
                attended = self.attention(x_flat)

                #Take the last timestep's output for the action
                last_x = attended[:, -1, :]

                action, log_prob, value = ppo.actor_critic.get_action(last_x)
                action_np = action.squeeze(0).detach().cpu().numpy()

                #Step parallel sub-strategy
                trend_index, short_limit, buy_limit, _ = parallel.step(float(action_np.mean()))

                #Step main environment with the trend signals
                next_state, reward, done = env.step(action_np, trend_index, short_limit, buy_limit)

                #Store the transition
                transitions.append(Transition(
                    state=last_x.squeeze(0).detach().cpu().numpy(),
                    action=action_np,
                    reward=reward,
                    value=value.item(),
                    log_prob=log_prob.item(),
                    done=done
                ))

                ep_reward += reward
                state = next_state

                #Update every rollout_length steps or at the end of the episode
                if len(transitions) >= rollout_length or done:
                    if done:
                        next_value = 0.0
                    else:
                        with torch.no_grad():
                            _, next_val = ppo.actor_critic(last_x)
                            next_value = next_val.squeeze(-1).item()

                    #Update the PPO agent with the collected transitions
                    metrics = ppo.update(transitions, next_value)

                    #Clear buffer
                    transitions = []

                    print(
                        f"Episode {episode + 1} | "
                        f"Step {step} | "
                        f"Portfolio Value: {env.portfolio_value:.2f} | "
                        f"Loss: {metrics['loss']:.4f} | "
                        f"Trend Index: {trend_index:.2f} | "
                    )


            print(f"Episode {episode + 1} completed with total reward: {ep_reward:.2f} and final portfolio value: {env.portfolio_value:.2f}")

        self.ppo = ppo


    def predict(self, testing_data, testing_opens, djia_opens, djia_closes):
        if not hasattr(self, 'ppo'):
            raise ValueError("Model must be trained before prediction")

        tickers = sorted(testing_data.keys())

        env = PortfolioEnvironment(testing_data, testing_opens, tickers=tickers, lambda_risk=self.lambda_risk)
        parallel = ParallelSubStrategy(djia_closes, djia_opens)

        testing_tensor = self._prepare_inputs(testing_data)
        x = self._attach_time_features(testing_tensor)

        env.reset()
        parallel.reset()
        done = False
        results = []

        while not done:
            step = env.current_step
            start = max(0, step - self.sequence_length)
            x_window = x[start: step+1].unsqueeze(0)

            batch_size, seq_len, num_tickers, feature_dim = x_window.shape
            x_flat = x_window.reshape(batch_size, seq_len, num_tickers * feature_dim).to(self.device)

            attended = self.attention(x_flat)

            last_x = attended[:, -1, :]

            with torch.no_grad():
                action, _, _ = self.ppo.actor_critic.get_action(last_x)
                action_np = action.squeeze(0).detach().cpu().numpy()

            trend_index, short_limit, buy_limit, _ = parallel.step(float(action_np.mean()))

            next_state, reward, done = env.step(action_np, trend_index, short_limit, buy_limit)

            results.append({
                "step": step,
                "portfolio_value": env.portfolio_value,
                "reward": reward,
                "trend_index": trend_index,
            })
        return results
