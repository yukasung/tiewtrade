import { useInfiniteQuery } from "@tanstack/react-query";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { OrderStatus } from "./components/OrderStatus";
import { Button } from "./components/ui/Button";
import { TableCell, TableRow } from "./components/ui/Table";
import { manualOrderText as t } from "./manualOrderMessages";
import { fetchOrders, manualKey, orderTerminal, type PaperOrder } from "./manualOrders";

/** Existing query and paging identity; presentation grouping never changes intake. */
export function usePaperOrders(owner: string, episode: string, visible: boolean) {
  const query = useInfiniteQuery({ queryKey: [...manualKey(owner), episode, "orders", "all"],
    initialPageParam: null as string | null, queryFn: ({ pageParam, signal }) => fetchOrders(episode, pageParam, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: visible, refetchInterval: visible ? 5000 : false, refetchIntervalInBackground: false,
  });
  const rows = query.data?.pages.flatMap(page => page.orders).filter(row => row.mode === "PAPER" && row.episode_id === episode) ?? [];
  return { query, rows };
}

/** Matches the shared activity columns; amounts remain authoritative server strings. */
export function PaperOrderRow({ row, disabled, onCancel }: { row: PaperOrder; disabled: boolean; onCancel: (value: PaperOrder) => void }) {
  const cell = "px-5 py-4 text-start text-sm";
  return <TableRow>
    <TableCell className={cell}>{row.base}/{row.quote}</TableCell>
    <TableCell className={cell}>{t(row.kind)} · {t(row.side)}</TableCell>
    <TableCell className={cell}><OrderStatus status={row.status}/></TableCell>
    <TableCell className={cell}>{row.quantity != null ? <MarketValue amount={row.quantity} unit={row.base}/> : row.quote_budget != null ? <MarketValue amount={row.quote_budget} unit={row.quote}/> : "—"}</TableCell>
    <TableCell className={cell}>
      <div>{t("filled")}: <MarketValue amount={row.filled_quantity} unit={row.base}/></div>
      <div>{t("remaining")}: <MarketValue amount={row.remaining_quantity ?? row.remaining_budget ?? ""} unit={row.remaining_quantity === null ? row.quote : row.base}/></div>
      <div>{t("reserved")}: <MarketValue amount={row.reserved_quote} unit={row.quote}/> / <MarketValue amount={row.reserved_base} unit={row.base}/></div>
    </TableCell>
    <TableCell className={cell}>{row.limit_price != null ? <MarketValue amount={row.limit_price} unit={row.quote}/> : row.kind === "MARKET" ? t("MARKET") : t("unavailable")}</TableCell>
    <TableCell className={cell}><MarketTime value={row.snapshot_at}/></TableCell>
    <TableCell className={cell}><Button type="button" disabled={disabled || orderTerminal(row.status)} onClick={() => onCancel(row)}>{t("cancel")}</Button></TableCell>
  </TableRow>;
}
