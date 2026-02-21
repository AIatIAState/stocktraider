import torch
from torch import nn
from TimeFeatureEmbedding import TimeFeatureEmbedding
import torch.nn.functional as F

class TimeAwareMultiHeadAttention(nn.Module):
    def __init__(self, input_dim, output_dim, num_heads, head_dim, sequence_length, memory_length):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.output_dim = output_dim
        self.sequence_length = sequence_length
        self.memory_length = memory_length
        self.input_dim = input_dim

        #Create learnable bias parameters: (U shifts by content, Y shifts by time)
        self.U = nn.Parameter(torch.randn(num_heads, head_dim))
        self.Y = nn.Parameter(torch.randn(num_heads, head_dim))

        #Output projection to map concatenated head outputs back to the desired output dimension
        self.output_projection = nn.Sequential(
            nn.Linear(num_heads * head_dim, output_dim),
            nn.GELU()
        )

        # Project the position features to the same dimension as the content features for attention calculations
        time_feature_out = num_heads * head_dim * 2 + 4
        self.position_projection = nn.Linear(time_feature_out, num_heads * head_dim, bias=False)

        #Learnable weights for combining the attention scores, one for each (content, weekly, monthly)
        self.wc = nn.Parameter(torch.ones(3))

        #Single projection for Q, K, F, V
        self.qkfv_projection = nn.Linear(input_dim, 4 * num_heads * head_dim, bias=False)

        #Instance normalization
        self.instance_norm = nn.InstanceNorm1d(input_dim, affine=True)

        #Position encoding for time features
        self.time_embedding = TimeFeatureEmbedding(output_dim=num_heads * head_dim,
                                                   sequence_length =sequence_length + memory_length)

        #precompute time features and register as buffer since they are fixed and not learnable parameters
        tf = self.time_embedding.forward()

        self.register_buffer("time_features", torch.tensor(tf, dtype=torch.float32))

    def _relative_shift(self, x):
        # Convert absolute positional scores into relative ones by shifting each row so position 0 aligns with the current timestep
        B, T, T_tau, H = x.shape

        # Pad with a dummy column at the end to allow for the shift
        x_pad = torch.nn.functional.pad(x, (0, 0, 1, 0))
        x_pad = x_pad.reshape(B, T_tau + 1, T, H)

        #strip first row and return
        x = x_pad[:, 1:, :, :].reshape(B, T, T_tau, H)
        return x

    def forward(self, x, memory=None):
        batch_size, trading_days, _ = x.shape
        tau = self.memory_length
        total_len = trading_days + tau

        #Concatenate memory with current input for attention calculations
        if memory is None:
            memory = torch.zeros(batch_size, tau, self.input_dim, device=x.device)

        x_combined = torch.cat([memory, x], dim=1)

        #Normalize the instance
        x_norm = self.instance_norm(x_combined.permute(0, 2, 1)).permute(0, 2, 1)

        #Project to Q (queries), K (keys), F (time features), V (values)
        qkfv = self.qkfv_projection(x_norm)
        Q, K, F_feat, V = torch.chunk(qkfv, 4, dim=-1)

        #Reshape to create multiple attention heads (ex. (1,40,64) -> (1,40,4,16))
        def reshape(t):
            t = t.reshape(batch_size, trading_days + tau, self.num_heads, self.head_dim)
            return t

        Q = reshape(Q)
        K = reshape(K)
        F_feat = reshape(F_feat)
        V = reshape(V)

        #Get weekly and monthly masks to only attend to the corresponding time features on a weekly or monthly basis
        D = self.head_dim
        Mw = torch.zeros(D, device=x.device)
        Mw[torch.arange(D) % 5 == 0] = 1.0
        Mm = torch.zeros(D, device=x.device)
        Mm[torch.arange(D) % 21 == 0] = 1.0

        #Apply the masks to the query projections to get the attention scores for the weekly and monthly heads, allowing them to focus on the relevant time features
        Qw = F.softmax(Q * Mw, dim=2)
        Qm = F.softmax(Q * Mm, dim=2)

        #Apply the weekly and monthly masks to the projected time features to get the time-based attention scores
        if total_len > self.time_features.shape[0]:
            full_embedding = TimeFeatureEmbedding(
                output_dim=self.num_heads * self.head_dim,
                sequence_length=total_len
            )
            tf = torch.tensor(
                full_embedding.forward(), dtype=torch.float32, device=x.device
            )
        else:
            tf = self.time_features[:total_len]  # (total_len, time_feature_dim)

        Rtime = self.position_projection(tf)  # (total_len, num_heads * head_dim)

        #reshape to match the dimensions for attention calculations (trading_days + tau, num_heads, head_dim)
        Rtime = Rtime.reshape(total_len, self.num_heads, self.head_dim)

        #Broadcast Rtime across the batch dimension since time embeddings are the same for all samples in the batch
        Rtime = Rtime.unsqueeze(0).expand(batch_size, -1, -1, -1)

        #Compute the four attention scores (Content, weekly, monthly, positional)

        #Compute content score taking current sequence queries, add the learnable content bias, and dot product with keys to get the content-based attention scores
        #Finds how relevant each past timestep is to the current day based purely on the content features, without considering time
        Q_content = Q[:, tau:] + self.U
        Sc = torch.einsum('bthd,bshd->btsh', Q_content, K)

        #Calculate weekly and monthly attention scores by taking the dot product of the masked queries with the projected time features, allowing these heads to focus on temporal patterns in the data
        #Finds if the current day matches a weekly or monthly pattern
        Sw = torch.einsum('bthd,bshd->btsh', Qw[:, tau:], F_feat)
        Sm = torch.einsum('bthd,bshd->btsh', Qm[:, tau:], F_feat)

        #Compute positional score by taking the dot product of the content queries with the projected time features
        # This allows the model to learn to attend to specific positions in the sequence based on temporal patterns, and then apply the relative shift to convert from absolute to relative positional attention
        Q_pos = Q[:, tau:] + self.Y
        Sp = torch.einsum('bthd,bshd->btsh', Q_pos, Rtime)
        Sp = self._relative_shift(Sp)

        #Combine the attention scores using the learnable weights and apply to V
        wc_norm = F.softmax(self.wc, dim=0)
        S = (
            wc_norm[0] * Sc +
            wc_norm[1] * Sw +
            wc_norm[2] * Sm +
            Sp
        )

        #Scale and normalize
        S = F.softmax(S / (D ** .5), dim=2)

        #Causal mask, prevents model from attending to future timesteps by masking out attention scores for any future positions beyond the current day
        Mseq = torch.ones(trading_days, trading_days + tau, device=x.device)
        for i in range(trading_days):
            Mseq[i, i + tau + 1:] = 0.0
        Mseq = Mseq.unsqueeze(0).unsqueeze(-1)

        S_masked = S * Mseq

        #Final attention weights
        W_attn = F.softmax(S_masked, dim=2)

        #Weighted sum over values, output is a blend of information from all days it attended to, with the attention weights determining how much each past day contributes to the representation of the current day
        O = torch.einsum('btsh,bshd->bthd', W_attn, V)

        #Reshape
        O = O.reshape(batch_size, trading_days, self.num_heads * self.head_dim)

        return self.output_projection(O)