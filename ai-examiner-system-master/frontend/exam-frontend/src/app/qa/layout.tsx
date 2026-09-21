export default function QALayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ overflow: 'auto', height: '100vh', userSelect: 'text' }}>
      {children}
    </div>
  );
}
