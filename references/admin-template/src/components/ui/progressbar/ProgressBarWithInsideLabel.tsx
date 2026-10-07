import ProgressBar from "./ProgressBar";

export default function ProgressBarWithInsideLabel() {
  return (
    <div className="w-full space-y-5 sm:max-w-[320px]">
      <ProgressBar progress={40} size="lg" label="inside" />
      <ProgressBar progress={70} size="lg" label="inside" />
      <ProgressBar progress={30} size="lg" label="inside" />
    </div>
  );
}
