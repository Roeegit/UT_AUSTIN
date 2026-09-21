interface FileTabBarProps {
  filenames: string[];
  activeFile: string | null;
  onSelect: (filename: string) => void;
}

export default function FileTabBar({ filenames, activeFile, onSelect }: FileTabBarProps) {
  if (filenames.length === 0) return null;

  return (
    <div className="flex overflow-x-auto bg-gray-900 border-b border-gray-800 flex-shrink-0 scrollbar-hide">
      {filenames.map((name) => (
        <button
          key={name}
          onClick={() => onSelect(name)}
          className={`px-4 py-2 text-sm font-mono whitespace-nowrap border-r border-gray-800 transition-colors flex-shrink-0 ${
            name === activeFile
              ? "bg-gray-950 text-white border-b-2 border-b-indigo-500"
              : "text-gray-400 hover:text-gray-200 hover:bg-gray-850"
          }`}
        >
          {name}
        </button>
      ))}
    </div>
  );
}
