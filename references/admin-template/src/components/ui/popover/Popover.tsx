import {
  arrow,
  autoUpdate,
  flip,
  FloatingFocusManager,
  offset,
  type Placement,
  shift,
  useClick,
  useDismiss,
  useFloating,
  useInteractions,
  useRole,
} from "@floating-ui/react";
import { type ReactNode, useRef, useState } from "react";

type Position = "top" | "right" | "bottom" | "left";

interface PopoverProps {
  position: Position;
  trigger: React.ReactNode;
  children: ReactNode;
}

export default function Popover({ position, trigger, children }: PopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const arrowRef = useRef(null);

  // Map position to Floating UI placement
  const placementMap: Record<Position, Placement> = {
    top: "top",
    right: "right",
    bottom: "bottom",
    left: "left",
  };

  // Different offset based on placement - more space for top/bottom
  const getOffset = () => {
    return position === "top" || position === "bottom" ? 20 : 10;
  };

  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    placement: placementMap[position],
    whileElementsMounted: autoUpdate,
    middleware: [
      offset(getOffset()),
      flip({
        fallbackAxisSideDirection: "start",
      }),
      shift({ padding: 8 }),
      arrow({
        element: arrowRef,
        padding: 8,
      }),
    ],
  });

  const click = useClick(context);
  const dismiss = useDismiss(context);
  const role = useRole(context);

  const { getReferenceProps, getFloatingProps } = useInteractions([
    click,
    dismiss,
    role,
  ]);

  // Get arrow position from context
  const arrowX = context.middlewareData.arrow?.x;
  const arrowY = context.middlewareData.arrow?.y;
  const side = context.placement.split("-")[0];

  // Arrow positioning based on placement
  const getArrowStyles = () => {
    const baseStyle: React.CSSProperties = {
      position: "absolute" as const,
      width: "12px",
      height: "12px",
      transform: "rotate(45deg)",
    };

    switch (side) {
      case "top":
        return {
          ...baseStyle,
          bottom: "-6px",
          left: arrowX != null ? `${arrowX}px` : "50%",
        };
      case "bottom":
        return {
          ...baseStyle,
          top: "-6px",
          left: arrowX != null ? `${arrowX}px` : "50%",
        };
      case "left":
        return {
          ...baseStyle,
          right: "-6px",
          top: arrowY != null ? `${arrowY}px` : "50%",
        };
      case "right":
        return {
          ...baseStyle,
          left: "-6px",
          top: arrowY != null ? `${arrowY}px` : "50%",
        };
      default:
        return baseStyle;
    }
  };

  // Get border side classes based on placement
  const getArrowBorderSides = () => {
    switch (side) {
      case "top":
        return "border-r border-b";
      case "bottom":
        return "border-l border-t";
      case "left":
        return "border-r border-t";
      case "right":
        return "border-l border-b";
      default:
        return "";
    }
  };

  return (
    <>
      <span ref={refs.setReference} {...getReferenceProps()}>
        {trigger}
      </span>
      {isOpen && (
        <FloatingFocusManager context={context} modal={false}>
          <div
            ref={refs.setFloating}
            style={floatingStyles}
            {...getFloatingProps()}
            className="z-99999 w-75 rounded-xl border border-gray-200 bg-white text-start shadow-md dark:border-gray-700 dark:bg-[#1E2634]"
          >
            {children}
            <div
              ref={arrowRef}
              style={getArrowStyles()}
              className={`bg-white dark:bg-[#1E2634] ${getArrowBorderSides()} border-gray-200 dark:border-gray-700`}
            />
          </div>
        </FloatingFocusManager>
      )}
    </>
  );
}
