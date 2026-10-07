import ProgressBar from "./ProgressBar";

export default function DefaultProgressbarExample() {
  return (
    <div className="w-full space-y-5 sm:max-w-[320px]">
      <ProgressBar progress={55} />
      <ProgressBar progress={85} />
      <ProgressBar progress={35} />
    </div>
  );
}
