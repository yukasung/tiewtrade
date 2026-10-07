import { useState } from "react";
import FaqTwo from "@/components/faqs/FaqTwo";
import { cn } from "@/utils";

const accordionTwoData = [
  {
    title: "Do I get free updates?",
    content:
      "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis magna ac nibh malesuada consectetur at vitae ipsum orem ipsum dolor sit amet, consectetur adipiscing elit nam fermentum, leo et lacinia accumsan.",
  },
  {
    title: "Which license type is suitable for me?",
    content:
      "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis magna ac nibh malesuada consectetur at vitae ipsum orem ipsum dolor sit amet, consectetur adipiscing elit nam fermentum, leo et lacinia accumsan.",
  },
  {
    title: "What are the Seats mentioned on pricing plans?",
    content:
      "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis magna ac nibh malesuada consectetur at vitae ipsum orem ipsum dolor sit amet, consectetur adipiscing elit nam fermentum, leo et lacinia accumsan.",
  },
  {
    title: "Can I Customize TailAdmin to suit my needs?",
    content:
      "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis magna ac nibh malesuada consectetur at vitae ipsum orem ipsum dolor sit amet, consectetur adipiscing elit nam fermentum, leo et lacinia accumsan.",
  },
  {
    title: "What does Unlimited Projects mean?",
    content:
      "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis magna ac nibh malesuada consectetur at vitae ipsum orem ipsum dolor sit amet, consectetur adipiscing elit nam fermentum, leo et lacinia accumsan.",
  },
  {
    title: "Can I upgrade to a higher plan?",
    content:
      "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis magna ac nibh malesuada consectetur at vitae ipsum orem ipsum dolor sit amet, consectetur adipiscing elit nam fermentum, leo et lacinia accumsan.",
  },
  {
    title: "Are there dark and light mode options?",
    content:
      "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec quis magna ac nibh malesuada consectetur at vitae ipsum orem ipsum dolor sit amet, consectetur adipiscing elit nam fermentum, leo et lacinia accumsan.",
  },
];

interface FaqsTwoProps {
  className?: string;
}

export default function FaqsTwo({ className }: FaqsTwoProps) {
  // State to manage the open accordion for both groups separately
  const [openIndexFirstGroup, setOpenIndexFirstGroup] = useState<number | null>(
    0
  );
  const [openIndexSecondGroup, setOpenIndexSecondGroup] = useState<
    number | null
  >(0);

  // Handle toggle for first group
  const handleToggleFirstGroup = (index: number) => {
    setOpenIndexFirstGroup(openIndexFirstGroup === index ? null : index);
  };

  // Handle toggle for second group
  const handleToggleSecondGroup = (index: number) => {
    setOpenIndexSecondGroup(openIndexSecondGroup === index ? null : index);
  };

  // A reusable function to render the FAQ items
  const renderFaqItems = (
    data: typeof accordionTwoData,
    openIndex: number | null,
    handleToggle: (index: number) => void
  ) =>
    data.map((item, index) => (
      <FaqTwo
        key={index}
        title={item.title}
        content={item.content}
        isOpen={openIndex === index}
        toggleAccordionTwo={() => handleToggle(index)}
      />
    ));
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-x-8 gap-y-5 xl:grid-cols-2",
        className
      )}
    >
      <div className="space-y-3">
        {renderFaqItems(
          accordionTwoData.slice(0, 3),
          openIndexFirstGroup,
          handleToggleFirstGroup
        )}
      </div>
      <div className="space-y-3">
        {renderFaqItems(
          accordionTwoData.slice(3, 7),
          openIndexSecondGroup,
          handleToggleSecondGroup
        )}
      </div>
    </div>
  );
}
