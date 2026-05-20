from __future__ import annotations

import torch
import torch.nn as nn


class CNNClassifier(nn.Module):
    """Lightweight 1D CNN classifier over the sensor feature sequence.

    Supports both legacy single-row input ([batch, 1, features]) and windowed
    training input ([batch, features, window]).
    """

    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        window_size: int = 1,
        conv_channels: int = 32,
        kernel_size: int = 3,
        hidden_dim: int = 64,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.window_size = window_size
        padding = (kernel_size - 1) // 2
        self.conv = nn.Sequential(
            nn.Conv1d(in_channels=input_dim, out_channels=conv_channels, kernel_size=kernel_size, padding=padding),
            nn.BatchNorm1d(conv_channels),
            nn.ReLU(inplace=True),
            nn.Conv1d(in_channels=conv_channels, out_channels=conv_channels, kernel_size=kernel_size, padding=padding),
            nn.BatchNorm1d(conv_channels),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Linear(conv_channels, hidden_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Accept windowed inputs [batch, window, features] or legacy [batch, 1, features].
        if x.dim() != 3:
            raise ValueError(f"Expected 3D tensor [batch, channels, length], got {x.shape}")
        if x.size(2) == self.input_dim and x.size(1) != self.input_dim:
            x = x.transpose(1, 2)

        x = self.conv(x)
        x = x.view(x.size(0), -1)
        return self.classifier(x)
