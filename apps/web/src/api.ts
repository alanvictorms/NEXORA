import type { EventItem, ProjectDetail, ProjectSummary, Question } from "./types";

const API = import.meta.env.VITE_API_URL ?? "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  projects: () => request<ProjectSummary[]>("/projects"),
  project: (id: string) => request<ProjectDetail>(`/projects/${id}`),
  create: (name: string, initial_message: string) =>
    request<{ project: ProjectSummary }>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, initial_message }),
    }),
  message: (id: string, content: string) =>
    request(`/projects/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
  questions: (id: string) => request<Question[]>(`/projects/${id}/questions`),
  answer: (projectId: string, questionId: string, answer: string) =>
    request(`/projects/${projectId}/questions/${questionId}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),
  pipeline: (id: string) => request(`/projects/${id}/pipeline`, { method: "POST" }),
  events: (id: string) => request<EventItem[]>(`/projects/${id}/events`),
  resume: (id: string) => request(`/previews/${id}/resume`, { method: "POST" }),
  pause: (id: string) => request(`/previews/${id}/pause`, { method: "POST" }),
};

