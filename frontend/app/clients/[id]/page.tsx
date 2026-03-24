"use client";

import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchClientDetail,
  overrideDocumentField,
  approveDocument,
  fetchExportUrl,
  DocumentDetail,
} from "@/lib/api";

export default function ClientDetailPage() {
  const params = useParams();
  const clientId = params.id as string;
  const queryClient = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["client-detail", clientId],
    queryFn: () => fetchClientDetail(clientId),
  });

  const approveMutation = useMutation({
    mutationFn: (docId: string) => approveDocument(docId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["client-detail", clientId] }),
  });

  if (isLoading) return <p className="text-sm text-slate-500">Loading client details…</p>;
  if (isError || !data) return <p className="text-sm text-red-600">Could not load client details.</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{data.full_name}</h1>
        <p className="text-sm text-slate-500">
          PAN: ••••{data.pan_last4 || "—"} · Added{" "}
          {new Date(data.created_at).toLocaleDateString()}
        </p>
      </div>

      {data.documents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-slate-500">No documents uploaded yet.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.documents.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              onApprove={() => approveMutation.mutate(doc.id)}
              isApproving={approveMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function DocumentCard({
  doc,
  onApprove,
  isApproving,
}: {
  doc: DocumentDetail;
  onApprove: () => void;
  isApproving: boolean;
}) {
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const queryClient = useQueryClient();

  const overrideMutation = useMutation({
    mutationFn: ({ field, value }: { field: string; value: string }) =>
      overrideDocumentField(doc.id, field, value),
    onSuccess: () => {
      setEditingField(null);
      queryClient.invalidateQueries({ queryKey: ["client-detail"] });
    },
  });

  async function handleExport(type: "excel" | "itdx_json" | "client_report_pdf") {
    try {
      const { url } = await fetchExportUrl(doc.id, type);
      window.open(url, "_blank");
    } catch {
      alert(`Export not available yet for type: ${type}`);
    }
  }

  const isApproved = doc.status === "approved";
  const extracted = doc.extracted_data || {};
  const fields = Object.entries(extracted).filter(([k]) => !k.startsWith("_"));

  return (
    <div className="rounded-lg border bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div>
          <p className="font-medium text-slate-800">{doc.filename}</p>
          <p className="text-xs text-slate-500">
            {doc.type} · {doc.status} · {new Date(doc.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!isApproved && (
            <button
              onClick={onApprove}
              disabled={isApproving}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
            >
              {isApproving ? "Approving…" : "✓ Approve"}
            </button>
          )}
          <button
            onClick={() => handleExport("excel")}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            📊 Excel
          </button>
          <button
            onClick={() => handleExport("client_report_pdf")}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            📄 PDF
          </button>
          <button
            onClick={() => handleExport("itdx_json")}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
          >
            📑 ITD JSON
          </button>
        </div>
      </div>

      {/* Extracted Fields */}
      {fields.length > 0 && (
        <div className="px-4 py-3">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Extracted Data
          </h3>
          <div className="grid gap-2 md:grid-cols-2">
            {fields.map(([key, value]) => {
              const confidence = typeof (extracted as any)[`_confidence_${key}`] === "number"
                ? (extracted as any)[`_confidence_${key}`]
                : null;
              const isLowConfidence = confidence !== null && confidence < 0.85;

              return (
                <div
                  key={key}
                  className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm ${
                    isLowConfidence
                      ? "border-amber-300 bg-amber-50"
                      : "border-slate-200 bg-slate-50"
                  }`}
                >
                  <div className="flex-1">
                    <span className="text-xs font-medium text-slate-500">{key}</span>
                    {editingField === key ? (
                      <div className="mt-1 flex gap-1">
                        <input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="w-full rounded border border-indigo-300 px-2 py-1 text-xs"
                          autoFocus
                        />
                        <button
                          onClick={() =>
                            overrideMutation.mutate({ field: key, value: editValue })
                          }
                          className="rounded bg-indigo-600 px-2 py-1 text-xs text-white"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingField(null)}
                          className="rounded border px-2 py-1 text-xs"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <p className="mt-0.5 text-slate-800">
                        {typeof value === "object" ? JSON.stringify(value) : String(value)}
                      </p>
                    )}
                  </div>
                  {!isApproved && editingField !== key && (
                    <button
                      onClick={() => {
                        setEditingField(key);
                        setEditValue(String(value));
                      }}
                      className="ml-2 text-xs text-indigo-600 hover:underline"
                    >
                      Edit
                    </button>
                  )}
                  {isLowConfidence && (
                    <span className="ml-2 text-xs text-amber-600" title={`Confidence: ${(confidence! * 100).toFixed(0)}%`}>
                      ⚠ Low
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tax Computation */}
      {doc.tax_computation && (
        <div className="border-t px-4 py-3">
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
            Tax Computation
          </h3>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-md border bg-slate-50 px-3 py-2">
              <p className="text-xs text-slate-500">Old Regime Tax</p>
              <p className="text-lg font-semibold">
                ₹{(doc.tax_computation.old_regime_tax_paise / 100).toLocaleString("en-IN")}
              </p>
            </div>
            <div className="rounded-md border bg-slate-50 px-3 py-2">
              <p className="text-xs text-slate-500">New Regime Tax</p>
              <p className="text-lg font-semibold">
                ₹{(doc.tax_computation.new_regime_tax_paise / 100).toLocaleString("en-IN")}
              </p>
            </div>
            <div className={`rounded-md border px-3 py-2 ${
              doc.tax_computation.recommended_regime === "new"
                ? "border-emerald-300 bg-emerald-50"
                : "border-blue-300 bg-blue-50"
            }`}>
              <p className="text-xs text-slate-500">Recommended</p>
              <p className="text-lg font-semibold capitalize">
                {doc.tax_computation.recommended_regime} Regime
              </p>
              <p className="text-xs text-slate-500">
                Save ₹{(doc.tax_computation.savings_paise / 100).toLocaleString("en-IN")}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
