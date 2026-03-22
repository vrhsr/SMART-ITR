"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { fetchClients, ClientSummary } from "@/lib/api";

export default function ClientsPage() {
  const [search, setSearch] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["clients", search],
    queryFn: () => fetchClients({ search: search || undefined }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Clients</h1>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          placeholder="Search by name or PAN…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-xs rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading clients…</p>
      ) : isError ? (
        <p className="text-sm text-red-600">Could not load clients. Please try again.</p>
      ) : !data || data.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
          <p className="text-slate-500">No clients found yet.</p>
          <p className="mt-1 text-xs text-slate-400">Clients will appear here after documents are uploaded.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">PAN (last 4)</th>
                <th className="px-4 py-3">Documents</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Last Activity</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((client: ClientSummary) => (
                <tr key={client.id} className="transition-colors hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">{client.full_name}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">
                    ••••{client.pan_last4 || "—"}
                  </td>
                  <td className="px-4 py-3">{client.document_count}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={client.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {client.last_activity
                      ? new Date(client.last_activity).toLocaleString(undefined, {
                          dateStyle: "short",
                          timeStyle: "short",
                        })
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      href={`/clients/${client.id}`}
                      className="rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 transition-colors hover:bg-indigo-100"
                    >
                      Review →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; className: string }> = {
    "Pending Review": { label: "Pending", className: "bg-amber-100 text-amber-700" },
    "Action Required": { label: "Action Required", className: "bg-rose-100 text-rose-700" },
    approved: { label: "Approved", className: "bg-emerald-100 text-emerald-700" },
  };

  const cfg = map[status] ?? { label: status, className: "bg-slate-100 text-slate-700" };

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  );
}
