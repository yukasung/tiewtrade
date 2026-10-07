import Prism from "prismjs";
import { useEffect, useRef, useState } from "react";
import Tooltip from "../ui/tooltip/Tooltip";
// Import additional languages
import "prismjs/components/prism-bash";
import "prismjs/components/prism-css";
import "prismjs/components/prism-json";
import "prismjs/components/prism-jsx";
import "prismjs/components/prism-markdown";
import "prismjs/components/prism-scss";
import "prismjs/components/prism-tsx";
import "prismjs/components/prism-typescript";
import "prismjs/plugins/line-numbers/prism-line-numbers";
import "prismjs/plugins/line-numbers/prism-line-numbers.css";
import { CheckSmIcon, CopySmIcon, EditIcon } from "../../icons";

interface CodeBlockProps {
  code: string;
  language: string;
  showLineNumbers?: boolean;
  className?: string;
}

export default function CodeBlock({
  code,
  language,
  showLineNumbers = false,
  className = "",
}: CodeBlockProps) {
  const codeRef = useRef<HTMLElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (codeRef.current) {
      Prism.highlightElement(codeRef.current);
    }
  }, [code, language]);

  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const preClasses = `rounded-lg overflow-x-auto p-4  text-white text-sm ${
    showLineNumbers ? "line-numbers" : ""
  } ${className}`.trim();

  return (
    <div className="w-full flex-1">
      <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-800">
        <div className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
          >
            <path
              d="M5.0625 5.99976L2.0625 9.00003L5.0625 12M12.9375 5.99976L15.9375 9.00003L12.9375 12M10.3329 2.99994L7.66626 14.9999"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {language.toUpperCase()}
          </p>
        </div>
        <div>
          <div className="flex gap-2">
            <Tooltip content="Copy" placement="top" variant="dark-plain">
              <button
                onClick={handleCopy}
                className="inline-flex size-8 items-center justify-center rounded-full border border-gray-200 text-gray-700 dark:border-gray-800 dark:text-gray-400"
              >
                {copied ? (
                  <CopySmIcon className="size-4" />
                ) : (
                  <CheckSmIcon className="size-4" />
                )}
              </button>
            </Tooltip>
            <Tooltip content="Edit" placement="top" variant="dark-plain">
              <button className="inline-flex size-8 items-center justify-center rounded-full border border-gray-200 text-gray-700 dark:border-gray-800 dark:text-gray-400">
                <EditIcon className="size-4" />
              </button>
            </Tooltip>
          </div>
        </div>
      </div>
      <div className="custom-scrollbar max-h-87.5 w-full overflow-y-auto px-5 py-4">
        <pre className={preClasses}>
          <code ref={codeRef} className={`language-${language}`}>
            {code}
          </code>
        </pre>
      </div>
    </div>
  );
}
