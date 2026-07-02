/**
 * Centralized API configuration.
 *
 * Defaults to relative URLs (empty API_BASE) — requests go to same origin.
 * Vercel production uses rewrites to proxy /api/* and /ws/* to ECS backend.
 * Local development: set VITE_API_URL=http://localhost:8002 in .env.local
 */
const API_BASE = import.meta.env.VITE_API_URL || ''

// WebSocket URL: derive from current page or use API_BASE
function getWsUrl(): string {
  if (API_BASE) {
    return API_BASE.replace(/^http/, 'ws') + '/ws/detect'
  }
  // Relative: use same origin, auto-detect wss:// for HTTPS
  const proto = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${typeof window !== 'undefined' ? window.location.host : 'localhost:8002'}/ws/detect`
}

export const config = {
  apiBase: API_BASE,
  wsUrl: getWsUrl(),
  endpoints: {
    health: `${API_BASE}/api/health`,
    exercises: `${API_BASE}/api/exercises`,
    chat: `${API_BASE}/api/chat`,
    sessions: `${API_BASE}/api/sessions`,
    sessionStart: `${API_BASE}/api/session/start`,
    sessionStop: `${API_BASE}/api/session/stop`,
    profile: `${API_BASE}/api/profile`,
    profileLoad: (name: string) => `${API_BASE}/api/profile/${name}`,
    planGenerate: `${API_BASE}/api/plan/generate`,
    aiPlanGenerate: `${API_BASE}/api/plan/ai-generate`,
    configScoring: `${API_BASE}/api/config/scoring`,
  },
}
