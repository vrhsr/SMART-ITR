"use client";

import { useEffect, useState, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";

const PUBLIC_PATHS = ["/login", "/upload"];

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const isPublic = PUBLIC_PATHS.some(
      (p) => pathname === p || pathname.startsWith(p + "/")
    );

    if (!isPublic) {
      const token = localStorage.getItem("smartitr_token");
      if (!token) {
        router.replace("/login");
        return;
      }
    }
    setChecked(true);
  }, [pathname, router]);

  if (!checked) {
    return null; // Prevent flash of protected content
  }

  return <>{children}</>;
}
