import { FileText, Tag, Package } from "@phosphor-icons/react";
import { useState, useEffect } from "react";

// UNSPSC code lookup - loaded once and cached
let unspscCache: Record<string, string> | null = null;
async function getUnspscLookup(): Promise<Record<string, string>> {
  if (unspscCache) return unspscCache;
  try {
    const resp = await fetch("/unspsc_codes.json");
    unspscCache = await resp.json();
    return unspscCache!;
  } catch {
    return {};
  }
}

function resolveUnspsc(code: string, lookup: Record<string, string>): string {
  if (lookup[code]) return lookup[code];
  for (const prefixLen of [6, 4]) {
    const parent = code.slice(0, prefixLen) + "0".repeat(8 - prefixLen);
    if (lookup[parent]) return lookup[parent];
  }
  return code;
}

const capitalize = (s: string | null) =>
  s ? s.charAt(0).toUpperCase() + s.slice(1) : "";

interface TenderNoticeBodyProps {
  tender: {
    description: string | null;
    procurement_method: string | null;
    category_primary: string | null;
    gsin: string | null;
    unspsc: string | null;
    delivery_location: string | null;
  };
  compact?: boolean;
}

export function TenderNoticeBody({
  tender,
  compact = false,
}: TenderNoticeBodyProps) {
  const [unspscLookup, setUnspscLookup] = useState<Record<string, string>>({});
  useEffect(() => {
    getUnspscLookup().then(setUnspscLookup);
  }, []);

  if (compact) {
    return (
      <div className="w-full bg-surface border border-border rounded-lg p-4">
        <h3 className="text-lg font-semibold text-text mb-3 flex items-center gap-2">
          <FileText className="w-4 h-4" />
          Description
        </h3>
        <div className="text-sm text-text mb-4">
          {tender.description ? (
            <p className="whitespace-pre-wrap line-clamp-4">{tender.description}</p>
          ) : (
            <p className="italic text-text-muted">No description provided</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Description */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-text mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Description
        </h2>
        <div className="text-sm leading-relaxed text-text">
          {tender.description ? (
            <p className="whitespace-pre-wrap">{tender.description}</p>
          ) : (
            <p className="italic text-text-muted">No description provided</p>
          )}
        </div>
      </div>

      {/* Procurement Details */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-text mb-4 flex items-center gap-2">
          <Tag className="w-5 h-5" />
          Procurement Details
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide">Method</label>
            <p className="text-sm text-text mt-0.5">{tender.procurement_method || "Not specified"}</p>
          </div>
          <div>
            <label className="text-xs font-medium text-text-muted uppercase tracking-wide">Category</label>
            <p className="text-sm text-text mt-0.5">{capitalize(tender.category_primary) || "Not specified"}</p>
          </div>
          {tender.delivery_location && (
            <div className="sm:col-span-2">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wide">Delivery Region</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {tender.delivery_location.split(",").map((region) => (
                  <span
                    key={region.trim()}
                    className="px-2 py-0.5 bg-surface-muted text-text-muted text-xs rounded-md border border-border"
                  >
                    {region.trim()}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* UNSPSC Commodity Codes */}
      {tender.unspsc && (
        <div className="bg-surface border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold text-text mb-4 flex items-center gap-2">
            <Package className="w-5 h-5" />
            Commodity Codes
          </h2>
          <div className="space-y-2">
            {tender.unspsc.split(",").map((code) => {
              const trimmed = code.trim();
              const desc = resolveUnspsc(trimmed, unspscLookup);
              return (
                <div key={trimmed} className="flex items-center gap-3">
                  <span className="px-2 py-0.5 bg-primary/10 text-primary text-xs rounded-md border border-primary/20 font-mono shrink-0">
                    {trimmed}
                  </span>
                  {desc !== trimmed && (
                    <span className="text-sm text-text">{desc}</span>
                  )}
                </div>
              );
            })}
          </div>
          {tender.gsin && (
            <div className="mt-4 pt-3 border-t border-border">
              <label className="text-xs font-medium text-text-muted uppercase tracking-wide">GSIN</label>
              <p className="text-sm text-text mt-0.5 font-mono">{tender.gsin}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
