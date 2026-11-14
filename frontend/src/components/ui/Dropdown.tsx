import { useEffect, useRef, type ReactNode, type RefObject } from "react";

/** Adapted from references/admin-template/src/components/ui/dropdown/Dropdown.tsx
 * and components/header/UserDropdown.tsx; a disclosure with native link tab order. */
export function Dropdown({ open, onClose, trigger, id, children, className = "", keepMounted = false, outsideEvent = "pointerdown" }: {
  open: boolean;
  onClose: () => void;
  trigger: RefObject<HTMLButtonElement>;
  id: string;
  children: ReactNode;
  className?: string;
  keepMounted?: boolean;
  outsideEvent?: "pointerdown" | "click";
}) {
  const surface = useRef<HTMLDivElement>(null);
  const pointerActive = useRef(false);
  useEffect(() => {
    if (!open) return;
    // Flowing submenus can move a sibling target if dismissed before its click.
    const pointerStarted = () => { pointerActive.current = true; };
    const pointerCanceled = () => { pointerActive.current = false; };
    const closeIfOutside = (target: EventTarget | null) => {
      if (target instanceof Node && !surface.current?.contains(target) && !trigger.current?.contains(target)) {
        onClose();
      }
    };
    const handleOutside = (event: Event) => {
      pointerActive.current = false;
      closeIfOutside(event.target);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      pointerActive.current = false;
      if (event.key === "Escape") { event.preventDefault(); onClose(); trigger.current?.focus(); }
    };
    const handleFocusIn = (event: FocusEvent) => {
      if (outsideEvent === "click" && pointerActive.current) return;
      closeIfOutside(event.target);
    };
    document.addEventListener(outsideEvent, handleOutside);
    if (outsideEvent === "click") {
      document.addEventListener("pointerdown", pointerStarted, true);
      document.addEventListener("pointercancel", pointerCanceled, true);
    }
    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("focusin", handleFocusIn);
    return () => {
      document.removeEventListener(outsideEvent, handleOutside);
      document.removeEventListener("pointerdown", pointerStarted, true);
      document.removeEventListener("pointercancel", pointerCanceled, true);
      pointerActive.current = false;
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("focusin", handleFocusIn);
    };
  }, [open, onClose, trigger, outsideEvent]);
  if (!open && !keepMounted) return null;
  return <div ref={surface} id={id} hidden={!open} className={`account-dropdown ${className}`}>{children}</div>;
}
