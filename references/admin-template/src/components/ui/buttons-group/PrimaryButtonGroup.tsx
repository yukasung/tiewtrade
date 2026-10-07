export default function PrimaryButtonGroup() {
  return (
    <div className="custom-scrollbar max-w-full overflow-x-auto pb-3 xsm:pb-0">
      <div className="min-w-77.25">
        <div className="inline-flex items-center shadow-theme-xs">
          <button
            type="button"
            className="inline-flex items-center gap-2 bg-brand-500 px-4 py-3 text-sm font-medium text-white ring-1 ring-brand-500 transition ring-inset first:rounded-s-lg last:rounded-e-lg hover:bg-brand-500"
          >
            Button Text
          </button>
          <button
            type="button"
            className="-ms-px inline-flex items-center gap-2 bg-transparent px-4 py-3 text-sm font-medium text-brand-500 ring-1 ring-brand-500 ring-inset first:rounded-s-lg last:rounded-e-lg hover:bg-brand-500 hover:text-white"
          >
            Button Text
          </button>
          <button
            type="button"
            className="-ms-px inline-flex items-center gap-2 bg-transparent px-4 py-3 text-sm font-medium text-brand-500 ring-1 ring-brand-500 ring-inset first:rounded-s-lg last:rounded-e-lg hover:bg-brand-500 hover:text-white"
          >
            Button Text
          </button>
        </div>
      </div>
    </div>
  );
}
