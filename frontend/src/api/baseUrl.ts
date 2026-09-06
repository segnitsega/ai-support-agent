/** API origin for browser calls. Empty = same origin (Vite dev proxy). */
export function apiUrl(path: string): string {
  const fromWindow =
    typeof window !== 'undefined' ? window.__API_BASE__ : undefined
  const base = String(fromWindow ?? import.meta.env.VITE_API_URL ?? '')
    .trim()
    .replace(/\/$/, '')
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}
