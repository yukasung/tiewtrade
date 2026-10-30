import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { OrderStatus } from "./components/OrderStatus";
import { Button } from "./components/ui/Button";
import { ComponentCard } from "./components/ui/ComponentCard";
import { Modal } from "./components/ui/Modal";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/Table";
import { Tabs } from "./components/ui/Tabs";
import { manualCode, manualOrderLocale, manualOrderText as t } from "./manualOrderMessages";
import { fetchOrder, fetchOrders, manualKey, orderTerminal, type PaperOrder } from "./manualOrders";

export function PaperOrderList({ owner, episode, visible, disabled, onCancel }: {
  owner: string; episode: string; visible: boolean; disabled: boolean; onCancel: (value: PaperOrder) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<"OPEN" | "HISTORY">("OPEN");
  const closeDetail = useCallback(() => setSelected(null), []);
  const query = useInfiniteQuery({ queryKey: [...manualKey(owner), episode, "orders", "all"],
    initialPageParam: null as string | null, queryFn: ({ pageParam, signal }) => fetchOrders(episode, pageParam, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: visible, refetchInterval: visible ? 5000 : false, refetchIntervalInBackground: false,
  });
  const detail = useQuery({ queryKey: [...manualKey(owner), episode, "order", selected],
    enabled: !!selected && visible, queryFn: async ({ signal }) => {
      const result = await fetchOrder(selected!, signal);
      if (result.mode !== "PAPER" || result.episode_id !== episode || result.order_id !== selected) throw new Error("order scope mismatch");
      return result;
    }, refetchInterval: q => visible && (!q.state.data || !orderTerminal(q.state.data.status)) ? 1000 : false,
  });
  const rows = query.data?.pages.flatMap(page => page.orders).filter(row => row.mode === "PAPER" && row.episode_id === episode) ?? [];
  const visibleRows = rows.filter(row => view === "OPEN" ? !orderTerminal(row.status) : orderTerminal(row.status));
  return <ComponentCard title={t("orders")} headingId="manual-orders-heading">
    <Tabs id="manual-orders-view" controls="manual-orders-table" label={t("orders")}
      items={[{ id: "OPEN", label: t("openOrders") }, { id: "HISTORY", label: t("orderHistory") }]}
      active={view} onChange={setView}/>
    {query.isError && <p role="alert">{t("loadError")}</p>}
    <div id="manual-orders-table" role="tabpanel" className="max-w-full overflow-x-auto rounded-xl border border-gray-200 dark:border-white/5"><Table className="whitespace-nowrap"><TableHeader className="border-b border-gray-100 dark:border-white/5"><TableRow>
      {["pair", "side", "kind", "status", "filled", "remaining", "reserved", "details", "cancel"].map(name => <TableHead key={name} scope="col" className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">{t(name)}</TableHead>)}
    </TableRow></TableHeader><TableBody className="divide-y divide-gray-100 dark:divide-white/5">
      {visibleRows.map(row => <TableRow key={row.order_id}>
        <TableCell className="px-5 py-4 text-start text-sm">{row.base}/{row.quote}</TableCell><TableCell className="px-5 py-4 text-start text-sm">{t(row.side)}</TableCell><TableCell className="px-5 py-4 text-start text-sm">{t(row.kind)}</TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><OrderStatus status={row.status}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><MarketValue amount={row.filled_quantity} unit={row.base}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><MarketValue amount={row.remaining_quantity ?? row.remaining_budget ?? ""} unit={row.remaining_quantity === null ? row.quote : row.base}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><MarketValue amount={row.reserved_quote} unit={row.quote}/><br/><MarketValue amount={row.reserved_base} unit={row.base}/></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><Button type="button" onClick={() => setSelected(row.order_id)}>{t("details")}</Button></TableCell>
        <TableCell className="px-5 py-4 text-start text-sm"><Button type="button" disabled={disabled || query.isError || orderTerminal(row.status)} onClick={() => onCancel(row)}>{t("cancel")}</Button></TableCell>
      </TableRow>)}
      {visibleRows.length === 0 && !query.isPending && !query.isError && !query.hasNextPage && <TableRow><TableCell colSpan={9}>{t(view === "OPEN" ? "noOpenOrders" : "noOrderHistory")}</TableCell></TableRow>}
      {visibleRows.length === 0 && query.hasNextPage && <TableRow><TableCell colSpan={9}>{t("incompleteResults")}</TableCell></TableRow>}
    </TableBody></Table></div>
    {query.isPending && <p role="status">{t("recovering")}</p>}
    {query.data && <p className="text-sm">{t("snapshot")} <MarketTime value={query.data.pages[0]!.snapshot_at} locale={manualOrderLocale()}/></p>}
    <Button type="button" onClick={() => void query.refetch()} disabled={query.isFetching}>{t("refresh")}</Button>
    {query.hasNextPage && <Button type="button" disabled={query.isFetching} onClick={() => void query.fetchNextPage()}>{t("more")}</Button>}
    <Modal isOpen={selected !== null} titleId="manual-order-detail-title" onClose={closeDetail} closeLabel={t("close")}>
      <h2 id="manual-order-detail-title">{t("details")}</h2>
      {selected && detail.isPending && <p role="status">{t("recovering")}</p>}
      {detail.isError && <p role="alert">{t("loadError")}</p>}
      {detail.data && <dl className="space-y-4">
        <div><dt>{t("order")}</dt><dd className="break-all">{detail.data.order_id}</dd></div>
        <div><dt>{t("status")}</dt><dd><OrderStatus status={detail.data.status}/></dd></div>
        <div><dt>{t("original")}</dt><dd><MarketValue amount={detail.data.quantity ?? detail.data.quote_budget ?? ""} unit={detail.data.quantity === null ? detail.data.quote : detail.data.base}/></dd></div>
        {detail.data.limit_price !== null && <div><dt>{t("price")}</dt><dd><MarketValue amount={detail.data.limit_price} unit={detail.data.quote}/> {t("GTC")}</dd></div>}
        <div><dt>{t("filled")}</dt><dd><MarketValue amount={detail.data.filled_quantity} unit={detail.data.base}/></dd></div>
        <div><dt>{t("spent")}</dt><dd><MarketValue amount={detail.data.spent} unit={detail.data.quote}/></dd></div>
        <div><dt>{t("remaining")}</dt><dd><MarketValue amount={detail.data.remaining_quantity ?? detail.data.remaining_budget ?? ""} unit={detail.data.remaining_quantity === null ? detail.data.quote : detail.data.base}/></dd></div>
        {detail.data.failure_code && <div><dt>{t("failure")}</dt><dd>{manualCode(detail.data.failure_code)}</dd></div>}
        <div><dt>{t("snapshot")}</dt><dd><MarketTime value={detail.data.snapshot_at} locale={manualOrderLocale()}/></dd></div>
      </dl>}
      <Button type="button" onClick={closeDetail}>{t("close")}</Button>
    </Modal>
  </ComponentCard>;
}
