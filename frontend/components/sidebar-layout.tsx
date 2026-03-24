"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/clients", label: "Clients" },
  { href: "/upload", label: "Upload Portal" },
  { href: "/settings", label: "Settings" }
];

export function SidebarLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 flex-col border-r bg-white px-4 py-6 md:flex">
        <div className="mb-8">
          <div className="text-xl font-semibold text-primary">SmartITR</div>
          <p className="text-xs text-slate-500">CA document dashboard</p>
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-md px-3 py-2 text-sm ${
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}

