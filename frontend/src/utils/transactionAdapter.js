/**
 * Backend Transaction Contract Display Adapter
 * Expected backend fields: id, document_id, date, description, debit, credit, balance, source_row
 * Document metadata fields: id, status, original_filename, currency, period_start, period_end
 */

export function adaptTransaction(raw = {}, documentMetadata = {}) {
  const debit = raw.debit !== null && raw.debit !== undefined ? Number(raw.debit) : null;
  const credit = raw.credit !== null && raw.credit !== undefined ? Number(raw.credit) : null;

  const isCredit = credit !== null && credit > 0 && (debit === null || debit === 0);
  const amount = isCredit ? credit : (debit !== null ? debit : 0);
  const type = isCredit ? 'credit' : 'debit';

  // Do NOT invent INR if currency is null/missing
  const currency = documentMetadata.currency !== undefined && documentMetadata.currency !== null
    ? documentMetadata.currency
    : (raw.currency !== undefined && raw.currency !== null ? raw.currency : null);

  // Filename: backend field is `original_filename`
  const source_file = documentMetadata.original_filename || raw.source_file || 'document';

  return {
    id: String(raw.id || `tx-${raw.source_row || Math.random()}`),
    document_id: String(raw.document_id || documentMetadata.id || ''),
    source_file,
    source_row: raw.source_row !== null && raw.source_row !== undefined ? raw.source_row : '—',
    date: raw.date || '',
    description: String(raw.description || 'No description available'),
    currency,
    debit,
    credit,
    balance: raw.balance !== null && raw.balance !== undefined ? Number(raw.balance) : null,
    amount,
    type
  };
}

export function adaptTransactionList(rawList = [], documentMetadata = {}) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(item => adaptTransaction(item, documentMetadata));
}
