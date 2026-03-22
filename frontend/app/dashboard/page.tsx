"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDashboardOverview } from "@/lib/api";

export default function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: fetchDashboardOverview
  });

  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading dashboard…</p>;
  }

  if (isError || !data) {
    return <p className="text-sm text-red-600">Could not load dashboard. Please try again.</p>;
  }

  const timeSavedHours = data.documents_this_month * 2.5;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <section className="grid gap-4 md:grid-cols-4">
        <Card title="Total clients" value={data.total_clients.toString()} />
        <Card title="Pending review" value={data.pending_documents.toString()} emphasis />
        <Card title="Processed today" value={data.processed_today.toString()} />
        <Card
          title="Time saved this month"
          value={`${timeSavedHours.toFixed(1)} hrs`}
          description="Assuming 2.5 hrs per client"
        />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium text-slate-700">Recent activity</h2>
        {data.recent_activity.length === 0 ? (
          <p className="text-sm text-slate-500">No recent activity yet.</p>
        ) : (
          <ul className="divide-y divide-slate-200 rounded-md border bg-white">
            {data.recent_activity.map((item) => (
              <li key={item.id} className="flex items-center justify-between px-4 py-3">
                <p className="text-sm text-slate-800">{item.message}</p>
                <p className="text-xs text-slate-500">
                  {new Date(item.created_at).toLocaleString(undefined, {
                    dateStyle: "short",
                    timeStyle: "short"
                  })}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Card({
  title,
  value,
  description,
  emphasis
}: {
  title: string;
  value: string;
  description?: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border bg-white px-4 py-3 shadow-sm ${
        emphasis ? "border-amber-400" : "border-slate-200"
      }`}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{title}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      {description ? <p className="mt-1 text-xs text-slate-500">{description}</p> : null}
    </div>
  );
}

