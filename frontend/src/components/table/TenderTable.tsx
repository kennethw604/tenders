import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  getPaginationRowModel,
  type ColumnResizeMode,
  type Updater,
  type PaginationState,
  type Row,
  getFilteredRowModel,
  createColumnHelper,
  getSortedRowModel,
  type SortingState,
} from "@tanstack/react-table";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableCell,
  TableEmptyState,
  TableLoadingState,
} from "./";
import { useState, useMemo, useCallback, useEffect } from "react";
import TablePaginationControls from "./TablePaginationControls";
import "./tableStyles.css";
import type { Tender } from "../../api/types";
import { Link } from "react-router-dom";
import {
  getTendersPaginated,
  type PaginatedTendersResponse,
  type PaginatedTendersParams,
} from "../../api/tenders";

interface TenderTableProps {
  // Legacy props for backward compatibility
  isLoading?: boolean;
  tenders?: Tender[];
  // New pagination props
  usePagination?: boolean;
  initialPage?: number;
  initialLimit?: number;
  initialSearch?: string;
  initialFilters?: {
    status?: string;
    category?: string;
    region?: string;
    entity?: string;
  };
  onDataChange?: (data: PaginatedTendersResponse) => void;
  statusFilter?: string;
  // Expose filter controls
  renderFilters?: (props: {
    setGlobalFilter: (filter: string) => void;
    tenders: Tender[];
    rowCount: number;
    onFilteredDataChange?: (filteredData: Tender[]) => void;
    usePagination: boolean;
    onSearchChange?: (search: string) => void;
    onFilterChange?: (filters: Record<string, string>) => void;
  }) => React.ReactNode;
}

const NUMBER_OF_TENDERS_PER_PAGE = 25;

// Create column helper
const columnHelper = createColumnHelper<Tender>();

const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case "open":
    case "active":
      return "bg-success/10 text-success border-success/20";
    case "closed":
      return "bg-error/10 text-error border-error/20";
    case "cancelled":
      return "bg-text-muted/10 text-text-muted border-text-muted/20";
    case "awarded":
      return "bg-info/10 text-info border-info/20";
    default:
      return "bg-warning/10 text-warning border-warning/20";
  }
};

const capitalize = (s: string | null) =>
  s ? s.charAt(0).toUpperCase() + s.slice(1) : "";

