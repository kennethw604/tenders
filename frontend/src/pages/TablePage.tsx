import { TenderTable } from "../components";
import { Table } from "@phosphor-icons/react";
import { PageHeader } from "../components/ui";
import { useState, useCallback, useEffect } from "react";
import type {
  PaginatedTendersResponse,
  TenderStatistics,
} from "../api/tenders";
import { getTenderStatistics } from "../api/tenders";
import TableStatsGrid from "../components/dashboard/TableStatsGrid";
import { QuickFilters } from "../components/search";

const STATUS_TABS = [
  { key: "", label: "All" },
  { key: "open", label: "Open" },
  { key: "awarded", label: "Awarded" },
  { key: "closed", label: "Closed" },
];

export default function TablePage() {
  const [, setPaginationData] = useState<PaginatedTendersResponse | null>(null);
  const [statistics, setStatistics] = useState<TenderStatistics>({
    total: 0,
    byStatus: {},
    byCategory: {},
  });
  const [statsLoading, setStatsLoading] = useState(true);
  const [filterProps, setFilterProps] = useState<any>(null);
  const [activeStatus, setActiveStatus] = useState("");

  useEffect(() => {
    const fetchStatistics = async () => {
      try {
        setStatsLoading(true);
        const stats = await getTenderStatistics();
        setStatistics(stats);
      } catch (error) {
        console.error("Failed to fetch tender statistics:", error);
        setStatistics({ total: 0, byStatus: {}, byCategory: {} });
      } finally {
        setStatsLoading(false);
      }
    };
    fetchStatistics();
  }, []);

  const handleDataChange = useCallback((data: PaginatedTendersResponse) => {
    setPaginationData(data);
  }, []);

  const handleStatusChange = (status: string) => {
    setActiveStatus(status);
    if (filterProps?.onFilterChange) {
      filterProps.onFilterChange({ status });
    }
  };

  return (
    <div className="h-full flex flex-col">
      <PageHeader
        icon={<Table className="w-10 h-10 text-primary" />}
        title="Tender Table"
        description="Browse all procurement opportunities in a comprehensive table view"
      />

      <div className="flex flex-wrap items-center gap-4 mb-4">
        <TableStatsGrid stats={statistics} loading={statsLoading} />
        {filterProps && <QuickFilters {...filterProps} />}
      </div>

      {/* Status tabs */}
      <div className="flex gap-1 mb-4 border-b border-border">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleStatusChange(tab.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeStatus === tab.key
                ? "border-primary text-primary"
                : "border-transparent text-text-muted hover:text-text hover:border-border"
            }`}
          >
            {tab.label}
            {tab.key && statistics.byStatus[tab.key] !== undefined && (
              <span className="ml-1.5 text-xs text-text-light">
                ({statistics.byStatus[tab.key]})
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0">
        <TenderTable
          usePagination={true}
          onDataChange={handleDataChange}
          initialLimit={25}
          statusFilter={activeStatus}
          renderFilters={(props) => {
            if (!filterProps) setFilterProps(props);
            return null;
          }}
        />
      </div>
    </div>
  );
}
