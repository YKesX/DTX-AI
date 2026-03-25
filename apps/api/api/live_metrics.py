"""In-memory live replay metrics for dataset validation demo mode."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock


class LiveReplayMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.total_replayed = 0
            self.total_correct = 0
            self.last_updated = None
            self.per_class_ground_truth = defaultdict(int)
            self.per_class_predicted = defaultdict(int)
            self.confusion = defaultdict(int)
            self.per_model = defaultdict(int)

    def update(self, *, ground_truth: str, predicted: str, correct: bool, model_key: str) -> None:
        with self._lock:
            self.total_replayed += 1
            if correct:
                self.total_correct += 1
            self.per_class_ground_truth[str(ground_truth)] += 1
            self.per_class_predicted[str(predicted)] += 1
            self.confusion[f"{ground_truth}->{predicted}"] += 1
            self.per_model[str(model_key)] += 1
            self.last_updated = datetime.now(timezone.utc)

    def snapshot(self) -> dict:
        with self._lock:
            accuracy = (
                self.total_correct / self.total_replayed if self.total_replayed else 0.0
            )
            return {
                "total_replayed": self.total_replayed,
                "total_correct": self.total_correct,
                "running_accuracy": round(accuracy, 6),
                "per_class_ground_truth": dict(self.per_class_ground_truth),
                "per_class_predicted": dict(self.per_class_predicted),
                "confusion_counts": dict(self.confusion),
                "per_model": dict(self.per_model),
                "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            }


live_metrics = LiveReplayMetrics()
