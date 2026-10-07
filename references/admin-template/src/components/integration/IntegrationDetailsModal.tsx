import { Modal } from "@/components/ui/modal";
import { useModal } from "@/hooks/useModal";
import { cn } from "@/utils";

interface IntegrationDetailsModalProps {
  className?: string;
}

export default function IntegrationDetailsModal({
  className,
}: IntegrationDetailsModalProps) {
  const detailsModal = useModal();
  return (
    <>
      <button
        type="button"
        onClick={detailsModal.openModal}
        className={cn(
          "inline-flex h-11 items-center justify-center rounded-lg border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 shadow-theme-xs dark:border-gray-700 dark:text-gray-400",
          className
        )}
      >
        Details
      </button>

      <Modal
        isOpen={detailsModal.isOpen}
        onClose={detailsModal.closeModal}
        className="relative m-5 w-full max-w-[558px] overflow-hidden rounded-3xl bg-white p-6 sm:m-0 lg:p-10 dark:bg-gray-900"
      >
        <div>
          <h4 className="mb-1 text-start text-title-xs font-semibold text-gray-800 dark:text-white/90">
            Integration details
          </h4>
          <p className="mb-7 text-start text-sm leading-6 text-gray-500 dark:text-gray-400">
            Check the credentials and settings for your connected app.
          </p>
          <ul>
            <li className="flex justify-between border-b border-gray-100 py-2.5 dark:border-gray-800">
              <span className="w-1/2 text-start text-sm text-gray-500 dark:text-gray-400">
                App Name
              </span>
              <span className="w-1/2 break-words text-end text-sm text-gray-700 dark:text-gray-400">
                Example App
              </span>
            </li>
            <li className="flex justify-between border-b border-gray-100 py-2.5 dark:border-gray-800">
              <span className="w-1/2 text-start text-sm text-gray-500 dark:text-gray-400">
                Client ID
              </span>
              <span className="w-1/2 break-words text-end text-sm text-gray-700 dark:text-gray-400">
                872364219810-abc123xyz456.apps.usercontent.com
              </span>
            </li>
            <li className="flex justify-between border-b border-gray-100 py-2.5 dark:border-gray-800">
              <span className="w-1/2 text-start text-sm text-gray-500 dark:text-gray-400">
                Client Secret
              </span>
              <span className="w-1/2 break-words text-end text-sm text-gray-700 dark:text-gray-400">
                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e
              </span>
            </li>
            <li className="flex justify-between border-b border-gray-100 py-2.5 dark:border-gray-800">
              <span className="w-1/2 text-start text-sm text-gray-500 dark:text-gray-400">
                Authentication base URI
              </span>
              <span className="w-1/2 break-words text-end text-sm text-gray-700 dark:text-gray-400">
                https://accounts.app.com/o/oauth2/auth
              </span>
            </li>
          </ul>
        </div>
      </Modal>
    </>
  );
}

