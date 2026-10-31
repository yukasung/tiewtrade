import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { MarketValue } from "./components/MarketValue";
import { OrderStatus } from "./components/OrderStatus";
import { Button } from "./components/ui/Button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/Table";
import { Tabs } from "./components/ui/Tabs";
import { manualOrderText as t } from "./manualOrderMessages";
import { fetchOrders, manualKey, orderTerminal, type PaperOrder } from "./manualOrders";

export function PaperOrderList({ owner, episode, visible, disabled, onCancel }: {
  owner: string; episode: string; visible: boolean; disabled: boolean; onCancel: (value: PaperOrder) => void;
}) {
  const [view, setView] = useState<"OPEN" | "HISTORY">("OPEN");
  const query = useInfiniteQuery({ queryKey: [...manualKey(owner), episode, "orders", "all"],
    initialPageParam: null as string | null, queryFn: ({ pageParam, signal }) => fetchOrders(episode, pageParam, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: visible, refetchInterval: visible ? 5000 : false, refetchIntervalInBackground: false,
  });
  const rows = query.data?.pages.flatMap(page => page.orders).filter(row => row.mode === "PAPER" && row.episode_id === episode) ?? [];
  const visibleRows = rows.filter(row => view === "OPEN" ? !orderTerminal(row.status) : orderTerminal(row.status));
  return <section className="paper-order-panel" aria-labelledby="manual-orders-heading">
    <h2 id="manual-orders-heading" className="sr-only">{t("orders")}</h2>
    <header className="paper-order-toolbar">
      <Tabs id="manual-orders-view" controls="manual-orders-table" label={t("orders")}
        items={[{ id: "OPEN", label: t("openOrders") }, { id: "HISTORY", label: t("orderHistory") }]}
        active={view} onChange={setView}/>
    </header>
    {query.isError && <p role="alert">{t("loadError")}</p>}
    <div id="manual-orders-table" role="tabpanel" className="paper-order-table"><Table className="whitespace-nowrap"><TableHeader className="border-b border-gray-100 dark:border-white/5"><TableRow>
      {["pair", "side", "kind", "status", "filled", "remaining", "reserved", "cancel"].map(name => <TableHead key={name} scope="col" className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">{t(name)}</TableHead>)}
    </TableRow></TableHeader><TableBody className="divide-y divide-gray-100 dark:divide-white/5">
      {visibleRows.map(row => <TableRow key={row.order_id}>
        <TableCell className="px-5 py-4 text-start text-sm">{row.base}/{row.quote}</TableCell><TableCell className="px-5 py-4 text-start text-sm">{t(row.side)}</TableCell><TableCell className="px-5 py-4 text-start text-sm">{t(row.kind)}</TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><OrderStatus status={row.status}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><MarketValue amount={row.filled_quantity} unit={row.base}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><MarketValue amount={row.remaining_quantity ?? row.remaining_budget ?? ""} unit={row.remaining_quantity === null ? row.quote : row.base}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><MarketValue amount={row.reserved_quote} unit={row.quote}/><br/><MarketValue amount={row.reserved_base} unit={row.base}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><Button type="button" disabled={disabled || query.isError || orderTerminal(row.status)} onClick={() => onCancel(row)}>{t("cancel")}</Button></TableCell>
      </TableRow>)}
      {visibleRows.length === 0 && !query.isPending && !query.isError && !query.hasNextPage && <TableRow><TableCell className="paper-order-empty" colSpan={8}>{t(view === "OPEN" ? "noOpenOrders" : "noOrderHistory")}</TableCell></TableRow>}
      {visibleRows.length === 0 && query.hasNextPage && <TableRow><TableCell colSpan={8}>{t("incompleteResults")}</TableCell></TableRow>}
    </TableBody></Table></div>
    {query.isPending && <p role="status">{t("recovering")}</p>}
    {query.hasNextPage && <div className="paper-order-pagination"><Button size="sm" variant="outline" type="button"
      disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{t("more")}</Button></div>}
  </section>;
}
