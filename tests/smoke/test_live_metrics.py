import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../apps/api"))

from api.live_metrics import LiveReplayMetrics


def test_live_metrics_update_and_accuracy():
    metrics = LiveReplayMetrics()
    metrics.update(ground_truth="bearing_fault", predicted="bearing_fault", correct=True, model_key="random_forest")
    metrics.update(ground_truth="overheating", predicted="bearing_fault", correct=False, model_key="random_forest")

    snapshot = metrics.snapshot()
    assert snapshot["total_replayed"] == 2
    assert snapshot["total_correct"] == 1
    assert snapshot["running_accuracy"] == 0.5
    assert snapshot["per_class_ground_truth"]["bearing_fault"] == 1
    assert snapshot["per_class_predicted"]["bearing_fault"] == 2
    assert snapshot["confusion_counts"]["overheating->bearing_fault"] == 1
    assert snapshot["per_model"]["random_forest"] == 2
