// Browser storage helpers. Every key is prefixed so "Reset demo workspace" can clear only ours.
export const PREFIX = 'kirchhoff.'

export function readJson<T>(key: string, fallback: T, store: Storage = localStorage): T {
  try {
    const raw = store.getItem(PREFIX + key)
    return raw === null ? fallback : (JSON.parse(raw) as T)
  } catch {
    return fallback
  }
}

export function writeJson(key: string, value: unknown, store: Storage = localStorage): void {
  try {
    store.setItem(PREFIX + key, JSON.stringify(value))
  } catch {
    // storage full or blocked (private mode): onboarding simply does not persist
  }
}

export function clearKirchhoffStorage(): void {
  for (const store of [localStorage, sessionStorage]) {
    const keys: string[] = []
    for (let i = 0; i < store.length; i++) {
      const k = store.key(i)
      if (k?.startsWith(PREFIX)) keys.push(k)
    }
    keys.forEach((k) => store.removeItem(k))
  }
}
