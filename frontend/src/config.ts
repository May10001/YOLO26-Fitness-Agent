/**
 * Centralized API configuration.
 *
 * In development, Vite reads from .env / .env.development.
 * In production (npm run build), reads from .env.production.
 * Deploy: set VITE_API_URL to your backend server URL before building.
 *
 * Example:
 *   VITE_API_URL=https://your-server.com npm run build
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8002'

// Derive WebSocket URL from HTTP URL
const wsBase = API_BASE.replace(/^http/, 'ws')

export const config = {
  apiBase: API_BASE,
  wsUrl: `${wsBase}/ws/detect`,
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
    configScoring: `${API_BASE}/api/config/scoring`,
  },
}
