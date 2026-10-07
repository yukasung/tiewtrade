import { useState } from "react";
import {
  CheckSmIcon,
  CopySmIcon,
  DownloadIcon,
  EditIcon,
  RegenerateIcon,
} from "../../icons";
import Tooltip from "../ui/tooltip/Tooltip";
import UserMessage from "./UserMessage";

// ─── Shared style constants ───────────────────────────────────────────────────

const TOOLTIP = { placement: "top" as const, variant: "dark-plain" as const };

// ─────────────────────────────────────────────────────────────────────────────

export default function ImageGeneratorContent() {
  const defaultUserMessage =
    "Minimalist building facade with vertical panels and greenery in a planter, set against a clear blue sky for a modern aesthetic.";

  const [copiedImage, setCopiedImage] = useState(false);

  const handleCopyImage = async () => {
    try {
      await navigator.clipboard.writeText("/images/ai/img-1.png");
      setCopiedImage(true);
      setTimeout(() => setCopiedImage(false), 2000);
    } catch (err) {
      console.error("Failed to copy: ", err);
    }
  };

  return (
    <div className="relative z-20 mx-auto custom-scrollbar max-h-[50vh] w-full flex-1 space-y-7 overflow-y-auto pb-16">
      {/* User Message */}
      <UserMessage initialText={defaultUserMessage} />

      {/* AI Response */}
      <div className="flex justify-start">
        <div>
          <div className="max-w-[480px]">
            <p className="mb-2 flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <img src="/images/model/nanobanana.svg" alt="model" />
              Nano Banana 2.0
            </p>
            <p className="mb-2 text-base leading-6 text-gray-800 dark:text-white/90">
              I have generated Minimalist building facade with vertical panels
              and greenery in a planter, set against a clear blue sky for a
              modern aesthetic.
            </p>
            <div className="group relative w-full max-w-[300px] overflow-hidden rounded-xl">
              <img
                src="/images/ai/img-1.png"
                className="w-full rounded-xl border border-gray-100 object-cover dark:border-gray-700"
                alt=""
              />
              {/* <!-- Hover Action Bar --> */}
              <div className="absolute start-0 end-0 bottom-0 flex translate-y-full items-center justify-between px-3 py-3 opacity-0 transition-all duration-300 ease-in-out group-hover:translate-y-0 group-hover:opacity-100">
                <div className="flex items-center gap-2">
                  {/* <!-- Edit Button --> */}
                  <Tooltip content="Edit" {...TOOLTIP}>
                    <button className="inline-flex size-9 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow backdrop-blur-sm transition hover:bg-white">
                      <EditIcon className="size-4" />
                    </button>
                  </Tooltip>
                  {/* <!-- Regenerate Button --> */}
                  <Tooltip content="Regenerate" {...TOOLTIP}>
                    <button className="inline-flex size-9 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow backdrop-blur-sm transition hover:bg-white">
                      <RegenerateIcon className="size-4" />
                    </button>
                  </Tooltip>
                  {/* <!-- Copy Button --> */}
                  <Tooltip
                    content={copiedImage ? "Copied!" : "Copy"}
                    {...TOOLTIP}
                  >
                    <button
                      onClick={handleCopyImage}
                      className="inline-flex size-9 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow backdrop-blur-sm transition hover:bg-white"
                    >
                      {copiedImage ? (
                        <CopySmIcon className="size-4" />
                      ) : (
                        <CheckSmIcon className="size-4" />
                      )}
                    </button>
                  </Tooltip>
                </div>
                {/* <!-- Download Button --> */}
                <Tooltip content="Download" {...TOOLTIP}>
                  <button className="inline-flex size-9 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow backdrop-blur-sm transition hover:bg-white">
                    <DownloadIcon className="size-4" />
                  </button>
                </Tooltip>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
