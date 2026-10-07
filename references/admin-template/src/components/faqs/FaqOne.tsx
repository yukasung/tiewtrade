import { ChevronDownIcon } from "@/icons";
import { cn } from "@/utils";

interface FaqOneProps {
  title: string;
  content: string;
  isOpen: boolean;
  toggleAccordion: () => void; // Function to toggle the open state
  className?: string;
}

const FaqOne: React.FC<FaqOneProps> = ({
  title,
  content,
  isOpen,
  toggleAccordion,
  className,
}) => {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3",
        className,
      )}
    >
      {/* Accordion Header */}
      <div
        onClick={toggleAccordion}
        className={cn(
          "flex cursor-pointer items-center justify-between py-3 ps-6 pe-3",
          isOpen && "bg-gray-50 dark:bg-white/3",
        )}
      >
        <h4 className="text-start text-lg font-medium text-gray-800 dark:text-white/90">
          {title}
        </h4>
        <button
          type="button"
          aria-expanded={isOpen}
          className={cn(
            "flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gray-100 transition-transform duration-200 ease-linear dark:bg-white/3",
            isOpen
              ? "rotate-180 text-gray-800 dark:text-white/90"
              : "text-gray-500 dark:text-gray-400",
          )}
        >
          <ChevronDownIcon className="size-5" />
        </button>
      </div>

      {/* Accordion Content */}
      {isOpen && (
        <div className="px-6 py-7">
          <p className="text-start text-base text-gray-500 dark:text-gray-400">
            {content}
          </p>
        </div>
      )}
    </div>
  );
};

export default FaqOne;
