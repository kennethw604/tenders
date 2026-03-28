import { useState } from "react";
import { CaretRight, CaretLeft } from "@phosphor-icons/react";

const PAGE_SIZE_OPTIONS = [25, 50, 100, 250];

export default function TablePaginationControls({
  getCanNextPage,
  getCanPreviousPage,
  nextPage,
  previousPage,
  pageIndex,
  pageSize,
  pageCount,
  rowCount,
  setPageIndex,
  onPageSizeChange,
}: {
  getCanNextPage: () => boolean;
  getCanPreviousPage: () => boolean;
  nextPage: () => void;
  previousPage: () => void;
  pageIndex: number;
  pageSize: number;
  pageCount: number;
  rowCount: number;
  setPageIndex: (updater: (prev: number) => number) => void;
  onPageSizeChange?: (size: number) => void;
}) {
  const [jumpValue, setJumpValue] = useState("");

  const start = pageIndex * pageSize + 1;
  const end = Math.min((pageIndex + 1) * pageSize, rowCount);

  const handleJump = () => {
    const page = parseInt(jumpValue, 10);
    if (page >= 1 && page <= pageCount) {
      setPageIndex(() => page - 1);
      setJumpValue("");
    }
  };

  const getPageNumbers = () => {
    const pages = [];
    const maxPages = 5;

    if (pageCount <= maxPages) {
      for (let i = 0; i < pageCount; i++) pages.push(i);
    } else {
      pages.push(0);
      let startPage = Math.max(pageIndex - 1, 1);
      let endPage = Math.min(startPage + 2, pageCount - 2);
      if (pageIndex >= pageCount - 3) {
        startPage = pageCount - 4;
        endPage = pageCount - 2;
      }
      if (startPage > 1) pages.push(-1);
      for (let i = startPage; i <= endPage; i++) pages.push(i);
      if (endPage < pageCount - 2) pages.push(-2);
      pages.push(pageCount - 1);
    }
    return pages;
  };

  const pageNumbers = getPageNumbers();

  return (
    <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between px-6 py-4 gap-4">
      {/* Left: showing count + page size selector */}
      <div className="flex items-center gap-4 text-sm text-text">
        {rowCount > 0 ? (
          <span>
            Showing <span className="font-semibold text-primary">{start}</span>
            {" - "}
            <span className="font-semibold text-primary">{end}</span> of{" "}
            <span className="font-semibold text-primary">{rowCount}</span>
          </span>
        ) : (
          <span className="font-medium">No results</span>
        )}

        {onPageSizeChange && (
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="border border-border rounded-lg px-2 py-1 text-sm bg-surface text-text focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size} / page
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Right: pagination buttons + jump */}
      <div className="flex items-center gap-2">
        <button
          className="flex items-center justify-center w-8 h-8 rounded-lg border border-border bg-surface hover:bg-primary/10 hover:border-primary/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          onClick={previousPage}
          disabled={!getCanPreviousPage()}
          aria-label="Previous page"
        >
          <CaretLeft className="w-4 h-4 text-text" />
        </button>

        {pageNumbers.map((pageNumber, index) => {
          if (pageNumber < 0) {
            return (
              <span key={`ellipsis-${index}`} className="px-1 text-text-muted">
                ...
              </span>
            );
          }
          const isActive = pageNumber === pageIndex;
          return (
            <button
              key={pageNumber}
              className={`flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-primary text-white border border-primary shadow-sm"
                  : "bg-surface text-text border border-border hover:bg-primary/10 hover:border-primary/30"
              }`}
              onClick={() => setPageIndex(() => pageNumber)}
              disabled={isActive}
            >
              {pageNumber + 1}
            </button>
          );
        })}

        <button
          className="flex items-center justify-center w-8 h-8 rounded-lg border border-border bg-surface hover:bg-primary/10 hover:border-primary/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          onClick={nextPage}
          disabled={!getCanNextPage()}
          aria-label="Next page"
        >
          <CaretRight className="w-4 h-4 text-text" />
        </button>

        {/* Jump to page */}
        {pageCount > 5 && (
          <div className="flex items-center gap-1 ml-2">
            <span className="text-sm text-text-muted">Go to</span>
            <input
              type="number"
              min={1}
              max={pageCount}
              value={jumpValue}
              onChange={(e) => setJumpValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleJump()}
              placeholder={String(pageIndex + 1)}
              className="w-16 border border-border rounded-lg px-2 py-1 text-sm text-center bg-surface text-text focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <button
              onClick={handleJump}
              className="text-sm px-2 py-1 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
            >
              Go
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
