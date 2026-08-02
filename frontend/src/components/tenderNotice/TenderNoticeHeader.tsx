import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Building,
  Calendar,
  Clock,
  MapPin,
  Bookmark,
  Share,
  ArrowSquareOut,
} from "@phosphor-icons/react";

interface TenderNoticeHeaderProps {
  tender: {
    id: string;
    title: string | null;
    status: string | null;
    procurement_type: string | null;
    procurement_method: string | null;
    contracting_entity_name: string | null;
    contracting_entity_city: string | null;
    contracting_entity_province: string | null;
    published_date: string | null;
    closing_date: string | null;
    source_reference: string | null;
    source_url: string | null;
    category_primary: string | null;
  };
  isBookmarked: boolean;
  isUrgent: boolean;
  closingDays: string;
  onBookmark: () => void;
  onShare: () => void;
  formatDate: (dateString: string | null) => string;
  formatDateTime: (dateString: string | null) => string;
  getStatusColor: (status: string | null) => string;
  compact?: boolean;
}

const capitalize = (s: string | null) =>
  s ? s.charAt(0).toUpperCase() + s.slice(1) : "";

export function TenderNoticeHeader({
  tender,
  isBookmarked,
  isUrgent,
  closingDays,
  onBookmark,
  onShare,
  formatDate,
  formatDateTime,
  getStatusColor,
  compact = false,
}: TenderNoticeHeaderProps) {
  const navigate = useNavigate();

  if (compact) {
    return (
      <div className="bg-surface border border-border rounded-lg p-4 mb-4 text-sm">
        <div className="flex justify-between items-start mb-2">
          <h1 className="text-lg font-semibold text-text">{tender.title}</h1>
          <button
            onClick={onBookmark}
            className={`p-1 rounded-lg transition-colors ${
              isBookmarked ? "text-primary" : "text-text-muted hover:text-text"
            }`}
          >
            <Bookmark className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-2 mb-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded text-xs font-medium border ${getStatusColor(tender.status)}`}>
            {capitalize(tender.status) || "Unknown"}
          </span>
          {tender.procurement_type && (
            <span className="px-2 py-0.5 bg-info/10 text-info rounded text-xs font-medium">
              {tender.procurement_type}
            </span>
          )}
          {tender.category_primary && (
            <span className="px-2 py-0.5 bg-surface-muted text-text-muted rounded text-xs font-medium">
              {capitalize(tender.category_primary)}
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Back Navigation */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 p-2 text-text-muted hover:text-text hover:bg-border rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>
      </div>

      {/* Header Card */}
      <div className="bg-surface border border-border rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            {/* Title + Badges */}
            <div className="flex items-start gap-3 mb-4">
              <h1 className="text-2xl font-bold text-text flex-1">{tender.title}</h1>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`px-3 py-1 rounded-lg text-sm font-medium border ${getStatusColor(tender.status)}`}>
                  {capitalize(tender.status) || "Unknown"}
                </span>
                {tender.procurement_type && (
                  <span className="px-3 py-1 bg-info/10 text-info rounded-lg text-sm font-medium border border-info/20">
                    {tender.procurement_type}
                  </span>
                )}
                {tender.category_primary && (
                  <span className="px-3 py-1 bg-surface-muted text-text-muted rounded-lg text-sm font-medium border border-border">
                    {capitalize(tender.category_primary)}
                  </span>
                )}
              </div>
            </div>

            {/* Key Info Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="flex items-center gap-2 text-text-muted">
                <Building className="w-4 h-4 shrink-0" />
                <span>{tender.contracting_entity_name || "Not specified"}</span>
              </div>
              <div className="flex items-center gap-2 text-text-muted">
                <MapPin className="w-4 h-4 shrink-0" />
                <span>
                  {[tender.contracting_entity_city, tender.contracting_entity_province]
                    .filter(Boolean)
                    .join(", ") || "Location not specified"}
                </span>
              </div>
              <div className="flex items-center gap-2 text-text-muted">
                <Calendar className="w-4 h-4 shrink-0" />
                <span>Published: {formatDate(tender.published_date)}</span>
              </div>
              <div className={`flex items-center gap-2 ${isUrgent ? "text-error" : "text-text-muted"}`}>
                <Clock className="w-4 h-4 shrink-0" />
                <span>Closes: {formatDateTime(tender.closing_date)}</span>
                {closingDays && (
                  <span className={`ml-2 px-2 py-0.5 rounded-lg text-xs font-medium ${
                    isUrgent ? "bg-error/10 text-error" : "bg-success/10 text-success"
                  }`}>
                    {closingDays}
                  </span>
                )}
              </div>
            </div>

            {/* Procurement Method */}
            {tender.procurement_method && (
              <div className="mt-3 text-sm text-text-muted">
                <span className="font-medium">Method:</span> {tender.procurement_method}
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 ml-4">
            <button
              onClick={onBookmark}
              className={`p-2 rounded-lg transition-colors ${
                isBookmarked ? "bg-accent text-white" : "text-text-muted hover:text-accent hover:bg-border"
              }`}
            >
              <Bookmark className="w-5 h-5" />
            </button>
            <button
              onClick={onShare}
              className="p-2 text-text-muted hover:text-text hover:bg-border rounded-lg transition-colors"
            >
              <Share className="w-5 h-5" />
            </button>
            {tender.source_url && (
              <a
                href={tender.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 text-text-muted hover:text-primary hover:bg-border rounded-lg transition-colors"
              >
                <ArrowSquareOut className="w-5 h-5" />
              </a>
            )}
          </div>
        </div>

        {/* Reference */}
        {tender.source_reference && (
          <div className="text-sm text-text-muted border-t border-border pt-3 mt-3">
            Reference: <strong className="text-text">{tender.source_reference}</strong>
          </div>
        )}
      </div>
    </>
  );
}
