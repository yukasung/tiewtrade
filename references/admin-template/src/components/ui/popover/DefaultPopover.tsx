import Button from "../button/Button";
import Popover from "./Popover";

export default function DefaultPopover() {
  return (
    <div className="custom-scrollbar max-w-full overflow-auto sm:overflow-visible">
      <div className="min-w-187.5">
        <div className="flex flex-col flex-wrap items-center gap-4 sm:flex-row sm:gap-5">
          <div>
            <Popover
              position="top"
              trigger={<Button size="sm"> Popover on Top</Button>}
            >
              <div className="relative rounded-t-xl border-b border-gray-200 px-5 py-3 dark:border-white/3">
                <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">
                  Top Popover
                </h3>
              </div>
              <div className="p-5">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Lorem ipsum dolor sit amet, consect adipiscing elit. Mauris
                  facilisis congue exclamate justo nec facilisis.
                </p>
              </div>
            </Popover>
          </div>
          <div>
            <Popover
              position="bottom"
              trigger={<Button size="sm"> Popover on Bottom</Button>}
            >
              <div className="relative rounded-t-xl border-b border-gray-200 px-5 py-3 dark:border-white/3">
                <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">
                  Bottom Popover
                </h3>
              </div>
              <div className="p-5">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Lorem ipsum dolor sit amet, consect adipiscing elit. Mauris
                  facilisis congue exclamate justo nec facilisis.
                </p>
              </div>
            </Popover>
          </div>
          <div>
            <Popover
              position="right"
              trigger={<Button size="sm"> Popover on Right</Button>}
            >
              <div className="relative rounded-t-xl border-b border-gray-200 px-5 py-3 dark:border-white/3">
                <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">
                  Right Popover
                </h3>
              </div>
              <div className="p-5">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Lorem ipsum dolor sit amet, consect adipiscing elit. Mauris
                  facilisis congue exclamate justo nec facilisis.
                </p>
              </div>
            </Popover>
          </div>
          <div>
            <Popover
              position="left"
              trigger={<Button size="sm"> Popover on Left</Button>}
            >
              <div className="relative rounded-t-xl border-b border-gray-200 px-5 py-3 dark:border-white/3">
                <h3 className="text-base font-semibold text-gray-800 dark:text-white/90">
                  Left Popover
                </h3>
              </div>
              <div className="p-5">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Lorem ipsum dolor sit amet, consect adipiscing elit. Mauris
                  facilisis congue exclamate justo nec facilisis.
                </p>
              </div>
            </Popover>
          </div>
        </div>
      </div>
    </div>
  );
}
