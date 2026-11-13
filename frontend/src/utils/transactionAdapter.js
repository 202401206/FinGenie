/**
 * Backend Transaction Contract Display Adapter
 * Expected backend fields: id, document_id, date, description, debit, credit, balance, source_row
 */

export function adaptTransaction(raw = {}, documentMetadata = {}) {
  const debit = raw.debit !== null && raw.debit !== undefined ? Number(raw.debit) : null;
  const credit = raw.credit !== null && raw.credit !== undefined ? Number(raw.credit) : null;

  const isCredit = credit !== null && credit > 0 && (debit === null || debit === 0);
  const amount = isCredit ? credit : (debit !== null ? debit : 0);
  const type = isCredit ? 'credit' : 'debit';

  return {
    id: String(raw.id || `tx-${raw.source_row || Math.random()}`),
    document_id: raw.document_id || documentMetadata.id || 'unknown-document',
    source_file: raw.source_file || documentMetadata.filename || documentMetadata.file_name || 'Uploaded Document',
    source_row: raw.source_row !== null && raw.source_row !== undefined ? raw.source_row : '—',
    date: raw.date || '',
    description: raw.description || 'No description available',
    category: raw.category || 'Unknown',
    payment_method: raw.payment_method || raw.channel || 'Unknown',
    currency: raw.currency || documentMetadata.currency || 'INR',
    debit,
    credit,
    balance: raw.balance !== null && raw.balance !== undefined ? Number(raw.balance) : null,
    amount,
    type,
    ai_inferred: Boolean(raw.ai_inferred)
  };
}

export function adaptTransactionList(rawList = [], documentMetadata = {}) {
  if (!Array.isArray(rawList)) return [];
  return rawList.map(item => adaptTransaction(item, documentMetadata));
}
