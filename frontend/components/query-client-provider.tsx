"use client";

import { QueryClient, QueryClientProvider as RQProvider } from "@tanstack/react-query";
import { ReactNode, useState } from "react";

export function QueryClientProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false
          }
        }
      })
  );

  return <RQProvider client={client}>{children}</RQProvider>;
}

