import Button from "@/components/ui/button/Button";
import { Modal } from "@/components/ui/modal";
import { useModal } from "@/hooks/useModal";
import { cn } from "@/utils";

interface AddIntegrationModalProps {
  className?: string;
}

export default function AddIntegrationModal({
  className,
}: AddIntegrationModalProps) {
  const addIntegrationModal = useModal();
  return (
    <>
      <Button onClick={addIntegrationModal.openModal} className={cn(className)}>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="20"
          height="20"
          viewBox="0 0 20 20"
          fill="none"
        >
          <path
            d="M5 10.0002H15.0006M10.0002 5V15.0006"
            stroke="white"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Add New Integration
      </Button>
      <Modal
        isOpen={addIntegrationModal.isOpen}
        onClose={addIntegrationModal.closeModal}
        className="relative m-5 w-full max-w-[558px] rounded-3xl bg-white p-6 sm:m-0 lg:p-10 dark:bg-gray-900"
      >
        <div>
          <h4 className="mb-1 text-start text-title-xs font-semibold text-gray-800 dark:text-white/90">
            New integration
          </h4>
          <p className="mb-7 text-start text-sm leading-6 text-gray-500 dark:text-gray-400">
            Set up an integration and add a brief explanation for the team.
          </p>
          <form action="#">
            <div className="space-y-4">
              <div>
                <label className="mb-1.5 block text-start text-sm font-medium text-gray-700 dark:text-gray-400">
                  Select App
                </label>
                <div className="relative z-20 bg-transparent">
                  <select className="h-11 w-full appearance-none rounded-lg border border-gray-300 bg-transparent bg-none px-4 py-2.5 pe-11 text-start text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:bg-dark-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800">
                    <option
                      value=""
                      className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
                    >
                      Select Option
                    </option>
                    <option
                      value=""
                      className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
                    >
                      Google Meet
                    </option>
                    <option
                      value=""
                      className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
                    >
                      Mailchimp
                    </option>
                    <option
                      value=""
                      className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
                    >
                      Zoom
                    </option>
                    <option
                      value=""
                      className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
                    >
                      Loom
                    </option>
                    <option
                      value=""
                      className="text-gray-700 dark:bg-gray-900 dark:text-gray-400"
                    >
                      Gmail
                    </option>
                  </select>
                  <span className="pointer-events-none absolute top-1/2 end-4 z-30 -translate-y-1/2 text-gray-500 dark:text-gray-400">
                    <svg
                      className="stroke-current"
                      width="20"
                      height="20"
                      viewBox="0 0 20 20"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        d="M4.79175 7.396L10.0001 12.6043L15.2084 7.396"
                        stroke=""
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </span>
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-start text-sm font-medium text-gray-700 dark:text-gray-400">
                  Client ID
                </label>
                <input
                  type="text"
                  placeholder="Enter client ID here"
                  className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-start text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:bg-dark-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-start text-sm font-medium text-gray-700 dark:text-gray-400">
                  Client Secret
                </label>
                <input
                  type="text"
                  placeholder="Enter client secret here"
                  className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-start text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:bg-dark-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-start text-sm font-medium text-gray-700 dark:text-gray-400">
                  Authentication base URI
                </label>
                <input
                  type="text"
                  placeholder="Paste URL here"
                  className="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-start text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:bg-dark-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
                />
              </div>
            </div>

            <p className="mt-4 text-start text-sm text-gray-500 dark:text-gray-400">
              Paste the full URI, and we’ll automatically pull out and show only
              the subdomain for quick reference.
            </p>
          </form>
          <div className="mt-8 flex w-full flex-col items-center justify-between gap-3 sm:flex-row">
            <Button
              variant="outline"
              onClick={addIntegrationModal.closeModal}
              className="w-full"
            >
              Close
            </Button>
            <Button className="w-full">Add Integration</Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

