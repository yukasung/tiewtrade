import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiRequestError, type Me } from "./auth";
/** One cache per mounted authenticated identity. No module-global or nested panel clients. */
export function AccountSession({
  identity,
  children,
  onExpired,
}: {
  identity: Me;
  children: ReactNode;
  onExpired?: () => void;
}) {
  return (
    <Session key={identity.user_id} onExpired={onExpired}>
      {children}
    </Session>
  );
}
function Session({
  children,
  onExpired,
}: {
  children: ReactNode;
  onExpired: (() => void) | undefined;
}) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: false, gcTime: 0 },
          mutations: { retry: false, gcTime: 0, networkMode: "always" },
        },
      }),
  );
  const expiryHandler = useRef(onExpired);
  expiryHandler.current = onExpired;
  useEffect(() => {
    let expired = false;
    const check = (error: unknown) => {
      if (
        !expired &&
        error instanceof ApiRequestError &&
        error.status === 401
      ) {
        expired = true;
        void client.cancelQueries();
        client.clear();
        expiryHandler.current?.();
      }
    };
    const queries = client
      .getQueryCache()
      .subscribe((event) => check(event.query.state.error));
    const mutations = client.getMutationCache().subscribe((event) => {
      if ("mutation" in event) check(event.mutation?.state.error);
    });
    return () => {
      queries();
      mutations();
      void client.cancelQueries();
      client.clear();
    };
  }, [client]);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
