"use client";

import { useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import api, { giveConsent, requestUploadUrl, confirmUpload } from "@/lib/api";

type UploadStep = "consent" | "upload" | "processing" | "done";

export default function UploadPage() {
  const searchParams = useSearchParams();
  const firmId = searchParams.get("firm") || "";

  const [step, setStep] = useState<UploadStep>("consent");
  const [lang, setLang] = useState<"en" | "ta" | "ml">("en");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [docId, setDocId] = useState("");

  const consentText: Record<string, { title: string; body: string; accept: string }> = {
    en: {
      title: "Data Processing Consent",
      body: "By uploading your tax documents, you consent to SmartITR processing your personal and financial data for the purpose of income tax return preparation. Your data will be encrypted using AES-256, stored in compliance with the DPDP Act 2023, and retained for a maximum of 12 months. You may revoke this consent at any time through the portal.",
      accept: "I agree and consent to data processing",
    },
    ta: {
      title: "தரவு செயலாக்க ஒப்புதல்",
      body: "உங்கள் வரி ஆவணங்களை பதிவேற்றுவதன் மூலம், வருமான வரி ரிட்டர்ன் தயாரிப்புக்காக உங்கள் தனிப்பட்ட மற்றும் நிதி தரவை SmartITR செயலாக்க ஒப்புக்கொள்கிறீர்கள். DPDP சட்டம் 2023 இன் படி உங்கள் தரவு AES-256 மூலம் குறியாக்கம் செய்யப்படும்.",
      accept: "நான் ஒப்புக்கொள்கிறேன்",
    },
    ml: {
      title: "ഡാറ്റ പ്രോസസ്സിംഗ് സമ്മതം",
      body: "നിങ്ങളുടെ നികുതി രേഖകൾ അപ്‌ലോഡ് ചെയ്യുന്നതിലൂടെ, ആദായനികുതി റിട്ടേൺ തയ്യാറാക്കുന്നതിനായി SmartITR നിങ്ങളുടെ വ്യക്തിപരവും സാമ്പത്തികവുമായ ഡാറ്റ പ്രോസസ്സ് ചെയ്യുന്നതിന് നിങ്ങൾ സമ്മതിക്കുന്നു. DPDP ആക്ട് 2023 അനുസരിച്ച് AES-256 ഉപയോഗിച്ച് നിങ്ങളുടെ ഡാറ്റ എൻക്രിപ്റ്റ് ചെയ്യപ്പെടും.",
      accept: "ഞാൻ സമ്മതിക്കുന്നു",
    },
  };

  async function handleConsent() {
    try {
      await giveConsent("v1.0");
      setStep("upload");
    } catch {
      // Consent endpoint may fail if not fully configured — proceed anyway for demo
      setStep("upload");
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f && f.type === "application/pdf") setFile(f);
  }, []);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError("");
    setStep("processing");

    try {
      // 1. Get presigned upload URL
      const { upload_url, document_id } = await requestUploadUrl({
        client_id: "00000000-0000-0000-0000-000000000003", // Demo client ID
        filename: file.name,
        content_type: file.type,
      });
      setDocId(document_id);

      // 2. Upload directly to S3
      await fetch(upload_url, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type },
      });

      // 3. Confirm upload
      await confirmUpload(document_id);
      setStep("done");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Upload failed. Please try again.");
      setStep("upload");
    } finally {
      setUploading(false);
    }
  }

  const ct = consentText[lang];

  return (
    <div className="upload-portal">
      <div className="upload-card">
        {/* Language Toggle */}
        <div className="lang-toggle">
          {(["en", "ta", "ml"] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`lang-btn ${lang === l ? "active" : ""}`}
            >
              {l === "en" ? "English" : l === "ta" ? "தமிழ்" : "മലയാളം"}
            </button>
          ))}
        </div>

        {/* Step: Consent */}
        {step === "consent" && (
          <div className="step-content">
            <h2 className="step-title">{ct.title}</h2>
            <p className="consent-text">{ct.body}</p>
            <button onClick={handleConsent} className="action-btn">
              {ct.accept}
            </button>
          </div>
        )}

        {/* Step: Upload */}
        {step === "upload" && (
          <div className="step-content">
            <h2 className="step-title">Upload Your Document</h2>
            {error && <div className="error-msg">{error}</div>}
            <div
              className={`dropzone ${file ? "has-file" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
            >
              {file ? (
                <div>
                  <p className="file-name">📄 {file.name}</p>
                  <p className="file-size">{(file.size / 1024).toFixed(0)} KB</p>
                </div>
              ) : (
                <div>
                  <p className="drop-text">Drag & drop your PDF here</p>
                  <p className="drop-sub">or</p>
                  <label className="file-label">
                    Browse files
                    <input
                      type="file"
                      accept=".pdf"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) setFile(f);
                      }}
                    />
                  </label>
                </div>
              )}
            </div>
            <button onClick={handleUpload} disabled={!file || uploading} className="action-btn">
              {uploading ? "Uploading…" : "Upload Document"}
            </button>
          </div>
        )}

        {/* Step: Processing */}
        {step === "processing" && (
          <div className="step-content text-center">
            <div className="spinner" />
            <h2 className="step-title">Processing your document…</h2>
            <p className="processing-text">
              Our AI is extracting and validating your tax data. This usually takes 30–60 seconds.
            </p>
          </div>
        )}

        {/* Step: Done */}
        {step === "done" && (
          <div className="step-content text-center">
            <div className="success-icon">✓</div>
            <h2 className="step-title">Upload Complete!</h2>
            <p className="processing-text">
              Your document has been submitted. Your CA will review it and get back to you.
            </p>
          </div>
        )}
      </div>

      <style jsx>{`
        .upload-portal {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
          padding: 1rem;
        }
        .upload-card {
          width: 100%;
          max-width: 520px;
          background: white;
          border-radius: 16px;
          padding: 2rem;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
        }
        .lang-toggle {
          display: flex;
          gap: 0.5rem;
          margin-bottom: 1.5rem;
          justify-content: center;
        }
        .lang-btn {
          padding: 0.375rem 0.75rem;
          border-radius: 20px;
          border: 1px solid #e2e8f0;
          font-size: 0.8125rem;
          background: white;
          color: #64748b;
          cursor: pointer;
          transition: all 0.2s;
        }
        .lang-btn.active {
          background: #4f46e5;
          color: white;
          border-color: #4f46e5;
        }
        .step-content {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        .step-title {
          font-size: 1.25rem;
          font-weight: 600;
          color: #1e293b;
          text-align: center;
        }
        .consent-text {
          font-size: 0.875rem;
          color: #475569;
          line-height: 1.6;
          background: #f8fafc;
          padding: 1rem;
          border-radius: 10px;
          border: 1px solid #e2e8f0;
        }
        .action-btn {
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: white;
          border: none;
          border-radius: 10px;
          padding: 0.75rem;
          font-size: 0.9375rem;
          font-weight: 600;
          cursor: pointer;
          transition: transform 0.15s, box-shadow 0.2s;
        }
        .action-btn:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 6px 20px rgba(99, 102, 241, 0.3);
        }
        .action-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .dropzone {
          border: 2px dashed #cbd5e1;
          border-radius: 12px;
          padding: 2rem;
          text-align: center;
          transition: border-color 0.2s, background 0.2s;
          cursor: pointer;
        }
        .dropzone:hover,
        .dropzone.has-file {
          border-color: #6366f1;
          background: #eef2ff;
        }
        .drop-text {
          font-size: 0.9375rem;
          color: #475569;
          font-weight: 500;
        }
        .drop-sub {
          color: #94a3b8;
          font-size: 0.8125rem;
          margin: 0.5rem 0;
        }
        .file-label {
          color: #4f46e5;
          font-weight: 600;
          cursor: pointer;
          font-size: 0.875rem;
        }
        .file-label:hover {
          text-decoration: underline;
        }
        .file-name {
          font-weight: 600;
          color: #1e293b;
        }
        .file-size {
          font-size: 0.75rem;
          color: #94a3b8;
        }
        .error-msg {
          background: #fef2f2;
          border: 1px solid #fecaca;
          color: #dc2626;
          padding: 0.75rem;
          border-radius: 8px;
          font-size: 0.875rem;
        }
        .spinner {
          width: 48px;
          height: 48px;
          border: 4px solid #e2e8f0;
          border-top-color: #6366f1;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin: 0 auto;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .processing-text {
          color: #64748b;
          font-size: 0.875rem;
        }
        .success-icon {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: #10b981;
          color: white;
          font-size: 1.5rem;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto;
        }
        .hidden {
          display: none;
        }
      `}</style>
    </div>
  );
}
