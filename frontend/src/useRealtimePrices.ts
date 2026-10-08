import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { ApiRequestError } from "./auth";
import { acceptPrices, decodePrices, fetchPrices, priceQueryKey, type PricesView } from "./realtimePrices";
export type Delivery = "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "AWAITING_SNAPSHOT";
export function useRealtimePrices() {
    const client = useQueryClient();
    const [delivery, setDelivery] = useState<Delivery>("CONNECTING");
    const query = useQuery<PricesView>({ queryKey: priceQueryKey, enabled: false, queryFn: ({ signal }) => fetchPrices(signal), structuralSharing: (old, next) => acceptPrices(old as PricesView | undefined, next as PricesView) });
    useEffect(() => {
        let receivedSnapshot = false;
        let active = true, epoch = 0, attempt = 0, socket: WebSocket | undefined;
        let retry: number | undefined, watchdog: number | undefined;
        const controller = new AbortController();
        const clearTimers = () => { window.clearTimeout(retry); window.clearTimeout(watchdog); };
        const invalidate = () => { epoch++; clearTimers(); socket?.close(); socket = undefined; };
        const fail = (state: Delivery = "DISCONNECTED") => {
            if (!active)
                return;
            invalidate();
            setDelivery(state);
            const delay = Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5)) * (0.5 + Math.random() * 0.5);
            retry = window.setTimeout(connect, delay);
        };
        const arm = (current: number) => { window.clearTimeout(watchdog); watchdog = window.setTimeout(() => { if (active && current === epoch)
            fail(); }, 3000); };
        function connect() {
            if (!active)
                return;
            if (window.navigator.onLine === false || document.visibilityState === "hidden") {
                setDelivery("DISCONNECTED");
                return;
            }
            const current = ++epoch;
            setDelivery("AWAITING_SNAPSHOT");
            try {
                const url = new URL("/api/market-data/prices/stream", window.location.href);
                url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
                socket = new WebSocket(url);
                socket.onopen = () => { if (active && current === epoch)
                    arm(current); };
                socket.onmessage = (event) => {
                    if (!active || current !== epoch)
                        return;
                    try {
                        if (typeof event.data !== "string" || event.data.length > 65536)
                            throw new Error();
                        const next = decodePrices(JSON.parse(event.data));
                        const old = client.getQueryData<PricesView>(priceQueryKey);
                        const accepted = acceptPrices(old, next);
                        arm(current);
                        if (accepted === old)
                            return;
                        receivedSnapshot = true;
                        client.setQueryData(priceQueryKey, accepted);
                        setDelivery("CONNECTED");
                        attempt = 0;
                    }
                    catch {
                        fail();
                    }
                };
                socket.onerror = () => { if (active && current === epoch)
                    fail(); };
                socket.onclose = (event) => {
                    if (!active || current !== epoch)
                        return;
                    if (event.code === 4401) {
                        active = false;
                        invalidate();
                        controller.abort();
                        client.getQueryCache().find({ queryKey: priceQueryKey })?.setState({ error: new ApiRequestError("PRICE_SESSION_EXPIRED", 401), status: "error" });
                    }
                    else
                        fail();
                };
                arm(current);
            }
            catch {
                fail();
            }
        }
        void client.fetchQuery({ queryKey: priceQueryKey, queryFn: async () => {
                const next = await fetchPrices(controller.signal);
                if (!active)
                    throw new ApiRequestError("PRICE_DELIVERY_FAILED", 0);
                return acceptPrices(client.getQueryData<PricesView>(priceQueryKey), next);
            }, retry: false }).catch(() => { if (active && !receivedSnapshot)
            setDelivery("DISCONNECTED"); });
        const offline = () => fail();
        const resume = () => fail("AWAITING_SNAPSHOT");
        const visibility = () => resume();
        window.addEventListener("offline", offline);
        window.addEventListener("online", resume);
        window.addEventListener("pageshow", resume);
        document.addEventListener("visibilitychange", visibility);
        document.addEventListener("freeze", resume);
        document.addEventListener("resume", resume);
        connect();
        return () => { active = false; invalidate(); controller.abort(); window.removeEventListener("offline", offline); window.removeEventListener("online", resume); window.removeEventListener("pageshow", resume); document.removeEventListener("visibilitychange", visibility); document.removeEventListener("freeze", resume); document.removeEventListener("resume", resume); };
    }, [client]);
    return { view: query.data, delivery };
}
