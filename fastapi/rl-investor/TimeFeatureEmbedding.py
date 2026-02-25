import numpy as np

class TimeFeatureEmbedding:
    def __init__(self, output_dim, sequence_length):
        self.output_dim = output_dim
        self.sequence_length = sequence_length

    def forward(self):
        # Create a range of week sequences (1-5 repeated) for positions
        pos = np.arange(self.sequence_length)

        # Create a range of frequency bands
        output_range = np.arange(0, self.output_dim)

        # Find the frequency where the sinusoids will oscilate.
        # Added 10000 base to spread frequencies across a wide range so both long-range and short-range differences are captured
        inv_frequency = 1.0 / (10000 ** (output_range / self.output_dim))

        # Pair together the positions and frequencies to create (date, angle) pairs kindof
        sinusoid_input = np.outer(pos, inv_frequency)

        #Create the embedding
        P_embeddings = np.concatenate([
            np.sin(sinusoid_input),
            np.cos(sinusoid_input)
        ], axis=1)

        #Create Weekly (5) and Monthly (21) cyclical component
        P5  = 2 * np.pi / 5
        P21 = 2 * np.pi / 21

        W_sin = np.sin(pos * P5).reshape(-1, 1)
        W_cos = np.cos(pos * P5).reshape(-1, 1)
        M_sin = np.sin(pos * P21).reshape(-1, 1)
        M_cos = np.cos(pos * P21).reshape(-1, 1)

        #Concatenate all components to create the final embedding
        final_embedding = np.concatenate([P_embeddings, W_sin, W_cos, M_sin, M_cos], axis=-1)

        return final_embedding