import { AdminLangProvider } from "@/lib/adminLang";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminLangProvider>
      <div style={{ overflow: "auto", height: "100vh", userSelect: "text" }}>
        {children}
      </div>
    </AdminLangProvider>
  );
}
