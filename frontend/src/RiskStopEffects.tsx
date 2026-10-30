import { useInfiniteQuery } from "@tanstack/react-query";
import { MarketTime, MarketValue } from "./components/MarketValue";
import { Button } from "./components/ui/Button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/Table";
import { riskCode, riskLocale, riskText as t } from "./riskLimitMessages";
import { fetchRiskEffects, riskKey, type RiskMode } from "./riskLimits";

/** A new effects revision remounts this entire snapshot, including its pagination cursor. */
export function RiskStopEffects({ owner, mode, stop, revision, visible }: {
  owner: string; mode: RiskMode; stop: string; revision: number | null; visible: boolean;
}) {
  const effects = useInfiniteQuery({
    queryKey: [...riskKey(owner, mode), "effects", stop, revision],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => fetchRiskEffects(mode, stop, pageParam, signal),
    getNextPageParam: page => page.next_cursor ?? undefined,
    enabled: visible,
  });
  const first = effects.data?.pages[0];
  // Counts and pages must describe the same watermark, including the first response.
  const consistent = (!first || first.effects_revision === revision) && (effects.data?.pages.every(p => p.stop_id === stop && p.mode === mode && p.effects_revision === first?.effects_revision) ?? true);
  const items = consistent ? effects.data?.pages.flatMap(p => p.items) ?? [] : [];
  return <div className="space-y-4">
    <h3 className="text-base font-medium">{t("effects")}</h3>
    {(effects.isError || !consistent) && <p role="alert">{t("loadError")}</p>}
    {effects.isPending && <p role="status">{t("loading")}</p>}
    {first && <p className="text-sm">{t("effectSnapshot")} <MarketTime value={first.snapshot_at} locale={riskLocale()}/></p>}
    {first && items.length === 0 && <p>{t("empty")}</p>}
    <div className="max-w-full overflow-x-auto">
      <Table className="whitespace-nowrap" aria-label={t("effects")}>
        <TableHeader className="border-b border-gray-100 dark:border-white/5"><TableRow>
          {["target", "order", "state", "filled", "spent"].map(label => <TableHead scope="col" key={label} className="px-5 py-3 text-start text-xs font-medium text-gray-500 dark:text-gray-400">{t(label)}</TableHead>)}
        </TableRow></TableHeader>
        <TableBody className="divide-y divide-gray-100 dark:divide-white/5">{items.map(row => <TableRow key={`${row.target_kind}:${row.target_id}`}>
          <TableCell className="px-5 py-4 text-sm">{riskCode(row.target_kind)}<p className="text-xs">{row.target_id}</p></TableCell>
          <TableCell className="px-5 py-4 text-xs">{row.order_id}</TableCell>
          <TableCell className="px-5 py-4 text-sm">{riskCode(row.state)}</TableCell>
          <TableCell className="px-5 py-4 text-sm">{row.details.filled_quantity ? <MarketValue amount={row.details.filled_quantity} unit=""/> : t("unavailable")}</TableCell>
          <TableCell className="px-5 py-4 text-sm">{row.details.spent ? <MarketValue amount={row.details.spent} unit="USDT"/> : t("unavailable")}</TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>
    {effects.hasNextPage && <Button disabled={effects.isFetching || !consistent} onClick={() => void effects.fetchNextPage()}>{t("more")}</Button>}
    <Button variant="outline" disabled={effects.isFetching} onClick={() => void effects.refetch()}>{t("refresh")}</Button>
  </div>;
}
