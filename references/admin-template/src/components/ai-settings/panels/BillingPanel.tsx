import { SparkIcon } from "../../../icons";
import {
  ActionRow,
  MetaLine,
  PrimaryButton,
  SecondaryButton,
  SettingsCard,
  SettingsPanel,
  SettingsSection,
} from "../shared";

const invoices = [
  { id: "INV-2026-004", amount: "$29", date: "Nov 12, 2026" },
  { id: "INV-2026-005", amount: "$49", date: "May 12, 2026" },
  { id: "INV-2026-006", amount: "$49", date: "Feb 12, 2026" },
];

export function BillingPanel() {
  return (
    <SettingsPanel title="Credit and Billing">
      <SettingsSection title="Current Plan">
        <SettingsCard>
          <ActionRow
            title="You're on Pro plan"
            description="Upgrade to team anytime"
            action={<PrimaryButton>Upgrade to Team</PrimaryButton>}
          />
          <div className="px-3 pt-4 pb-3">
            <div className="rounded-lg bg-gray-50 p-5 dark:bg-gray-900">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2 text-gray-800 dark:text-white/90">
                  <SparkIcon className="size-5" />
                  <span className="text-sm font-medium">Credits remaining</span>
                </div>
                <span className="text-sm font-medium text-gray-800 dark:text-white/90">
                  50
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                <div
                  className="bg-brand-500 h-2 rounded-full"
                  style={{ width: "100%" }}
                />
              </div>
              <div className="mt-3 flex items-center justify-between">
                <div>
                  <p className="text-xs leading-4.5 font-normal text-gray-800 dark:text-white/90">
                    Daily credits
                  </p>
                  <p className="text-xs text-gray-400">
                    Resets to 50 credits in 12 hours
                  </p>
                </div>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  50
                </span>
              </div>
            </div>
          </div>
        </SettingsCard>
      </SettingsSection>

      <SettingsSection title="Payment Method">
        <SettingsCard className="p-2">
          <div className="flex flex-col justify-between gap-3 rounded-lg border border-gray-100 px-5 py-4 sm:flex-row sm:items-center dark:border-gray-800">
            <div>
              <p className="text-sm font-medium text-gray-800 dark:text-white/90">
                Card
              </p>
              <MetaLine items={["Visa ending in 4242", "Expires 06/28"]} />
            </div>
            <SecondaryButton>Update</SecondaryButton>
          </div>
          {invoices.map((invoice, index) => (
            <div
              key={invoice.id}
              className={`flex items-center justify-between px-5 py-4 ${
                index < invoices.length - 1
                  ? "border-b border-gray-100 dark:border-gray-800"
                  : ""
              }`}
            >
              <div>
                <p className="text-sm font-medium text-gray-800 dark:text-white/90">
                  {invoice.id}
                </p>
                <MetaLine items={[invoice.amount, invoice.date]} />
              </div>
              <a
                href="#"
                className="text-sm font-medium text-gray-700 hover:underline dark:text-white/90"
              >
                View Invoice
              </a>
            </div>
          ))}
        </SettingsCard>
      </SettingsSection>
    </SettingsPanel>
  );
}
