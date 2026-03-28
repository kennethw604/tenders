import type { TenderStatistics } from "../../api/tenders";

interface TableStatsGridProps {
  stats: TenderStatistics;
  loading?: boolean;
}

export default function TableStatsGrid({
  stats,
  loading = false,
}: TableStatsGridProps) {
  if (loading) {
    return (
      <div className="bg-surface border border-border rounded-lg p-4 min-w-[200px] animate-pulse">
        <div className="h-4 bg-gray-200 rounded mb-2 w-3/4"></div>
        <div className="h-8 bg-gray-200 rounded mb-2 w-1/2"></div>
        <div className="h-3 bg-gray-200 rounded w-full"></div>
      </div>
    );
  }

  const total = stats?.total || 0;
  const statusEntries = stats?.byStatus
    ? Object.entries(stats.byStatus)
    : [];
  const openCount =
    statusEntries
      .filter(([key]) => ["open", "active"].includes(key.toLowerCase()))
      .reduce((sum, [, count]) => sum + count, 0) || 0;

  return (
    <div className="flex flex-wrap gap-3">
      <div className="bg-surface border border-border rounded-lg p-4 min-w-[200px] hover:border-primary hover:bg-primary/5 transition-all">
        <div className="text-xs font-semibold text-text-muted mb-3">
          Total Tenders
        </div>
        <div className="flex items-baseline gap-2 mb-3">
          <span
            className={`text-3xl font-bold ${
              total > 0 ? "text-primary" : "text-text"
            }`}
          >
            {total}
          </span>
          <span className="text-xs text-text-light">available</span>
        </div>
        {openCount > 0 && (
          <div className="text-sm">
            <span className="font-semibold text-success">{openCount}</span>
            <span className="text-text-light ml-1">open</span>
          </div>
        )}
      </div>

      {statusEntries.length > 0 && (
        <div className="bg-surface border border-border rounded-lg p-4 min-w-[200px] hover:border-primary hover:bg-primary/5 transition-all">
          <div className="text-xs font-semibold text-text-muted mb-3">
            By Status
          </div>
          <div className="space-y-1">
            {statusEntries.map(([status, count]) => (
              <div key={status} className="flex justify-between text-sm">
                <span className="text-text-light capitalize">{status}</span>
                <span className="font-semibold text-text">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
