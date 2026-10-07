import Tooltip from "../ui/tooltip/Tooltip";
import UserMessage from "./UserMessage";
import {
  DownloadIcon,
  PlayIcon,
  RegenerateIcon,
} from "../../icons";

// ─── Shared style constants ───────────────────────────────────────────────────

const TOOLTIP = { placement: "top" as const, variant: "dark-plain" as const };

// ─────────────────────────────────────────────────────────────────────────────

export default function VideoGeneratorContent() {
  const defaultUserMessage =
    "Minimalist building facade with vertical panels and greenery in a planter, set against a clear blue sky for a modern aesthetic.";

  return (
    <div className="custom-scrollbar relative z-20 mx-auto max-h-[50vh] max-w-[720px] flex-1 space-y-7 overflow-y-auto pb-16">
      {/* User Message */}
      <UserMessage initialText={defaultUserMessage} />

      {/* AI Response */}
      <div className="flex justify-start">
        <div>
          <div className="max-w-[480px]">
            <p className="mb-2 flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <img src="./images/model/google.svg" alt="" />
              Google Veo 3.1
            </p>
            <p className="mb-2 text-base leading-6 text-gray-800 dark:text-white/90">
              I have generated Minimalist building facade with vertical panels
              and greenery in a planter, set against a clear blue sky for a
              modern aesthetic.
            </p>
            <div className="group relative w-full max-w-[400px] overflow-hidden rounded-xl">
              <img
                src="./images/ai/video-thumb.png"
                className="w-full rounded-xl border border-gray-100 object-cover dark:border-gray-700"
                alt=""
              />
              <a
                href="https://www.youtube.com/watch?v=_iHmNaQBtKk"
                className="video-popup absolute top-1/2 left-1/2 flex h-20 w-20 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white/40 backdrop-blur-[10px]"
              >
                <PlayIcon className="size-7" />
              </a>
              <div className="absolute top-0 end-0 flex -translate-y-full items-center justify-between px-3 py-3 opacity-0 transition-all duration-300 ease-in-out group-hover:translate-y-0 group-hover:opacity-100">
                <div className="flex items-center gap-2">
                  <Tooltip content="Regenerate" {...TOOLTIP}>
                    <button className="inline-flex size-9 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow backdrop-blur-sm transition hover:bg-white">
                      <RegenerateIcon className="size-4" />
                    </button>
                  </Tooltip>
                  <Tooltip content="Download" {...TOOLTIP}>
                    <button className="inline-flex size-9 items-center justify-center rounded-full bg-white/90 text-gray-700 shadow backdrop-blur-sm transition hover:bg-white">
                      <DownloadIcon className="size-[18px]" />
                    </button>
                  </Tooltip>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
