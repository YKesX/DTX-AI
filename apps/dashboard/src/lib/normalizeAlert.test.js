import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeAlert } from './normalizeAlert.js';

test('simulator positions never become alert rows', () => {
  assert.equal(normalizeAlert({ type: 'position_update', entity_id: 'forklift-01', x: 1, y: 2 }), null);
});

test('T5 explanation and source survive live and saved alert normalization', () => {
  const summary = 'Temperature rose under load.\nInspect cooling.';
  const live = normalizeAlert({
    event: { event_id: 'test-event', asset_id: 'forklift-01' },
    anomaly: { anomaly_type: 'overheat', is_anomaly: true },
    explanation: { summary, source: 't5', recommendation: 'Reduce load.' },
  });
  const saved = normalizeAlert({
    event_id: 'test-event', summary,
    raw_payload: JSON.stringify({ metadata: { explanation_source: 't5', recommendation: 'Reduce load.' } }),
  });
  for (const event of [live, saved]) {
    assert.equal(event.summary, summary);
    assert.equal(event.explanation_source, 't5');
    assert.equal(event.recommendation, 'Reduce load.');
  }
});
