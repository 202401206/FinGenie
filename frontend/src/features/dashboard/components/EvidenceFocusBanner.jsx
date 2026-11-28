import React from 'react';

/**
 * Renders an evidence focus banner when query parameters (?documentId=...&sourceRow=...) are active.
 * Never confuses source_row with page index or offset.
 */
export function EvidenceFocusBanner({
  sourceRow = null,
  documentId = null,
  isRowLoaded = false,
  offset = 0,
  limit = 50,
  total = 0,
  isBalanceSheet = false,
  onClearFocus = null
}) {
  if (!sourceRow) return null;

  return (
    <aside className="fg-evidence-focus-banner" role="complementary" aria-label="Evidence Provenance Focus">
      <div className="fg-evidence-focus-icon">🎯</div>
      <div className="fg-evidence-focus-content">
        <h4 className="fg-evidence-focus-title">
          Evidence Focus: Statement Row #{sourceRow}
        </h4>

        {isBalanceSheet ? (
          <p className="fg-evidence-focus-desc">
            This balance sheet calculation references row #{sourceRow} in the uploaded corporate report
            {documentId ? ` (Document: ${documentId})` : ''}. Balance sheets contain instantaneous position data, not transaction logs.
          </p>
        ) : isRowLoaded ? (
          <p className="fg-evidence-focus-desc">
            Matching transaction record located on the current page. The corresponding row is highlighted in gold in the statement ledger below.
          </p>
        ) : (
          <p className="fg-evidence-focus-desc">
            Row #{sourceRow} is outside the currently loaded page (viewing records #{total > 0 ? offset + 1 : 0} to #{Math.min(offset + limit, total)} of {total}).
            Use the ledger pagination controls below to navigate through the statement rows.
          </p>
        )}
      </div>

      {onClearFocus && (
        <button
          type="button"
          className="fg-evidence-clear-btn"
          onClick={onClearFocus}
          aria-label="Dismiss evidence focus"
        >
          Dismiss Focus ✕
        </button>
      )}
    </aside>
  );
}

export default EvidenceFocusBanner;
