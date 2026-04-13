export const mockEvents = [
  {
    id: 'evt-001',
    timestamp: '2026-03-24T10:42:13Z',
    entity: 'Forklift-01',
    anomaly_type: 'Forklift Proximity Risk',
    anomaly_score: 0.91,
    severity: 'critical',
    top_features: [
      { name: 'Proximity', value: '0.8 m', impact: 0.92 },
      { name: 'Speed', value: '12 km/h', impact: 0.74 },
      { name: 'Zone Violation', value: '1', impact: 0.61 },
    ],
    explanation:
      'Forklift-01 approached a human worker to within 0.8 meters. This is well below the 1.5-meter safety threshold. The forklift did not slow down and continued moving despite the warning.',
  },
  {
    id: 'evt-002',
    timestamp: '2026-03-24T10:38:55Z',
    entity: 'Human-03',
    anomaly_type: 'Restricted Zone Entry',
    anomaly_score: 0.83,
    severity: 'high',
    top_features: [
      { name: 'Zone Violation', value: 'Yes', impact: 0.88 },
      { name: 'Proximity', value: '1.2 m', impact: 0.55 },
      { name: 'Direction', value: 'Inbound', impact: 0.47 },
    ],
    explanation:
      'The worker identified as Human-03 entered a restricted warehouse zone without authorization. The zone overlaps with an active forklift path, and a collision risk was detected.',
  },
  {
    id: 'evt-003',
    timestamp: '2026-03-24T10:31:22Z',
    entity: 'Forklift-02',
    anomaly_type: 'Unexpected Stop',
    anomaly_score: 0.67,
    severity: 'medium',
    top_features: [
      { name: 'Stop Duration', value: '47 s', impact: 0.82 },
      { name: 'Speed', value: '0 km/h', impact: 0.65 },
      { name: 'Direction', value: 'Stationary', impact: 0.38 },
    ],
    explanation:
      'Forklift-02 made an unplanned 47-second stop on its active task route. Stops like this often indicate a mechanical fault or obstacle detection. Operator intervention may be required.',
  },
  {
    id: 'evt-004',
    timestamp: '2026-03-24T10:25:08Z',
    entity: 'Sensor-Rack-B',
    anomaly_type: 'Vibration Increase',
    anomaly_score: 0.54,
    severity: 'medium',
    top_features: [
      { name: 'RMS Vibration', value: '4.2 g', impact: 0.91 },
      { name: 'Speed', value: 'N/A', impact: 0.22 },
      { name: 'Stop Duration', value: 'N/A', impact: 0.15 },
    ],
    explanation:
      'The Sensor-Rack-B sensor on the rack system is recording above-normal vibration values (4.2 g). This may indicate nearby movement or rack instability. A structural integrity check is recommended.',
  },
  {
    id: 'evt-005',
    timestamp: '2026-03-24T10:18:44Z',
    entity: 'Human-07',
    anomaly_type: 'Forklift Proximity Risk',
    anomaly_score: 0.38,
    severity: 'low',
    top_features: [
      { name: 'Proximity', value: '2.1 m', impact: 0.52 },
      { name: 'Speed', value: '3 km/h', impact: 0.31 },
      { name: 'Direction', value: 'Approaching', impact: 0.28 },
    ],
    explanation:
      'Human-07 moved within 2.1 meters of an active forklift route. The distance is still within acceptable bounds, but the approach direction and low speed warrant attention. Low-priority monitoring is recommended.',
  },
];
