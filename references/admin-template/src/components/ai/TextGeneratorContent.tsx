import { useState } from "react";
import Tooltip from "../ui/tooltip/Tooltip";
import UserMessage from "./UserMessage";
import {
  CheckSmIcon,
  CopySmIcon,
  DislikeIcon,
  LikeIcon,
  RegenerateIcon,
} from "../../icons";

// ─── Shared style constants ───────────────────────────────────────────────────

const BTN_CLASS =
  "group flex size-8 items-center justify-center rounded-lg p-2 text-sm font-medium text-gray-800 hover:bg-gray-100 hover:text-gray-900 dark:border-white/5 dark:bg-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white/90";

const REACTION_BTN_CLASS =
  "group flex size-8 items-center justify-center rounded-lg p-2 text-sm font-medium hover:bg-gray-100 dark:border-white/5 dark:bg-gray-900 dark:hover:bg-gray-800";

const REACTION_ICON_CLASS =
  "size-4 transition-colors duration-200 dark:group-hover:text-white/90";

const TOOLTIP = { placement: "top" as const, variant: "dark-plain" as const };

// ─────────────────────────────────────────────────────────────────────────────

export default function TextGeneratorContent() {
  const defaultUserMessage =
    "Can you generate some random, creative, and engaging placeholder text for me? It doesn't need to follow any specific structure—just something fun or interesting to fill space temporarily.";

  // Response 1 States
  const [copiedAI1, setCopiedAI1] = useState(false);
  const [liked1, setLiked1] = useState(false);
  const [disliked1, setDisliked1] = useState(false);

  // Response 2 States
  const [copiedAI2, setCopiedAI2] = useState(false);
  const [liked2, setLiked2] = useState(false);
  const [disliked2, setDisliked2] = useState(false);

  const handleCopyAI1 = async () => {
    try {
      await navigator.clipboard.writeText(
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus et varius tortor. Aenean dui magna, vehicula in lacinia non, euismod sed odio. Aliquam erat volutpat.",
      );
      setCopiedAI1(true);
      setTimeout(() => setCopiedAI1(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  const handleLike1 = () => {
    setLiked1((prev) => !prev);
    if (!liked1) setDisliked1(false);
  };

  const handleDislike1 = () => {
    setDisliked1((prev) => !prev);
    if (!disliked1) setLiked1(false);
  };

  const handleCopyAI2 = async () => {
    try {
      await navigator.clipboard.writeText(
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus et varius tortor. Aenean dui magna, vehicula in lacinia non, euismod sed odio. Aliquam erat volutpat.\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus et varius tortor. Aenean dui magna, vehicula in lacinia non, euismod sed odio. Aliquam erat volutpat.",
      );
      setCopiedAI2(true);
      setTimeout(() => setCopiedAI2(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  const handleLike2 = () => {
    setLiked2((prev) => !prev);
    if (!liked2) setDisliked2(false);
  };

  const handleDislike2 = () => {
    setDisliked2((prev) => !prev);
    if (!disliked2) setLiked2(false);
  };

  return (
    <div className="custom-scrollbar relative z-20 max-h-[50vh] flex-1 mx-auto space-y-7 w-full overflow-y-auto pb-16">
      {/* User Message */}
      <UserMessage initialText={defaultUserMessage} />

      {/* AI Response */}
      <div className="flex justify-start">
        <div>
          <div className="max-w-[480px]">
            <p className="mb-2 flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <img src="/images/model/claude.svg" alt="model" />
              Claude Sonnet 4.6
            </p>
            <p className="mb-2 text-base leading-6 text-gray-800 dark:text-white/90">
              Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus
              et varius tortor. Aenean dui magna, vehicula in lacinia non,
              euismod sed odio. Aliquam erat volutpat.
            </p>
          </div>
          <div className="relative inline-flex mt-3">
            <Tooltip content="Copy" {...TOOLTIP}>
              <button onClick={handleCopyAI1} className={BTN_CLASS}>
                {copiedAI1 ? (
                  <CopySmIcon className="size-4" />
                ) : (
                  <CheckSmIcon className="size-4" />
                )}
              </button>
            </Tooltip>
            <Tooltip content="Like" {...TOOLTIP}>
              <button onClick={handleLike1} className={REACTION_BTN_CLASS}>
                <LikeIcon
                  className={`${REACTION_ICON_CLASS} ${liked1 ? "text-brand-500" : "text-gray-800 dark:text-gray-400"}`}
                />
              </button>
            </Tooltip>
            <Tooltip content="Dislike" {...TOOLTIP}>
              <button onClick={handleDislike1} className={REACTION_BTN_CLASS}>
                <DislikeIcon
                  className={`${REACTION_ICON_CLASS} ${disliked1 ? "text-brand-500" : "text-gray-800 dark:text-gray-400"}`}
                />
              </button>
            </Tooltip>
            <Tooltip content="Regenerate" {...TOOLTIP}>
              <button className={BTN_CLASS}>
                <RegenerateIcon className="size-4" />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>

      {/* User Message 2 */}
      <UserMessage
        initialText="I'm looking for a block of random, imaginative text—something quirky or unexpected to use as placeholder content."
        isEditable={false}
      />

      {/* AI Response 2 */}
      <div className="flex justify-start">
        <div>
          <div className="max-w-[480px]">
            <p className="mb-2 flex items-center gap-1.5 text-sm text-gray-500 dark:text-gray-400">
              <img src="/images/model/claude.svg" alt="model" />
              Claude Sonnet 4.6
            </p>
            <p className="mb-2 text-base leading-6 text-gray-800 dark:text-white/90">
              Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus
              et varius tortor. Aenean dui magna, vehicula in lacinia non,
              euismod sed odio. Aliquam erat volutpat.
            </p>
            <p className="mb-2 text-base leading-6 text-gray-800 dark:text-white/90">
              Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus
              et varius tortor. Aenean dui magna, vehicula in lacinia non,
              euismod sed odio. Aliquam erat volutpat.
            </p>
          </div>
          <div className="relative inline-flex mt-3">
            <Tooltip content="Copy" {...TOOLTIP}>
              <button onClick={handleCopyAI2} className={BTN_CLASS}>
                {copiedAI2 ? (
                  <CopySmIcon className="size-4" />
                ) : (
                  <CheckSmIcon className="size-4" />
                )}
              </button>
            </Tooltip>
            <Tooltip content="Like" {...TOOLTIP}>
              <button onClick={handleLike2} className={REACTION_BTN_CLASS}>
                <LikeIcon
                  className={`${REACTION_ICON_CLASS} ${liked2 ? "text-brand-500" : "text-gray-800 dark:text-gray-400"}`}
                />
              </button>
            </Tooltip>
            <Tooltip content="Dislike" {...TOOLTIP}>
              <button onClick={handleDislike2} className={REACTION_BTN_CLASS}>
                <DislikeIcon
                  className={`${REACTION_ICON_CLASS} ${disliked2 ? "text-brand-500" : "text-gray-800 dark:text-gray-400"}`}
                />
              </button>
            </Tooltip>
            <Tooltip content="Regenerate" {...TOOLTIP}>
              <button className={BTN_CLASS}>
                <RegenerateIcon className="size-4" />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>
    </div>
  );
}
