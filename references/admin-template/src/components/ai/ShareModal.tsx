import { useState } from "react";
import { CloseLineIcon } from "../../icons";
import { Modal } from "../ui/modal";
import Tooltip from "../ui/tooltip/Tooltip";

const SHARE_LINK = "https://tailadmin.com/chat/f3d82a91-7c4ea84c31e672bf";

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ShareModal({ isOpen, onClose }: ShareModalProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(SHARE_LINK);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      showCloseButton={false}
      className="max-w-[520px] p-6"
    >
      <div className="relative flex flex-col gap-6">
        {/* Custom close button */}
        <button
          onClick={onClose}
          className="absolute -end-1 -top-1 text-gray-400 hover:text-gray-700 dark:text-gray-500 dark:hover:text-white"
        >
          <CloseLineIcon className="size-5" />
        </button>

        <div>
          <h4 className="mb-1 font-semibold text-gray-800 dark:text-white/90">
            Share Chat
          </h4>
          <p className="mb-3 text-sm leading-5 text-gray-500 dark:text-gray-400">
            Anyone with the link can view this conversation. New messages won't
            be shared.
          </p>
          <div className="flex h-11 items-center overflow-hidden rounded-lg border border-gray-300 px-4 py-3 text-sm whitespace-nowrap text-gray-800 shadow-xs dark:border-gray-800 dark:text-white/90">
            {SHARE_LINK}
          </div>
        </div>

        <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-0">
          <div className="sm:pe-3">
            <button
              onClick={handleCopy}
              className="flex shrink-0 items-center gap-2 rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white"
            >
              {copied ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                >
                  <path
                    d="M4.16699 10.8333L7.50033 14.1667L15.8337 5.83334"
                    stroke="white"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                >
                  <path
                    d="M14.1569 14.1628H7.08822C6.39786 14.1628 5.83822 13.6032 5.83822 12.9128V5.84416M14.1569 14.1628L14.1569 15.4161C14.1569 16.1065 13.5973 16.6661 12.9069 16.6661H4.58496C3.89461 16.6661 3.33496 16.1065 3.33496 15.4161V7.09416C3.33496 6.4038 3.89461 5.84416 4.58496 5.84416H5.83822M14.1569 14.1628H15.4154C16.1058 14.1628 16.6654 13.6032 16.6654 12.9128L16.6654 4.58398C16.6654 3.89363 16.1058 3.33398 15.4154 3.33398H7.08822C6.39786 3.33398 5.83822 3.89363 5.83822 4.58398V5.84416"
                    stroke="white"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
              {copied ? "Copied!" : "Copy Link"}
            </button>
          </div>

          <div className="hidden h-8 w-[1.5px] bg-gray-300 sm:block dark:bg-gray-800" />

          <div className="flex items-center gap-3 ps-3">
            <span className="text-base text-gray-500">Share to:</span>

            {/* Email */}
            <Tooltip
              content="Share via Email"
              placement="top"
              variant="dark-plain"
            >
              <a
                href={`mailto:?subject=Check this chat&body=${encodeURIComponent(SHARE_LINK)}`}
                className="flex size-10 items-center justify-center rounded-lg border border-gray-300 text-gray-800 hover:bg-gray-50 dark:border-gray-700 dark:text-white/90 dark:hover:bg-white/3"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                >
                  <path
                    d="M17.7082 5.19498V14.375C17.7082 15.0654 17.1485 15.625 16.4582 15.625H3.5415C2.85115 15.625 2.2915 15.0654 2.2915 14.375V5.19498M3.1131 4.375H16.8869C17.3405 4.375 17.7082 4.7427 17.7083 5.19632C17.7083 5.46492 17.577 5.71657 17.3567 5.8702L10.7151 10.5016C10.2855 10.8011 9.71472 10.8011 9.28513 10.5016L2.64331 5.87004C2.42312 5.7165 2.29186 5.46504 2.29177 5.1966C2.29162 4.74289 2.65939 4.375 3.1131 4.375Z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
            </Tooltip>

            {/* X / Twitter */}
            <Tooltip content="Share via X" placement="top" variant="dark-plain">
              <a
                href={`https://x.com/intent/tweet?url=${encodeURIComponent(SHARE_LINK)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex size-10 items-center justify-center rounded-lg border border-gray-300 text-gray-800 hover:bg-gray-50 dark:border-gray-700 dark:text-white/90 dark:hover:bg-white/3"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                >
                  <path
                    d="M14.7066 2.60449H17.2158L11.734 8.8699L18.1829 17.3957H13.1334L9.1785 12.2248L4.65318 17.3957H2.14247L8.00586 10.6941L1.81934 2.60449H6.99702L10.5719 7.33085L14.7066 2.60449ZM13.826 15.8938H15.2164L6.24153 4.02748H4.74951L13.826 15.8938Z"
                    fill="currentColor"
                  />
                </svg>
              </a>
            </Tooltip>

            {/* LinkedIn */}
            <Tooltip
              content="Share via LinkedIn"
              placement="top"
              variant="dark-plain"
            >
              <a
                href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(SHARE_LINK)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex size-10 items-center justify-center rounded-lg border border-gray-300 text-gray-800 hover:bg-gray-50 dark:border-gray-700 dark:text-white/90 dark:hover:bg-white/3"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                >
                  <path
                    d="M5.78357 4.16645C5.78326 4.84504 5.37157 5.45569 4.74262 5.71045C4.11367 5.96521 3.39306 5.81321 2.92059 5.32613C2.44811 4.83904 2.31813 4.11413 2.59192 3.49323C2.86572 2.87233 3.48862 2.47942 4.1669 2.49978C5.0678 2.52682 5.78398 3.26515 5.78357 4.16645ZM5.83357 7.06645H2.50024V17.4998H5.83357V7.06645ZM11.1003 7.06645H7.78357V17.4998H11.0669V12.0248C11.0669 8.97475 15.0419 8.69142 15.0419 12.0248V17.4998H18.3336V10.8914C18.3336 5.74978 12.4503 5.94145 11.0669 8.46642L11.1003 7.06645Z"
                    fill="currentColor"
                  />
                </svg>
              </a>
            </Tooltip>

            {/* WhatsApp */}
            <Tooltip
              content="Share via WhatsApp"
              placement="top"
              variant="dark-plain"
            >
              <a
                href={`https://wa.me/?text=${encodeURIComponent(SHARE_LINK)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex size-10 items-center justify-center rounded-lg border border-gray-300 text-gray-800 hover:bg-gray-50 dark:border-gray-700 dark:text-white/90 dark:hover:bg-white/3"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 20 20"
                  fill="none"
                >
                  <path
                    d="M15.8949 4.07808C14.3407 2.52395 12.2239 1.6665 10.0535 1.6665C5.49829 1.6665 1.77375 5.36425 1.77375 9.91945C1.77375 11.3932 2.14888 12.7865 2.87235 14.0727L1.69336 18.3332L6.11458 17.2078C7.32037 17.8509 8.68693 18.226 10.0803 18.226C14.6087 18.1992 18.3064 14.5014 18.3064 9.91945C18.3064 7.72224 17.449 5.659 15.8949 4.07808ZM10.0267 16.8058C8.8209 16.8058 7.56153 16.4575 6.51651 15.8144L6.24856 15.6536L3.64941 16.3235L4.37289 13.8048L4.21212 13.5368C3.54223 12.4382 3.1671 11.152 3.1671 9.86586C3.1671 6.08773 6.22176 3.03306 10.0267 3.03306C11.8488 3.03306 13.5637 3.75654 14.8498 5.04271C16.136 6.32889 16.8595 8.07058 16.8595 9.91945C16.9131 13.7512 13.8048 16.8058 10.0267 16.8058ZM13.8048 11.6611C13.5905 11.554 12.599 11.0449 12.3579 11.0181C12.1703 10.9377 12.0095 10.9109 11.9024 11.1252C11.7952 11.3396 11.3665 11.7683 11.2593 11.9291C11.1521 12.0363 11.0449 12.0899 10.8038 11.9559C10.5894 11.8487 9.94631 11.6611 9.14245 10.9109C8.52616 10.375 8.09743 9.70509 8.01705 9.46393C7.90986 9.24957 7.99025 9.16918 8.12423 9.03521C8.23141 8.92803 8.33859 8.82085 8.41897 8.66007C8.52616 8.55289 8.52616 8.44571 8.63334 8.31174C8.74052 8.20455 8.66013 8.04378 8.60654 7.9366C8.52616 7.82942 8.15102 6.8112 7.96345 6.38248C7.80268 5.95375 7.61512 6.03414 7.50794 6.03414C7.40075 6.03414 7.23998 6.03414 7.1328 6.03414C7.02562 6.03414 6.75767 6.06093 6.5969 6.30209C6.40933 6.51645 5.87342 7.02556 5.87342 8.04378C5.87342 9.062 6.5969 9.99984 6.73087 10.1874C6.83805 10.2946 8.20461 12.4114 10.2411 13.3225C10.7234 13.5368 11.0985 13.6708 11.42 13.778C11.9024 13.9387 12.3579 13.8852 12.7062 13.8584C13.1081 13.8316 13.912 13.376 14.0996 12.8669C14.2603 12.4114 14.2603 11.9559 14.2068 11.8755C14.1532 11.8219 13.9924 11.7415 13.8048 11.6611Z"
                    fill="currentColor"
                  />
                </svg>
              </a>
            </Tooltip>
          </div>
        </div>
      </div>
    </Modal>
  );
}
