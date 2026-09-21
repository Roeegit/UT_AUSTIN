export default function ExamLayout({ children }: { children: React.ReactNode }) {
  const childArray = Array.isArray(children) ? children : [children];
  return (
    <div
      dir="ltr"
      className="h-screen w-screen flex bg-gray-950 overflow-hidden"
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="flex-1 min-w-0 overflow-hidden">{childArray[0]}</div>
      <div className="w-px bg-gray-800 flex-shrink-0" />
      <div className="flex-1 min-w-0 overflow-hidden">{childArray[1]}</div>
    </div>
  );
}
