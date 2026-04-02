const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8484";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

// Scores
export const getScores = (params?: string) =>
  apiFetch<any>(`/api/scores${params ? `?${params}` : ""}`);
export const getCandidates = (params?: string) =>
  apiFetch<any>(`/api/scores/candidates${params ? `?${params}` : ""}`);
export const getSummary = () => apiFetch<any>("/api/scores/summary");
export const getScore = (tmdbId: number) =>
  apiFetch<any>(`/api/scores/${tmdbId}`);
export const getScoreHistory = (tmdbId: number) =>
  apiFetch<any>(`/api/scores/${tmdbId}/history`);

// Config
export const getWeights = () => apiFetch<any>("/api/config/weights");
export const updateWeights = (weights: any) =>
  apiFetch<any>("/api/config/weights", {
    method: "PUT",
    body: JSON.stringify(weights),
  });
export const getThreshold = () => apiFetch<any>("/api/config/threshold");
export const updateThreshold = (threshold: number) =>
  apiFetch<any>("/api/config/threshold", {
    method: "PUT",
    body: JSON.stringify({ candidate_threshold: threshold }),
  });

// Media
export const getMedia = (tmdbId: number) =>
  apiFetch<any>(`/api/media/${tmdbId}`);
export const protectTitle = (tmdbId: number, reason?: string) =>
  apiFetch<any>(`/api/media/${tmdbId}/protect`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null }),
  });
export const unprotectTitle = (tmdbId: number) =>
  apiFetch<any>(`/api/media/${tmdbId}/protect`, { method: "DELETE" });
export const getProtected = () => apiFetch<any>("/api/media/protected/list");

// Actions
export const triggerScoring = () =>
  apiFetch<any>("/api/actions/score", { method: "POST" });
export const getStatus = () => apiFetch<any>("/api/actions/status");
export const markRemoved = (tmdbId: number) =>
  apiFetch<any>(`/api/actions/remove/${tmdbId}`, { method: "POST" });
export const getRemovalHistory = (params?: string) =>
  apiFetch<any>(`/api/actions/removal-history${params ? `?${params}` : ""}`);
export const getSchedule = () => apiFetch<any>("/api/actions/schedule");
export const updateSchedule = (cron: string) =>
  apiFetch<any>("/api/actions/schedule", {
    method: "PUT",
    body: JSON.stringify({ cron_expression: cron }),
  });
export const getRunHistory = (params?: string) =>
  apiFetch<any>(`/api/actions/runs${params ? `?${params}` : ""}`);

// Health
export const getHealth = () => apiFetch<any>("/api/health");
export const getServiceStatus = () => apiFetch<any>("/api/health/services");
