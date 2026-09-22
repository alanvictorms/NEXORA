export type ProjectSummary = {
  id: string;
  name: string;
  slug: string;
  status: string;
  current_spec_version: number;
  current_architecture_version: number;
};

export type Question = {
  id: string;
  key: string;
  severity: string;
  question: string;
  reason: string;
  options: string[];
  recommended?: string;
  status: string;
  answer?: string;
};

export type EventItem = {
  id: string;
  sequence: number;
  type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ProjectDetail = {
  project: ProjectSummary;
  spec: Record<string, unknown> | null;
  architecture: Record<string, unknown> | null;
  task_graph: {
    id: string;
    version: number;
    status: string;
    tasks: { id: string; key: string; type: string; status: string; objective: string }[];
  } | null;
  preview: { id: string; state: string; url: string; idle_timeout_seconds: number } | null;
  production_plan: { monthly_credits: number; resources: Record<string, unknown> } | null;
};

