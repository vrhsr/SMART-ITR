"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await api.post("/api/auth/login", { email, password });
      const { access_token, full_name, role } = res.data;

      localStorage.setItem("smartitr_token", access_token);
      localStorage.setItem("smartitr_user", JSON.stringify({ full_name, role, email }));

      router.push("/dashboard");
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Login failed. Please try again.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1 className="login-title">SmartITR</h1>
          <p className="login-subtitle">CA Document Intelligence Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="login-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@smartitr.com"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          <button type="submit" disabled={loading} className="login-btn">
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <p className="login-footer">
          Secured with 256-bit encryption · DPDP Act 2023 compliant
        </p>
      </div>

      <style jsx>{`
        .login-page {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
          padding: 1rem;
        }
        .login-card {
          width: 100%;
          max-width: 420px;
          background: rgba(255, 255, 255, 0.05);
          backdrop-filter: blur(24px);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 20px;
          padding: 2.5rem 2rem;
          box-shadow: 0 25px 50px rgba(0, 0, 0, 0.4);
        }
        .login-header {
          text-align: center;
          margin-bottom: 2rem;
        }
        .login-title {
          font-size: 2rem;
          font-weight: 700;
          background: linear-gradient(135deg, #818cf8, #6366f1, #4f46e5);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          margin: 0 0 0.25rem;
        }
        .login-subtitle {
          color: #94a3b8;
          font-size: 0.875rem;
          margin: 0;
        }
        .login-form {
          display: flex;
          flex-direction: column;
          gap: 1.25rem;
        }
        .login-error {
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.3);
          color: #fca5a5;
          padding: 0.75rem 1rem;
          border-radius: 10px;
          font-size: 0.875rem;
        }
        .form-group {
          display: flex;
          flex-direction: column;
          gap: 0.375rem;
        }
        .form-group label {
          color: #cbd5e1;
          font-size: 0.8125rem;
          font-weight: 500;
        }
        .form-group input {
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 10px;
          padding: 0.75rem 1rem;
          color: #f1f5f9;
          font-size: 0.9375rem;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .form-group input::placeholder {
          color: #64748b;
        }
        .form-group input:focus {
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
        }
        .login-btn {
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: white;
          border: none;
          border-radius: 10px;
          padding: 0.8rem;
          font-size: 0.9375rem;
          font-weight: 600;
          cursor: pointer;
          transition: transform 0.15s, box-shadow 0.2s;
          margin-top: 0.5rem;
        }
        .login-btn:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 8px 25px rgba(99, 102, 241, 0.35);
        }
        .login-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .login-footer {
          text-align: center;
          color: #475569;
          font-size: 0.75rem;
          margin-top: 1.5rem;
        }
      `}</style>
    </div>
  );
}
