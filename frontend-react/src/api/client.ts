/**
 * Typed API client for the Delabyrix backend at http://localhost:8000
 * All types mirror the Pydantic models in architecture.md §6.
 */

export const BASE_URL = "http://localhost:8000";

// ─── Shared helpers ────────────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<{ data: T; status: number }> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok && res.status !== 202) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  const data: T = await res.json();
  return { data, status: res.status };
}

export class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ─── §6.1 Agent Pipeline ───────────────────────────────────────────────────────

export interface AgentQueryRequest {
  text: string;
  source_language: string;
  user_type: "patient" | "provider" | "coordinator";
  country: string;
  session_id?: string;
}

export interface PipelineTrace {
  jurisdiction: string;
  pii_redacted: boolean;
  translation: string;
  medical_interpretation: string;
  cultural_context: string;
  next_steps: string;
}

export interface AgentQueryResponse {
  session_id: string;
  pipeline_trace: PipelineTrace;
  escalated: false;
  review_id: null;
  response_text: string;
}

export interface AgentEscalatedResponse {
  session_id: string;
  escalated: true;
  review_id: string;
  status: "pending_review";
  message: string;
}

export type AgentQueryResult = AgentQueryResponse | AgentEscalatedResponse;

export interface SessionStatusResponse {
  session_id: string;
  status: "approved" | "pending" | "rejected";
  response_text: string | null;
  rejection_reason?: string | null;
}

export async function postAgentQuery(
  body: AgentQueryRequest
): Promise<{ result: AgentQueryResult; isEscalated: boolean }> {
  const { data, status } = await request<AgentQueryResult>("/agent/query", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return { result: data, isEscalated: status === 202 };
}

export async function getSessionStatus(
  sessionId: string
): Promise<SessionStatusResponse> {
  const { data } = await request<SessionStatusResponse>(
    `/agent/session/${sessionId}`
  );
  return data;
}

// ─── §6.2 Medication Registry ─────────────────────────────────────────────────

export interface RegistryRecord {
  medication_id: string;
  name_generic: string;
  jurisdiction: string;
  status: "approved" | "restricted" | "banned" | "delisted";
  restriction_reason: string | null;
  therapeutic_alternatives: string[];
  last_updated: string;
}

export interface RegistryListResponse {
  total: number;
  page: number;
  records: RegistryRecord[];
}

export interface RegistryCheckParams {
  medication_name: string;
  jurisdiction: "US_FDA" | "EU_EMA";
}

export async function getRegistryCheck(
  params: RegistryCheckParams
): Promise<RegistryRecord> {
  const qs = new URLSearchParams({
    medication_name: params.medication_name,
    jurisdiction: params.jurisdiction,
  });
  const { data } = await request<RegistryRecord>(`/registry/check?${qs}`);
  return data;
}

export async function getRegistryList(params: {
  page?: number;
  page_size?: number;
  jurisdiction?: string;
}): Promise<RegistryListResponse> {
  const qs = new URLSearchParams();
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  if (params.jurisdiction) qs.set("jurisdiction", params.jurisdiction);
  const { data } = await request<RegistryListResponse>(`/registry/list?${qs}`);
  return data;
}

// ─── §6.3 Documents ───────────────────────────────────────────────────────────

export interface DocumentResponse {
  doc_type: string;
  language: string;
  title: string;
  content: string;
}

export interface DocumentAnalysisResponse {
  filename: string;
  detected_language: string;
  jurisdiction: string;
  pii_redacted: boolean;
  redacted_preview: string;
  analysis: string;
}

export type DocType =
  | "consent_icu_admission"
  | "consent_surgery"
  | "billing_deductible_explanation";

export async function getDocument(
  docType: DocType,
  language: string
): Promise<DocumentResponse> {
  const { data } = await request<DocumentResponse>(
    `/documents/${docType}/${language}`
  );
  return data;
}

export async function postDocumentAnalyze(
  file: File,
  sourceLanguage: string,
  country: string
): Promise<DocumentAnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("source_language", sourceLanguage);
  formData.append("country", country);

  const url = `${BASE_URL}/documents/analyze`;
  const res = await fetch(url, { method: "POST", body: formData });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return res.json() as Promise<DocumentAnalysisResponse>;
}

// ─── §6.4 HITL Review Queue ───────────────────────────────────────────────────

export interface HITLItem {
  review_id: string;
  session_id: string;
  submitted_at: string;
  user_type: string;
  country: string;
  pipeline_trace: PipelineTrace;
  draft_response: string;
}

export interface HITLQueueResponse {
  pending_count: number;
  items: HITLItem[];
}

export interface ApproveRequest {
  review_id: string;
  approved_response: string;
  reviewer_note?: string | null;
}

export interface RejectRequest {
  review_id: string;
  rejection_reason: string;
}

export async function getHITLQueue(): Promise<HITLQueueResponse> {
  const { data } = await request<HITLQueueResponse>("/hitl/queue");
  return data;
}

export async function postHITLApprove(
  body: ApproveRequest
): Promise<{ status: string }> {
  const { data } = await request<{ status: string }>("/hitl/approve", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data;
}

export async function postHITLReject(
  body: RejectRequest
): Promise<{ status: string }> {
  const { data } = await request<{ status: string }>("/hitl/reject", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data;
}

// ─── §6.5 Analytics ───────────────────────────────────────────────────────────

export interface ProactiveRecommendation {
  category: "dietary" | "icd10_cluster" | "medication_conflict";
  title: string;
  description: string;
  affected_groups: string[];
  magnitude: number;
}

export interface AnalyticsDashboardResponse {
  total_queries: number;
  escalation_rate: number;
  queries_by_language: Record<string, number>;
  queries_by_user_type: Record<string, number>;
  top_medication_flags: Array<{ medication: string; status: string; count: number }>;
  avg_pipeline_stages_completed: number;
  jurisdiction_breakdown: Record<string, number>;
  proactive_recommendations: ProactiveRecommendation[];
}

export async function getAnalyticsDashboard(params?: {
  date_from?: string;
  date_to?: string;
  jurisdiction?: string;
}): Promise<AnalyticsDashboardResponse> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  if (params?.jurisdiction) qs.set("jurisdiction", params.jurisdiction);
  const query = qs.toString() ? `?${qs}` : "";
  const { data } = await request<AnalyticsDashboardResponse>(
    `/analytics/dashboard${query}`
  );
  return data;
}

// ─── §6.0 Health ──────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await request<HealthResponse>("/health");
  return data;
}

// ─── §6.6 Registry Sync & Changelog (Teammate 2 stubs) ───────────────────────

export interface BulletinRequest {
  medication_id: string;
  source: string;
  updates: Record<string, unknown>;
}

export interface BulletinResponse {
  sync_version: string;
  timestamp: string;
  source: string;
  changes: Array<{
    medication_id: string;
    field: string;
    old_value: unknown;
    new_value: unknown;
  }>;
}

export interface ChangelogResponse {
  total_entries: number;
  entries: BulletinResponse[];
}

export async function postRegistrySync(
  body: BulletinRequest
): Promise<BulletinResponse> {
  const { data } = await request<BulletinResponse>("/registry/sync", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return data;
}

export async function getRegistryChangelog(
  limit?: number
): Promise<ChangelogResponse> {
  const qs = limit ? `?limit=${limit}` : "";
  const { data } = await request<ChangelogResponse>(`/registry/changelog${qs}`);
  return data;
}
