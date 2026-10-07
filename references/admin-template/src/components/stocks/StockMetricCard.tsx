import Badge from "@/components/ui/badge/Badge";
import { ArrowDownIcon, ArrowUpIcon } from "@/icons";

type StockCardProps = {
  imgUrl: string;
  symbol: string;
  companyName: string;
  price: string;
  change: string;
  changeDirection: "up" | "down"; // Direction of the price change
};

// Component rendering
const StockCard: React.FC<StockCardProps> = ({
  imgUrl,
  symbol,
  companyName,
  price,
  change,
  changeDirection,
}) => {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white px-6 pt-6 pb-5 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-6 flex items-center gap-3">
        <div className="h-10 w-10">
          <img src={imgUrl} alt={companyName} />
        </div>
        <div>
          <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">
            {companyName}
          </h3>
          <span className="block text-theme-xs text-gray-500 dark:text-gray-400">
            {symbol}
          </span>
        </div>
      </div>
      <div className="flex items-end justify-between">
        <div>
          <h4 className="text-lg font-semibold text-gray-800 dark:text-white/90">
            {price}
          </h4>
        </div>
        <Badge
          variant="light"
          color={changeDirection === "up" ? "success" : "error"}
          startIcon={
            changeDirection === "up" ? <ArrowUpIcon /> : <ArrowDownIcon />
          }
        >
          {change}
        </Badge>
      </div>
    </div>
  );
};

export default StockCard;
