import { useState, useEffect } from "react";
import { Modal } from "../ui/modal";

interface RenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTitle: string;
  onSave: (name: string) => void;
}

export default function RenameModal({
  isOpen,
  onClose,
  currentTitle,
  onSave,
}: RenameModalProps) {
  const [draft, setDraft] = useState(currentTitle);

  useEffect(() => {
    if (isOpen) setDraft(currentTitle);
  }, [isOpen, currentTitle]);

  const handleSave = () => {
    if (draft.trim()) {
      onSave(draft.trim());
    }
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      showCloseButton={false}
      className="max-w-[500px] p-6 rounded-2xl"
    >
      <h4 className="mb-5 text-base font-semibold text-gray-800 dark:text-white/90">
        Rename Chat
      </h4>
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") handleSave();
        }}
        placeholder="Generate Responsive Login"
        autoFocus
        className="h-11 w-full rounded-lg border border-gray-200 bg-transparent py-2.5 px-4 text-sm text-gray-800 shadow-theme-xs placeholder:text-gray-400 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-800 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dark:focus:border-brand-800"
      />
      <div className="mt-6 flex items-center justify-end gap-3">
        <button
          onClick={onClose}
          className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          className="bg-brand-500 hover:bg-brand-600 rounded-lg px-5 py-2.5 text-sm font-semibold text-white"
        >
          Save
        </button>
      </div>
    </Modal>
  );
}
