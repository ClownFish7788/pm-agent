/**
 * 设置存储 —— localStorage 读写 + 订阅。
 *
 * 原则：零依赖，类型安全，改完立即生效。
 */

const STORAGE_KEY = "pm-agent-settings";

export interface AppSettings {
  /** FastAPI 后端地址（含 /analyze/stream） */
  backendUrl: string;
  /** LLM 调用硬上限 */
  maxCalls: number;
  /** 首次 POST 请求超时（秒） */
  firstByteTimeout: number;
}

const DEFAULTS: AppSettings = {
  backendUrl: "/api/analyze/stream",
  maxCalls: 30,
  firstByteTimeout: 30,
};

function load(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULTS };
}

function save(s: AppSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch { /* ignore */ }
}

let _settings = load();
const _listeners = new Set<(s: AppSettings) => void>();

export const settingsStore = {
  get(): AppSettings {
    return _settings;
  },

  set<K extends keyof AppSettings>(key: K, value: AppSettings[K]): void {
    _settings = { ..._settings, [key]: value };
    save(_settings);
    for (const fn of _listeners) fn(_settings);
  },

  setAll(patch: Partial<AppSettings>): void {
    _settings = { ..._settings, ...patch };
    save(_settings);
    for (const fn of _listeners) fn(_settings);
  },

  reset(): void {
    _settings = { ...DEFAULTS };
    save(_settings);
    for (const fn of _listeners) fn(_settings);
  },

  subscribe(fn: (s: AppSettings) => void): () => void {
    _listeners.add(fn);
    return () => _listeners.delete(fn);
  },
};