// Define table columns
const tenderColumns = [
  columnHelper.accessor("title", {
    header: "Tender",
    size: 280,
    enableSorting: true,
    cell: (info) => {
      const tender = info.row.original;
      return (
        <div>
          <Link
            to={`/tender-notice/${tender.id}`}
            className="text-primary hover:text-primary-dark font-medium text-sm"
          >
            {info.getValue() || "Untitled"}
          </Link>
          {tender.procurement_type && (
            <span className="ml-2 px-1.5 py-0.5 bg-info/10 text-info text-[10px] rounded font-medium">
              {tender.procurement_type.length > 30
                ? tender.procurement_type.replace(/^Request for /, "RF").replace(/^Invitation to /, "IT")
                : tender.procurement_type}
            </span>
          )}
        </div>
      );
    },
  }),
  columnHelper.accessor("contracting_entity_name", {
    id: "entity_info",
    header: "Entity",
    size: 200,
    enableSorting: true,
    cell: (info) => {
      const tender = info.row.original;
      return (
        <div className="text-sm">
          <div className="text-text font-medium truncate">{tender.contracting_entity_name || "Unknown"}</div>
          <div className="text-text-muted text-xs truncate">
            {[tender.contracting_entity_city, tender.contracting_entity_province]
              .filter(Boolean)
              .join(", ")}
          </div>
        </div>
      );
    },
  }),
  columnHelper.accessor("category_primary", {
    header: "Category",
    size: 100,
    enableSorting: true,
    cell: (info) => {
      const val = info.getValue();
      return (
        <span className="text-sm text-text">
          {capitalize(val) || "N/A"}
        </span>
      );
    },
  }),
  columnHelper.accessor("closing_date", {
    header: "Closes",
    size: 140,
    enableSorting: true,
    cell: (info) => {
      const closing = info.getValue();
      if (!closing) return <span className="text-text-muted text-sm">N/A</span>;
      const date = new Date(closing);
      const now = new Date();
      const diffDays = Math.ceil((date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
      const isUrgent = diffDays >= 0 && diffDays <= 7;
      const isPast = diffDays < 0;
      return (
        <div className="text-sm">
          <div className="text-text">{date.toLocaleDateString("en-CA", { month: "short", day: "numeric", year: "numeric" })}</div>
          {!isPast && (
            <span className={`text-xs ${isUrgent ? "text-error font-medium" : "text-text-muted"}`}>
              {diffDays === 0 ? "Today" : diffDays === 1 ? "Tomorrow" : `${diffDays} days`}
            </span>
          )}
        </div>
      );
    },
  }),
  columnHelper.accessor("procurement_method", {
    header: "Method",
    size: 160,
    enableSorting: true,
    cell: (info) => {
      const val = info.getValue();
      return <span className="text-sm text-text-muted">{val || "N/A"}</span>;
    },
  }),
  columnHelper.accessor("status", {
    header: "Status",
    size: 90,
    enableSorting: true,
    cell: (info) => {
      const status = info.getValue() || "Unknown";
      return (
        <span className={`px-2 py-1 rounded text-xs font-medium border ${getStatusColor(status)}`}>
          {capitalize(status)}
        </span>
      );
    },
  }),
];
export default function TenderTable({
  isLoading = false,
  tenders = [],
  usePagination = false,
  initialPage = 1,
  initialLimit = NUMBER_OF_TENDERS_PER_PAGE,
  initialSearch = "",
  initialFilters = {},
  onDataChange,
  renderFilters,
  statusFilter = "",
}: TenderTableProps) {
  const [globalFilter, setGlobalFilter] = useState("");
  const [filteredTenders, setFilteredTenders] = useState<Tender[]>([]);

  // Server-side pagination state
  const [paginatedData, setPaginatedData] =
    useState<PaginatedTendersResponse | null>(null);
  const [paginationLoading, setPaginationLoading] = useState(false);
  const [paginationParams, setPaginationParams] =
    useState<PaginatedTendersParams>({
      page: initialPage,
      limit: initialLimit,
      search: initialSearch,
      sortBy: "published_date",
      sortOrder: "desc",
      ...initialFilters,
    });

  const globalTenderFilter = useCallback(
    (row: Row<Tender>, _columnId: string, filterValue: string) => {
      const tender = row.original;
      return (
        tender.title
          ?.toString()
          .toLowerCase()
          .includes(filterValue.toLowerCase()) ||
        tender.description
          ?.toString()
          .toLowerCase()
          .includes(filterValue.toLowerCase()) ||
        tender.contracting_entity_name
          ?.toString()
          .toLowerCase()
          .includes(filterValue.toLowerCase()) ||
        false
      );
    },
    []
  );

  const [pagination, setPagination] = useState({
    pageIndex: usePagination ? initialPage - 1 : 0,
    pageSize: usePagination ? initialLimit : NUMBER_OF_TENDERS_PER_PAGE,
  });
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnResizeMode] = useState<ColumnResizeMode>("onChange");

  // Handle filtered data from QuickFilters
  const handleFilteredDataChange = useCallback((filtered: Tender[]) => {
    setFilteredTenders(filtered);
    setPagination((prev) => ({ ...prev, pageIndex: 0 })); // Reset to first page when filters change
  }, []);

  // Fetch paginated data when using server-side pagination
  const fetchPaginatedData = useCallback(
    async (params: PaginatedTendersParams) => {
      if (!usePagination) return;

      setPaginationLoading(true);
      try {
        const response = await getTendersPaginated(params);
        setPaginatedData(response);
        onDataChange?.(response);
      } catch (error) {
        console.error("Failed to fetch paginated tenders:", error);
      } finally {
        setPaginationLoading(false);
      }
    },
    [usePagination, onDataChange]
  ); // onDataChange intentionally excluded to prevent infinite loop

  // Effect to fetch data when params change
  useEffect(() => {
    if (usePagination) {
      fetchPaginatedData(paginationParams);
    }
  }, [paginationParams, usePagination, fetchPaginatedData]);

  // Effect to update status filter from parent
  useEffect(() => {
    if (usePagination) {
      setPaginationParams((prev) => ({
        ...prev,
        status: statusFilter || undefined,
        page: 1,
      }));
    }
  }, [statusFilter, usePagination]);

  // Update pagination params
  const updatePaginationParams = useCallback(
    (updates: Partial<PaginatedTendersParams>) => {
      setPaginationParams((prev) => ({
        ...prev,
        ...updates,
        // Reset to page 1 when changing search or filters
        ...(updates.search !== undefined ||
        Object.keys(updates).some((key) =>
          ["status", "category", "region", "entity"].includes(key)
        )
          ? { page: 1 }
          : {}),
      }));
    },
    []
  );

  // Use filtered data if available, otherwise use all tenders
  const tableData = useMemo(() => {
    if (usePagination && paginatedData) {
      return paginatedData.data;
    }
    return filteredTenders.length > 0 ? filteredTenders : [];
  }, [usePagination, paginatedData, filteredTenders]);

  // Memoize pagination change handler
  const onPaginationChange = useCallback(
    (updater: Updater<PaginationState>) => {
      if (usePagination) {
        // For server-side pagination, update the API params
        const newPagination =
          typeof updater === "function" ? updater(pagination) : updater;
        const newPage = newPagination.pageIndex + 1;
        updatePaginationParams({
          page: newPage,
          limit: newPagination.pageSize,
        });
      }
      setPagination(updater);
    },
    [usePagination, pagination, updatePaginationParams]
  );

  const table = useReactTable({
    data: tableData,
    columns: tenderColumns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: usePagination ? undefined : getPaginationRowModel(),
    getSortedRowModel: usePagination ? undefined : getSortedRowModel(),
    columnResizeMode,
    state: {
      pagination,
      sorting,
      globalFilter,
    },
    onPaginationChange,
    onSortingChange: (updater) => {
      setSorting(updater);
      if (usePagination) {
        const newSorting =
          typeof updater === "function" ? updater(sorting) : updater;
        if (newSorting.length > 0) {
          const sort = newSorting[0];
          updatePaginationParams({
            sortBy: sort.id,
            sortOrder: sort.desc ? "desc" : "asc",
            page: 1, // Reset to first page when sorting changes
          });
        }
      }
    },
    rowCount: usePagination
      ? paginatedData?.pagination.total || 0
      : tableData.length,
    manualPagination: usePagination,
    manualSorting: usePagination,
    pageCount: usePagination ? paginatedData?.pagination.totalPages || 1 : -1,
    enableColumnResizing: true,
    enableSorting: true,
    globalFilterFn: globalTenderFilter,
    getFilteredRowModel: usePagination ? undefined : getFilteredRowModel(),
  });

  const TenderTableInner = () => {
    // Show loading state
    if (isLoading || (usePagination && paginationLoading)) {
      return (
        <div className="w-full bg-surface rounded-lg border border-border">
          <TableLoadingState message="Finding relevant tenders..." />
        </div>
      );
    }

    // Show empty state if no data
    if (!tableData || tableData.length === 0) {
      return (
        <div className="w-full bg-surface rounded-lg border border-border">
          <TableEmptyState
            message="No tenders found"
            description="Try adjusting your search criteria or check back later for new opportunities."
          />
        </div>
      );
    }

    return (
      <div className="flex flex-col bg-surface rounded-lg border border-border">
        <div>
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id} isHeader>
                  {headerGroup.headers.map((header) => {
                    const column = header.column.columnDef;
                    const width = column.size ? `${column.size}px` : undefined;

                    return (
                      <TableCell
                        key={header.id}
                        isHeader
                        width={width}
                        className="relative select-none"
                      >
                        {header.isPlaceholder ? null : (
                          <div
                            className="flex items-center justify-between cursor-pointer hover:bg-surface-muted/50 p-1 rounded"
                            onClick={
                              header.column.getCanSort()
                                ? header.column.getToggleSortingHandler()
                                : undefined
                            }
                          >
                            <div className="flex items-center gap-2">
                              {flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                              {header.column.getCanSort() && (
                                <span className="text-text-light">
                                  {{
                                    asc: "↑",
                                    desc: "↓",
                                  }[header.column.getIsSorted() as string] ??
                                    "↕"}
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                        {header.column.getCanResize() && (
                          <div
                            className={`resizer ${
                              header.column.getIsResizing() ? "isResizing" : ""
                            }`}
                            onMouseDown={header.getResizeHandler()}
                            onTouchStart={header.getResizeHandler()}
                          />
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} className="hover:bg-surface-muted">
                  {row.getVisibleCells().map((cell) => {
                    const column = cell.column.columnDef;
                    const width = column.size ? `${column.size}px` : undefined;

                    // Only use truncate for columns that aren't Tender or Dates
                    const useTruncate =
                      cell.column.id !== "title" &&
                      cell.column.id !== "closing_date";

                    return (
                      <TableCell
                        key={cell.id}
                        width={width}
                        truncate={useTruncate}
                        className={
                          cell.column.id === "title" ? "align-top" : ""
                        }
                      >
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <div className="flex-shrink-0 border-t border-border">
          <TablePaginationControls
            getCanNextPage={
              usePagination
                ? () => paginatedData?.pagination.hasNext || false
                : table.getCanNextPage
            }
            getCanPreviousPage={
              usePagination
                ? () => paginatedData?.pagination.hasPrev || false
                : table.getCanPreviousPage
            }
            nextPage={
              usePagination
                ? () =>
                    updatePaginationParams({
                      page: (paginationParams.page || 1) + 1,
                    })
                : table.nextPage
            }
            previousPage={
              usePagination
                ? () =>
                    updatePaginationParams({
                      page: Math.max(1, (paginationParams.page || 1) - 1),
                    })
                : table.previousPage
            }
            pageIndex={
              usePagination
                ? (paginationParams.page || 1) - 1
                : pagination.pageIndex
            }
            pageSize={
              usePagination
                ? paginationParams.limit || NUMBER_OF_TENDERS_PER_PAGE
                : pagination.pageSize
            }
            pageCount={
              usePagination
                ? paginatedData?.pagination.totalPages || 1
                : table.getPageCount()
            }
            setPageIndex={
              usePagination
                ? (updater: number | ((prev: number) => number)) => {
                    const newIndex =
                      typeof updater === "function"
                        ? updater(pagination.pageIndex)
                        : updater;
                    updatePaginationParams({ page: newIndex + 1 });
                  }
                : table.setPageIndex
            }
            rowCount={
              usePagination
                ? paginatedData?.pagination.total || 0
                : table.getRowCount()
            }
            onPageSizeChange={
              usePagination
                ? (size: number) => updatePaginationParams({ limit: size, page: 1 })
                : undefined
            }
          />
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col">
      {renderFilters?.({
        setGlobalFilter,
        tenders: usePagination ? [] : tenders || [],
        rowCount: usePagination
          ? paginatedData?.pagination.total || 0
          : filteredTenders.length,
        onFilteredDataChange: usePagination
          ? undefined
          : handleFilteredDataChange,
        usePagination,
        onSearchChange: usePagination
          ? (search: string) => updatePaginationParams({ search })
          : undefined,
        onFilterChange: usePagination
          ? (filters: Record<string, string>) => updatePaginationParams(filters)
          : undefined,
      })}
      <div>
        <TenderTableInner />
      </div>
    </div>
  );
}
