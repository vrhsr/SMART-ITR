import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
});

// Attach JWT from localStorage to every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("smartitr_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// On 401 responses, redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("smartitr_token");
      localStorage.removeItem("smartitr_user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface DashboardOverview {
  total_clients: number;
  pending_documents: number;
  processed_today: number;
  documents_this_month: number;
  recent_activity: {
    id: string;
    message: string;
    created_at: string;
  }[];
}

export interface ClientSummary {
  id: string;
  full_name: string;
  pan_last4: string;
  last_activity: string | null;
  document_count: number;
  status: string;
}

export interface ClientDetail {
  id: string;
  full_name: string;
  pan_last4: string;
  created_at: string;
  documents: DocumentDetail[];
}

export interface DocumentDetail {
  id: string;
  filename: string;
  type: string;
  status: string;
  created_at: string;
  extracted_data: Record<string, unknown> | null;
  tax_computation: TaxComputation | null;
}

export interface TaxComputation {
  old_regime_tax_paise: number;
  new_regime_tax_paise: number;
  recommended_regime: "old" | "new" | "unknown";
  savings_paise: number;
  income_data_used?: Record<string, unknown>;
}

export interface ExportUrl {
  url: string;
}

export interface BillingStatus {
  plan: string | null;
  status: string;
  next_billing_date: string | null;
  amount: number;
}

export interface FirmBranding {
  logo_url: string | null;
  brand_color: string | null;
  firm_name: string;
}

// ---------------------------------------------------------------------------
// API functions — CA dashboard
// ---------------------------------------------------------------------------

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
  const res = await api.get("/api/ca/dashboard");
  return res.data;
}

export async function fetchClients(params?: {
  search?: string;
}): Promise<ClientSummary[]> {
  const res = await api.get("/api/ca/clients", { params });
  return res.data;
}

export async function fetchClientDetail(clientId: string): Promise<ClientDetail> {
  const res = await api.get(`/api/ca/clients/${clientId}`);
  return res.data;
}

export async function overrideDocumentField(
  documentId: string,
  fieldPath: string,
  newValue: unknown
): Promise<{ status: string }> {
  const res = await api.post(`/api/ca/documents/${documentId}/override`, {
    field_path: fieldPath,
    new_value: newValue,
  });
  return res.data;
}

export async function approveDocument(
  documentId: string
): Promise<{ status: string }> {
  const res = await api.post(`/api/ca/documents/${documentId}/approve`);
  return res.data;
}

export async function fetchExportUrl(
  documentId: string,
  artifactType: "excel" | "itdx_json" | "client_report_pdf"
): Promise<ExportUrl> {
  const res = await api.get(
    `/api/ca/documents/${documentId}/export/${artifactType}`
  );
  return res.data;
}

export async function fetchBillingStatus(): Promise<BillingStatus> {
  const res = await api.get("/api/billing/status");
  return res.data;
}

// ---------------------------------------------------------------------------
// API functions — client upload portal (white-label, unauthenticated for branding)
// ---------------------------------------------------------------------------

export async function fetchFirmBranding(firmId: string): Promise<FirmBranding> {
  const res = await api.get(`/api/public/firm-branding/${firmId}`);
  return res.data;
}

export async function requestUploadUrl(payload: {
  client_id: string;
  filename: string;
  content_type: string;
}): Promise<{ upload_url: string; document_id: string; expires_at: string }> {
  const res = await api.post("/api/documents/upload-url", payload);
  return res.data;
}

export async function confirmUpload(
  documentId: string
): Promise<{ status: string; document_id: string }> {
  const res = await api.post("/api/documents/confirm", {
    document_id: documentId,
  });
  return res.data;
}

export async function giveConsent(
  consentTextVersion: string
): Promise<{ status: string; given_at: string }> {
  const res = await api.post("/api/client/consent", {
    consent_text_version: consentTextVersion,
  });
  return res.data;
}

export default api;
