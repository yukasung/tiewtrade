import { useEffect, useRef, type ReactNode, type RefObject } from "react";

/** Adapted from TailAdmin Pro 2.4.0 components/ui/modal/index.tsx. */
export function Modal({
  isOpen,
  onClose,
  titleId,
  closeLabel,
  returnFocusRef,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  titleId: string;
  closeLabel: string;
  returnFocusRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
}) {
  const dialog = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    previousFocus.current = returnFocusRef?.current ?? document.activeElement as HTMLElement | null;
    const focusable = () => Array.from(
        dialog.current?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex='-1'])",
        ) ?? [],
      );
    (focusable()[0] ?? dialog.current)?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const currentFocusable = focusable();
      if (currentFocusable.length === 0) return;
      const first = currentFocusable[0];
      const last = currentFocusable[currentFocusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handleKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = "";
      previousFocus.current?.focus();
    };
  }, [isOpen, onClose, returnFocusRef]);

  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-99999 flex items-center justify-center overflow-y-auto p-4">
      <button
        type="button"
        className="fixed inset-0 h-full w-full border-0 bg-gray-400/50 backdrop-blur-[32px]"
        aria-label={closeLabel}
        onClick={onClose}
      />
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative w-full max-w-126.75 rounded-3xl bg-white p-6 shadow-theme-xl lg:p-10 dark:bg-gray-900"
      >
        {children}
      </div>
    </div>
  );
}
