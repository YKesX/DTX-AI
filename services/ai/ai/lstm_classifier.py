"""Shared LSTM-Autoencoder + classification head architecture.

Imported by both the runtime detector (services/ai/ai/model_loader.py) and the
training notebook (services/ai/dtxai_model_training.ipynb) so that saved
state_dict keys always line up.
"""

from __future__ import annotations

import torch
import torch.nn as nn


class LSTMAutoencoderClassifier(nn.Module):
    """Sequence autoencoder with a multi-class classification head on the latent.

    ``forward(x)`` returns ``(reconstructed, logits)``:
      - reconstructed: same shape as input, used for the reconstruction loss /
        anomaly-magnitude signal at runtime.
      - logits: ``[batch, num_classes]``, used for cross-entropy training and
        argmax classification at runtime.

    ``dropout`` is applied between the two linear layers of the classification
    head (and optionally inside the LSTMs when num_layers > 1). It defaults to
    a small value because the current synthetic dataset is so easy that any
    larger value just adds noise — but the knob is exposed so retrains against
    a noisier dataset can crank it up.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        latent_dim: int,
        num_classes: int,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.num_classes = num_classes
        self.dropout = dropout

        # Encoder
        self.encoder = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.hidden_to_latent = nn.Linear(hidden_dim, latent_dim)

        # Decoder
        self.latent_to_hidden = nn.Linear(latent_dim, hidden_dim)
        self.decoder = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.hidden_to_output = nn.Linear(hidden_dim, input_dim)

        # Classification head on the latent vector with dropout regularisation.
        self.classifier = nn.Sequential(
            nn.Linear(latent_dim, latent_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(latent_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: [batch, seq, input_dim]
        _, (hidden, _) = self.encoder(x)
        latent = self.hidden_to_latent(hidden[-1])

        hidden_dec = self.latent_to_hidden(latent).unsqueeze(0)
        dec_out, _ = self.decoder(x, (hidden_dec, torch.zeros_like(hidden_dec)))
        reconstructed = self.hidden_to_output(dec_out)

        logits = self.classifier(latent)
        return reconstructed, logits
