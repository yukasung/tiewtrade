import ProgressBar from "./ProgressBar";

export default function ProgressBarInMultipleSizes() {
  return (
    <div className="w-full space-y-4 sm:max-w-[320px]">
      <ProgressBar progress={55} size="sm" />
      <ProgressBar progress={55} size="md" />
      <ProgressBar progress={55} size="lg" />
      <ProgressBar progress={55} size="xl" />
    </div>
  );
}
