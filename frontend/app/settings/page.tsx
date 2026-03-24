"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchBillingStatus } from "@/lib/api";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const [user, setUser] = useState<{ full_name: string; role: string; email: string } | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem("smartitr_user");
    if (raw) setUser(JSON.parse(raw));
  }, []);

  const { data: billing } = useQuery({
    queryKey: ["billing-status"],
    queryFn: fetchBillingStatus,
    retry: false,
  });

  function handleLogout() {
    localStorage.removeItem("smartitr_token");
    localStorage.removeItem("smartitr_user");
    window.location.href = "/login";
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      {/* Profile Card */}
      <section className="rounded-lg border bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Account
        </h2>
        {user && (
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Name</span>
              <span className="font-medium">{user.full_name || "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Email</span>
              <span className="font-medium">{user.email}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Role</span>
              <span className="inline-flex rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium capitalize text-indigo-700">
                {user.role}
              </span>
            </div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-2 text-xs font-medium text-red-700 transition-colors hover:bg-red-100"
        >
          Sign Out
        </button>
      </section>

      {/* Branding */}
      <section className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3 rounded-lg border bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Branding
          </h2>
          <div className="space-y-3 text-sm">
            <div>
              <label className="block text-xs font-medium text-slate-600">Firm Logo</label>
              <input type="file" accept="image/*" className="mt-1 text-xs" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600">Brand Color</label>
              <input
                type="color"
                defaultValue="#4f46e5"
                className="mt-1 h-8 w-16 cursor-pointer rounded border border-slate-300"
              />
            </div>
          </div>
        </div>

        <div className="space-y-3 rounded-lg border bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Data Retention
          </h2>
          <p className="text-xs text-slate-500">
            Choose how long SmartITR keeps structured data before automatic deletion (DPDP compliance).
          </p>
          <select className="mt-2 rounded-md border border-slate-300 px-3 py-2 text-sm">
            <option value="6">6 months</option>
            <option value="12" selected>12 months</option>
            <option value="24">24 months</option>
          </select>
        </div>
      </section>

      {/* Billing */}
      <section className="rounded-lg border bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          Billing
        </h2>
        <p className="text-xs text-slate-500">
          Subscription is handled via Razorpay.
        </p>
        {billing ? (
          <div className="mt-3 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Plan</span>
              <span className="font-medium">{billing.plan || "Free"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Status</span>
              <span className="font-medium capitalize">{billing.status}</span>
            </div>
            {billing.next_billing_date && (
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Next Billing</span>
                <span className="font-medium">
                  {new Date(billing.next_billing_date).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>
        ) : (
          <p className="mt-2 text-sm text-slate-600">No billing information available.</p>
        )}
        <button className="mt-4 rounded-md border border-slate-300 px-4 py-2 text-xs font-medium transition-colors hover:bg-slate-50">
          Manage Subscription
        </button>
      </section>
    </div>
  );
}
