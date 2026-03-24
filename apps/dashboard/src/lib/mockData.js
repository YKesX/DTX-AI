export const mockEvents = [
  {
    id: 'evt-001',
    timestamp: '2026-03-24T10:42:13Z',
    entity: 'Forklift-01',
    anomaly_type: 'Forklift Yakını Riski',
    anomaly_score: 0.91,
    severity: 'critical',
    top_features: [
      { name: 'Yakınlık', value: '0.8 m', impact: 0.92 },
      { name: 'Hız', value: '12 km/h', impact: 0.74 },
      { name: 'Bölge İhlali', value: '1', impact: 0.61 },
    ],
    explanation:
      'Forklift-01, insan çalışanına 0.8 metre mesafeye kadar yaklaşmıştır. Bu mesafe güvenlik sınırının (1.5 m) çok altındadır. Forkliftin hızı azaltılmamış ve uyarıya rağmen hareket sürmüştür.',
  },
  {
    id: 'evt-002',
    timestamp: '2026-03-24T10:38:55Z',
    entity: 'Human-03',
    anomaly_type: 'Yasak Bölge Girişi',
    anomaly_score: 0.83,
    severity: 'high',
    top_features: [
      { name: 'Bölge İhlali', value: 'Evet', impact: 0.88 },
      { name: 'Yakınlık', value: '1.2 m', impact: 0.55 },
      { name: 'Yön', value: 'İçeri', impact: 0.47 },
    ],
    explanation:
      'Human-03 kimliğiyle tanımlanan çalışan, depo içindeki kısıtlı bölgeye yetkisiz giriş yapmıştır. Bölge aktif forklift rotasıyla çakışmaktadır ve çarpışma riski tespit edilmiştir.',
  },
  {
    id: 'evt-003',
    timestamp: '2026-03-24T10:31:22Z',
    entity: 'Forklift-02',
    anomaly_type: 'Beklenmeyen Duruş',
    anomaly_score: 0.67,
    severity: 'medium',
    top_features: [
      { name: 'Duruş Süresi', value: '47 sn', impact: 0.82 },
      { name: 'Hız', value: '0 km/h', impact: 0.65 },
      { name: 'Yön', value: 'Sabit', impact: 0.38 },
    ],
    explanation:
      'Forklift-02, aktif görev rotasında 47 saniyelik planlanmamış bir duruş gerçekleştirmiştir. Bu tür duruşlar genellikle mekanik arıza veya engel tespitini işaret etmektedir. Operatör müdahalesi gerekebilir.',
  },
  {
    id: 'evt-004',
    timestamp: '2026-03-24T10:25:08Z',
    entity: 'Sensor-Rack-B',
    anomaly_type: 'Vibrasyon Artışı',
    anomaly_score: 0.54,
    severity: 'medium',
    top_features: [
      { name: 'RMS Vibrasyon', value: '4.2 g', impact: 0.91 },
      { name: 'Hız', value: 'N/A', impact: 0.22 },
      { name: 'Duruş Süresi', value: 'N/A', impact: 0.15 },
    ],
    explanation:
      'Raf sistemindeki Sensor-Rack-B sensörü normalin üzerinde titreşim değerleri kaydetmektedir (4.2 g). Bu, yakın geçişlerin veya raf dengesizliğinin göstergesi olabilir. Yapısal bütünlük kontrolü önerilir.',
  },
  {
    id: 'evt-005',
    timestamp: '2026-03-24T10:18:44Z',
    entity: 'Human-07',
    anomaly_type: 'Forklift Yakını Riski',
    anomaly_score: 0.38,
    severity: 'low',
    top_features: [
      { name: 'Yakınlık', value: '2.1 m', impact: 0.52 },
      { name: 'Hız', value: '3 km/h', impact: 0.31 },
      { name: 'Yön', value: 'Yaklaşıyor', impact: 0.28 },
    ],
    explanation:
      'Human-07, aktif forklift güzergahına 2.1 metre mesafede hareket etmiştir. Mesafe kabul edilebilir sınır içinde olsa da yaklaşma yönü ve düşük hız dikkat gerektirmektedir. Düşük öncelikli izleme önerilir.',
  },
];

