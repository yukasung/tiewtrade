import { useRef, useState } from "react";
import { useModal } from "../../hooks/useModal";
import { useClickOutside } from "../../hooks/useClickOutside";
import RenameModal from "./RenameModal";
import ShareModal from "./ShareModal";
import {
  ChevronDownIcon,
  PencilIcon,
  ShareIcon,
  StarFill,
  StarLine,
  TrashBinIcon,
} from "../../icons";

export default function GeneratorTopBar() {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [starred, setStarred] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  useClickOutside(dropdownRef, () => setDropdownOpen(false));

  const renameModal = useModal();
  const shareModal = useModal();

  const [title, setTitle] = useState("Generate responsive login");

  const handleOpenRename = () => {
    setDropdownOpen(false);
    renameModal.openModal();
  };

  return (
    <>
      {/* Top bar */}
      <div className="mb-4 flex items-center justify-between xl:p-4">
        {/* Title dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="flex items-center gap-3 rounded-lg bg-transparent px-2 py-1 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          >
            {title}
            <ChevronDownIcon
              className={`size-4 transition-transform duration-150${dropdownOpen ? " rotate-180" : ""}`}
            />
          </button>

          {dropdownOpen && (
            <ul className="absolute top-full start-0 z-30 mt-1 w-45 space-y-0.5 rounded-xl bg-white p-1.5 shadow-md dark:bg-gray-800">
              {/* Star / Unstar */}
              <li>
                <button
                  onClick={() => {
                    setStarred((prev) => !prev);
                    setDropdownOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-lg bg-transparent px-1.5 py-2 text-gray-700 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-white/90"
                >
                  {starred ? (
                    <StarFill className="size-5" />
                  ) : (
                    <StarLine className="size-5" />
                  )}
                  {starred ? "Remove Starred" : "Add Starred"}
                </button>
              </li>

              {/* Rename */}
              <li>
                <button
                  onClick={handleOpenRename}
                  className="flex w-full items-center gap-2 rounded-lg bg-transparent px-1.5 py-2 text-gray-700 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-white/90"
                >
                  <PencilIcon className="size-5" />
                  Rename
                </button>
              </li>

              <hr className="my-1 border-gray-200 dark:border-white/10" />

              {/* Delete */}
              <li>
                <button
                  onClick={() => setDropdownOpen(false)}
                  className="flex w-full items-center gap-2 rounded-lg bg-transparent px-1.5 py-2 text-gray-700 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-900 dark:hover:text-white/90"
                >
                  <TrashBinIcon className="size-5" />
                  Delete
                </button>
              </li>
            </ul>
          )}
        </div>

        {/* Share button */}
        <button
          onClick={shareModal.openModal}
          className="flex items-center gap-1.5 rounded-[10px] border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 transition-all hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-900"
        >
          <ShareIcon className="size-4" />
          Share
        </button>
      </div>

      <RenameModal
        isOpen={renameModal.isOpen}
        onClose={renameModal.closeModal}
        currentTitle={title}
        onSave={(name) => setTitle(name)}
      />

      <ShareModal isOpen={shareModal.isOpen} onClose={shareModal.closeModal} />
    </>
  );
}
