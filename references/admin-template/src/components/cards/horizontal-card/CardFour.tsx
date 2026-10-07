import { Link } from "react-router";
import { CardDescription, CardTitle } from "../../ui/card";

export default function CardFour() {
  return (
    <div>
      <div className="flex flex-col gap-5 rounded-xl border border-gray-200 bg-white p-4 sm:flex-row sm:items-center sm:gap-6 dark:border-gray-800 dark:bg-white/3">
        <div className="overflow-hidden rounded-lg">
          <img
            src="/images/cards/card-01.png"
            alt="card"
            className="overflow-hidden rounded-lg"
          />
        </div>
        <div>
          <CardTitle>Card title</CardTitle>

          <CardDescription>
            Lorem ipsum dolor sit amet, consectetur adipisicing elit. Animi
            architecto aspernatur cum et ipsum
          </CardDescription>

          <Link
            to="/"
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-3 text-sm font-medium text-white shadow-theme-xs hover:bg-brand-600"
          >
            Read more
          </Link>
        </div>
      </div>
    </div>
  );
}
