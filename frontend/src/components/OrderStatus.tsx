import { manualCode } from "../manualOrderMessages";
import { Badge } from "./ui/Badge";
/** Central status presentation. A successful command never implies a filled/canceled order. */
export function OrderStatus({ status }: { status: string | null | undefined }) {
  const color = status === "REJECTED" ? "error" : status === "FILLED" || status === "CANCELED" ? "success" : "light";
  return <Badge color={color}>{manualCode(status)}</Badge>;
}
