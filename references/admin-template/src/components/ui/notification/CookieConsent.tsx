import { CloseIcon } from "@/icons";
import { useState } from "react";

interface CookieConsentProps {
  message: string;
  onCookieSettings?: () => void;
  onDenyAll?: () => void;
  onAcceptAll?: () => void;
}

const CookieConsent: React.FC<CookieConsentProps> = ({
  message,
  onCookieSettings,
  onDenyAll,
  onAcceptAll,
}) => {
  const [isVisible, setIsVisible] = useState(true); // Local state to handle visibility

  // Hide the component
  const handleClose = () => setIsVisible(false);

  // Don't render if not visible
  if (!isVisible) return null;

  return (
    <div className="relative w-full max-w-144.25 rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-[#1E2634]">
      {/* Close Button */}
      <button
        className="absolute top-3 right-3 text-gray-400 hover:text-gray-800 dark:hover:text-white/90"
        onClick={handleClose}
        aria-label="Close"
      >
        <CloseIcon />
      </button>

      {/* Message */}
      <p className="mb-6 pr-4 text-sm text-gray-700 dark:text-gray-400">
        {message}
      </p>

      {/* Buttons */}
      <div className="flex flex-col justify-end gap-6 sm:flex-row sm:items-center sm:gap-4">
        {/* Cookie Settings */}
        <button
          type="button"
          className="text-left text-sm font-medium text-gray-700 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
          onClick={onCookieSettings}
        >
          Cookie Settings
        </button>

        {/* Deny All & Accept All */}
        <div className="flex w-full items-center gap-3 sm:w-auto">
          <button
            type="button"
            className="flex w-full justify-center rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-theme-xs hover:bg-gray-50 hover:text-gray-800 sm:w-auto dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-white/3 dark:hover:text-gray-200"
            onClick={() => {
              onDenyAll?.(); // Optional callback
              handleClose();
            }}
          >
            Deny All
          </button>
          <button
            type="button"
            className="flex w-full justify-center rounded-lg bg-brand-500 px-4 py-3 text-sm font-medium text-white shadow-theme-xs hover:bg-brand-600 sm:w-auto"
            onClick={() => {
              onAcceptAll?.(); // Optional callback
              handleClose();
            }}
          >
            Accept All
          </button>
        </div>
      </div>
    </div>
  );
};

export default CookieConsent;
