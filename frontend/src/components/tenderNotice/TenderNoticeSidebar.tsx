import {
  Calendar,
  User,
  Phone,
  Envelope,
  Building,
  Globe,
  Bookmark,
  MapPin,
} from "@phosphor-icons/react";

interface TenderNoticeSidebarProps {
  tender: {
    published_date: string | null;
    closing_date: string | null;
    contract_start_date: string | null;
    contact_name: string | null;
    contact_email: string | null;
    contact_phone: string | null;
    contracting_entity_name: string | null;
    contracting_entity_city: string | null;
    contracting_entity_province: string | null;
    contracting_entity_country: string | null;
    delivery_location: string | null;
    source_url: string | null;
  };
  isBookmarked: boolean;
  isUrgent: boolean;
  onBookmark: () => void;
  formatDate: (dateString: string | null) => string;
  formatDateTime: (dateString: string | null) => string;
  compact?: boolean;
}

export function TenderNoticeSidebar({
  tender,
  isBookmarked,
  isUrgent,
  onBookmark,
  formatDate,
  formatDateTime,
  compact = false,
}: TenderNoticeSidebarProps) {
  if (compact) {
    return (
      <div className="flex w-full bg-surface border border-border rounded-lg p-4 gap-4 text-sm">
        <div className="flex-1 space-y-1">
          <h3 className="font-semibold text-text flex items-center gap-2 mb-1">
            <Calendar className="w-4 h-4" /> Dates
          </h3>
          <p><span className="font-medium">Pub:</span> {formatDate(tender.published_date)}</p>
          <p className={isUrgent ? "text-error font-medium" : ""}>
            <span className="font-medium">Close:</span> {formatDateTime(tender.closing_date)}
          </p>
        </div>
        {tender.contact_name && (
          <div className="flex-1 space-y-1">
            <h3 className="font-semibold text-text flex items-center gap-2 mb-1">
              <User className="w-4 h-4" /> Contact
            </h3>
            <p>{tender.contact_name}</p>
          </div>
        )}
      </div>
    );
  }

  const hasContact = tender.contact_name || tender.contact_email || tender.contact_phone;

  return (
    <div className="space-y-4">
      {/* Important Dates */}
      <div className="bg-surface border border-border rounded-lg p-5">
        <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2 uppercase tracking-wide">
          <Calendar className="w-4 h-4" />
          Important Dates
        </h3>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-text-muted">Publication Date</label>
            <p className="text-sm text-text font-medium">{formatDate(tender.published_date)}</p>
          </div>
          <div>
            <label className="text-xs text-text-muted">Closing Date</label>
            <p className={`text-sm font-medium ${isUrgent ? "text-error" : "text-text"}`}>
              {formatDateTime(tender.closing_date)}
            </p>
          </div>
          {tender.contract_start_date && (
            <div>
              <label className="text-xs text-text-muted">Expected Start</label>
              <p className="text-sm text-text font-medium">{formatDate(tender.contract_start_date)}</p>
            </div>
          )}
        </div>
      </div>

      {/* Contact Information */}
      {hasContact && (
        <div className="bg-surface border border-border rounded-lg p-5">
          <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2 uppercase tracking-wide">
            <User className="w-4 h-4" />
            Contact
          </h3>
          <div className="space-y-2.5">
            {tender.contact_name && (
              <div>
                <label className="text-xs text-text-muted">Name</label>
                <p className="text-sm text-text">{tender.contact_name}</p>
              </div>
            )}
            {tender.contact_email && (
              <a
                href={`mailto:${tender.contact_email}`}
                className="flex items-center gap-2 text-sm text-primary hover:underline"
              >
                <Envelope className="w-4 h-4 shrink-0" />
                {tender.contact_email}
              </a>
            )}
            {tender.contact_phone && (
              <a
                href={`tel:${tender.contact_phone}`}
                className="flex items-center gap-2 text-sm text-primary hover:underline"
              >
                <Phone className="w-4 h-4 shrink-0" />
                {tender.contact_phone}
              </a>
            )}
          </div>
        </div>
      )}

      {/* Contracting Entity */}
      <div className="bg-surface border border-border rounded-lg p-5">
        <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2 uppercase tracking-wide">
          <Building className="w-4 h-4" />
          Contracting Entity
        </h3>
        <div className="space-y-2">
          <p className="text-sm text-text font-medium">
            {tender.contracting_entity_name || "Not specified"}
          </p>
          {(tender.contracting_entity_city || tender.contracting_entity_province) && (
            <div className="flex items-center gap-1.5 text-sm text-text-muted">
              <MapPin className="w-3.5 h-3.5 shrink-0" />
              {[tender.contracting_entity_city, tender.contracting_entity_province, tender.contracting_entity_country]
                .filter(Boolean)
                .join(", ")}
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="bg-surface border border-border rounded-lg p-5 space-y-3">
        {tender.source_url && (
          <a
            href={tender.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="w-full bg-primary text-white py-2.5 px-4 rounded-lg hover:bg-primary-dark transition-colors flex items-center justify-center gap-2 text-sm font-medium"
          >
            <Globe className="w-4 h-4" />
            View Official Notice
          </a>
        )}
        <button
          onClick={onBookmark}
          className={`w-full py-2.5 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm font-medium ${
            isBookmarked
              ? "bg-accent text-white"
              : "border border-border text-text hover:bg-border"
          }`}
        >
          <Bookmark className="w-4 h-4" />
          {isBookmarked ? "Bookmarked" : "Bookmark Tender"}
        </button>
      </div>
    </div>
  );
}
