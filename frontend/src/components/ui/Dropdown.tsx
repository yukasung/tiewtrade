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
    const outside = (event: Event) => {
      pointerActive.current = false;
      if (event.target instanceof Node && !surface.current?.contains(event.target) && !trigger.current?.contains(event.target)) onClose();
    };
    const keyboard = (event: KeyboardEvent) => {
      pointerActive.current = false;
      if (event.key === "Escape") { event.preventDefault(); onClose(); trigger.current?.focus(); }
    };
    const blur = (event: FocusEvent) => {
      if (outsideEvent === "click" && pointerActive.current) return;
      if (event.target instanceof Node && !surface.current?.contains(event.target) && !trigger.current?.contains(event.target)) onClose();
    };
    document.addEventListener(outsideEvent, outside);
    if (outsideEvent === "click") {
      document.addEventListener("pointerdown", pointerStarted, true);
      document.addEventListener("pointercancel", pointerCanceled, true);
    }
    document.addEventListener("keydown", keyboard);
    document.addEventListener("focusin", blur);
    return () => {
      document.removeEventListener(outsideEvent, outside);
      document.removeEventListener("pointerdown", pointerStarted, true);
      document.removeEventListener("pointercancel", pointerCanceled, true);
      pointerActive.current = false;
      document.removeEventListener("keydown", keyboard);
      document.removeEventListener("focusin", blur);
    };
  }, [open, onClose, trigger, outsideEvent]);
  if (!open && !keepMounted) return null;
  return <div ref={surface} id={id} hidden={!open} className={`account-dropdown ${className}`}>{children}</div>;
}
