export const PREFERENCES_KEY = 'dtx-console-preferences-v1';
export const DEFAULT_PREFERENCES = {
  eventLimit: 100,
  refreshSeconds: 5,
  autoRefresh: true,
  esp32Url: 'http://dtx-esp32.local',
  hardwareInterval: 1,
  defaultModel: 'lightgbm',
};

export function validatePreferences(value) {
  if (!value || typeof value !== 'object') throw new Error('Invalid saved preferences.');
  const eventLimit = Number(value.eventLimit);
  const refreshSeconds = Number(value.refreshSeconds);
  const hardwareInterval = Number(value.hardwareInterval);
  if (![50, 100, 200].includes(eventLimit)) throw new Error('Choose 50, 100, or 200 events.');
  if (![3, 5, 10, 30].includes(refreshSeconds)) throw new Error('Choose a supported refresh interval.');
  if (!Number.isFinite(hardwareInterval) || hardwareInterval < 1 || hardwareInterval > 60) {
    throw new Error('Hardware polling must be between 1 and 60 seconds.');
  }
  let url;
  try { url = new URL(String(value.esp32Url).trim()); } catch {
    throw new Error('Enter a complete ESP32 URL, such as http://dtx-esp32.local.');
  }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
    throw new Error('Use an HTTP or HTTPS device address without a path, credentials, query, or fragment.');
  }
  if (typeof value.defaultModel !== 'string' || !/^[a-z0-9_]{1,64}$/.test(value.defaultModel)) {
    throw new Error('Choose a valid model.');
  }
  if (typeof value.autoRefresh !== 'boolean') throw new Error('Invalid automatic refresh preference.');
  return { eventLimit, refreshSeconds, hardwareInterval, autoRefresh: value.autoRefresh,
    esp32Url: url.origin, defaultModel: value.defaultModel };
}
