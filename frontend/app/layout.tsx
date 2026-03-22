import type { Metadata } from "next";
import "./globals.css";
import { ReactNode } from "react";
import { QueryClientProvider } from "@/components/query-client-provider";
import { SidebarLayout } from "@/components/sidebar-layout";
import { AuthGuard } from "@/components/auth-guard";

export const metadata: Metadata = {
  title: "SmartITR CA Dashboard",
  description: "Document intelligence for CA firms"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <QueryClientProvider>
          <AuthGuard>
            <SidebarLayout>{children}</SidebarLayout>
          </AuthGuard>
        </QueryClientProvider>
      </body>
    </html>
  );
}
