interface TimerProps {
  secondsRemaining: number;
}

export default function Timer({ secondsRemaining }: TimerProps) {
  // Pure-function mask for the 3-hour (10,800s) override
  if (secondsRemaining > 7200) {
    return (
      <div className="font-mono text-lg font-bold text-gray-400 select-none uppercase tracking-wider">
        No Time Limit
      </div>
    );
  }

  const minutes = Math.floor(secondsRemaining / 60);
  const seconds = secondsRemaining % 60;
  const isWarning = secondsRemaining <= 180 && secondsRemaining > 60;
  const isLow = secondsRemaining <= 60 && secondsRemaining > 30;
  const isCritical = secondsRemaining <= 30;

  return (
    <div
      className={`font-mono text-2xl font-bold tabular-nums transition-colors ${
        isCritical
          ? "text-red-400 animate-pulse"
          : isLow
          ? "text-orange-400"
          : isWarning
          ? "text-yellow-400"
          : "text-gray-300"
      }`}
    >
      {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
    </div>
  );
}