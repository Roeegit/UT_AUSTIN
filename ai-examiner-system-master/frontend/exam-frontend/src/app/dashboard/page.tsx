import DashboardTable from "../../components/DashboardTable";

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-gray-50 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">Instructor Dashboard</h1>
          <p className="mt-2 text-sm text-gray-600">Review student oral defense results, transcripts, and automated grading reports.</p>
        </div>
        
        <DashboardTable />
      </div>
    </main>
  );
}