from collections import namedtuple

import torch
from torch import nn
#Create a container for a one timestep of experience

Transition = namedtuple('Transition',[
    'state',        # The state observed at time t from TimeAwareMultiHeadAttention
    'action',       # The portfolio weights chosen at time t by the ActorCritic model
    'reward',       # The reward received after taking the action (delta_P - gamma * icvaR)
    'value',       # Critics estimate of how good this state is
    'log_prob',   # The log probability of the action taken under the current policy (for PPO updates)
    'done'          # A boolean indicating if the episode ended at time t+1
])

class ActorCritic(nn.Module):
    def __init__(self, input_dim, num_tickers):
        super().__init__()

        #Define the shared layers for both actor and critic for action selection (learns same feature representation of market state for both tasks)
        self.shared = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU()
        )

        #Actor head for the portfolio weights (one weight per ticker)
        self.actor = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, num_tickers)
        )

        #Critic head for the state value estimation, used for computing GAE to reduce variance in advantage estimation
        self.critic = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

        #Learnable log standard deviation for action distribution (one per ticker)
        self.log_std = nn.Parameter(torch.zeros(num_tickers))

    def forward(self, x):

        #Split features into actor/critic shared layers, then separate heads for action mean and state value
        shared = self.shared(x)
        action_mean = torch.softmax(self.actor(shared), dim=-1)
        state_value = self.critic(shared)
        return action_mean, state_value

    def get_action(self, x):
        action_mean, state_value = self.forward(x)
        std = self.log_std.exp()

        #Create a Gaussian distribution over the portfolio weights for stochasticity during training
        dist = torch.distributions.Normal(action_mean, std)
        action = dist.sample()

        #Clamp to valid portfolio weight range
        action = torch.clamp(action, 0.0, 1.0)

        #Normalize portfolio weights
        action = action / (action.sum() + 1e-8)

        # Sum log probs across tickers
        log_prob = dist.log_prob(action).sum(dim=-1)


        return action, log_prob, state_value.squeeze(-1)

    def evaluate(self, states, actions):
        action_mean, state_value = self.forward(states)
        std = self.log_std.exp()

        dist = torch.distributions.Normal(action_mean, std)

        #Get the log probability and entropy over the new distribution for the actions taken in the trajectory, used for PPO updates
        log_prob = dist.log_prob(actions).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)

        return log_prob, state_value.squeeze(-1), entropy

class PPO:
    def __init__(self, input_dim, num_tickers, device, lr=3e-4, gamma=.99, gae_lambda=.95, clip_epsilon=.2, epochs=20, batch_size=64, entropy_coef=.01, value_coef=.5):
        self.device = device

        #Discount Factor
        self.gamma = gamma

        #GAE smoothing parameter
        self.gae_lambda = gae_lambda

        #PPO clipping range. Policy can only change by this much per update to prevent large destructive updates
        self.clip_epsilon = clip_epsilon

        #Update epochs per PPO update
        self.epochs = epochs

        #Batch size for PPO updates
        self.batch_size = batch_size

        #Coefficient for entropy regularization (smaller encourages exploration)
        self.entropy_coef = entropy_coef

        #Critic loss weight to use to balance critical loss relative to actor loss
        self.value_coef = value_coef

        self.actor_critic = ActorCritic(input_dim, num_tickers).to(self.device)
        self.optimizer = torch.optim.Adam(self.actor_critic.parameters(), lr=lr)

    def compute_gae(self, transitions, next_value):
        rewards = [t.reward for t in transitions]
        values = [t.value for t in transitions]
        dones = [t.done for t in transitions]

        advantages = []
        gae = 0.0

        #Work backwards through the trajectory to compute GAE advantages
        for t in reversed(range(len(transitions))):
            if t == len(transitions) - 1:
                next_val = next_value
            else:
                next_val = values[t+1]

            #Zero out future values to restrict model
            not_done = 1.0 - float(dones[t])
            delta = rewards[t] + self.gamma * next_val * not_done - values[t]

            gae = delta + self.gamma * self.gae_lambda * not_done * gae
            advantages.insert(0, gae)

        #Convert advantages to a tensor and normalize for stability
        advantages = torch.tensor(advantages, dtype=torch.float32)

        returns = advantages + torch.tensor(values, dtype=torch.float32)

        #Normalize advantages to have mean 0 and std 1 for more stable training
        #Accomodate for rare occurence all advantages are the same value
        if advantages.std() > 1e-8:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        else:
            advantages = advantages - advantages.mean()


        return advantages, returns

    def update(self, transitions, next_value):
        advantages, returns = self.compute_gae(transitions, next_value)

        #Convert stored experience into tensors for PPO updates
        states = torch.stack([torch.tensor(t.state, dtype=torch.float32) for t in transitions]).to(self.device)
        actions = torch.stack([torch.tensor(t.action, dtype=torch.float32) for t in transitions]).to(self.device)
        old_log_probs = torch.stack([torch.tensor(t.log_prob, dtype=torch.float32) for t in transitions]).to(self.device)

        advantages = advantages.to(self.device)
        returns = returns.to(self.device)

        total_loss = 0.0
        total_actor = 0.0
        total_critic = 0.0
        total_entropy = 0.0
        num_updates = 0

        #Multiple epochs of updates over the collected trajectory
        for epoch in range(self.epochs):

            #Create random mini-batches for stochastic updates
            indices = torch.randperm(len(transitions))

            for start in range(0, len(transitions), self.batch_size):
                batch_idx = indices[start:start + self.batch_size]
                batch_states = states[batch_idx]
                batch_actions = actions[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]

                #Re-evaluate the action log probabilities, state values, and entropy for the current policy
                new_log_probs, state_values, entropy = self.actor_critic.evaluate(batch_states, batch_actions)

                #probability ratio for PPO clipping, shows how much the policy has changed
                ratio = (new_log_probs - batch_old_log_probs).exp()

                #Clipped for more controlled gradient updates
                unclipped = ratio * batch_advantages
                clipped = torch.clamp(ratio, 1.0 - self.clip_epsilon, 1.0 + self.clip_epsilon) * batch_advantages

                #Find the actor loss
                actor_loss = -torch.min(unclipped, clipped).mean()

                #Critic loss as MSE between returns and value estimates
                critic_loss = nn.MSELoss()(state_values, batch_returns)

                #Entropy bonus to encourage exploration
                entropy_loss = -entropy.mean()

                #Total loss with entropy regularization
                loss = actor_loss + self.value_coef * critic_loss + self.entropy_coef * entropy_loss

                if not torch.isfinite(loss):
                    self.optimizer.zero_grad()
                    print("WARNING: Non-finite loss, skipping batch")
                    continue

                self.optimizer.zero_grad()
                loss.backward()

                #Gradient clipping for stability
                nn.utils.clip_grad_norm_(self.actor_critic.parameters(), max_norm=0.5)

                self.optimizer.step()

                total_loss += loss.item()
                total_actor += actor_loss.item()
                total_critic += critic_loss.item()
                total_entropy += entropy_loss.item()
                num_updates += 1

        # Guard against division by zero if all batches were skipped
        if num_updates == 0:
            return {'loss': 0.0, 'actor_loss': 0.0, 'critic_loss': 0.0, 'entropy_loss': 0.0}

        return {
            'loss': total_loss / num_updates,
            'actor_loss': total_actor / num_updates,
            'critic_loss': total_critic / num_updates,
            'entropy_loss': total_entropy / num_updates
        }