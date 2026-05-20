from __future__ import annotations

import torch
import torch.nn as nn

class BiLSTMClassifier(nn.Module):
    """Standalone Bi-Directional LSTM classifier for time-series sensor data."""
    
    def __init__(
        self,
        input_dim: int,
        num_classes: int,
        window_size: int = 30, # Used for metadata compatibility
        hidden_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.window_size = window_size
        
        # Bi-LSTM Layer
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        
        # Classification Head (Bidirectional -> hidden_dim * 2)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(64, num_classes)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Expected shape: [Batch, Window, Features]
        if x.dim() != 3:
            raise ValueError(f"Expected 3D tensor [batch, window, features], got {x.shape}")
        
        out, _ = self.lstm(x)
        out_pooled = out.mean(dim=1) # Global Average Pooling
        return self.classifier(out_pooled)
