/**
 * FinGenie Transaction History & Ledger Service
 * High-performance querying, multi-parameter filtering, and financial KPI computation
 */

import { mockDb } from '../lib/supabaseClient.js';

export const TRANSACTION_CATEGORIES = [
  'All Categories',
  'Salary',
  'Investments',
  'Rent',
  'Dining',
  'Groceries',
  'Utilities',
  'Consulting',
  'Cash',
  'Shopping',
  'Medical',
  'Transfer'
];

export const PAYMENT_METHODS = [
  'All Methods',
  'UPI',
  'NEFT',
  'IMPS',
  'RTGS',
  'Card',
  'ATM',
  'NetBanking'
];

/**
 * Filter transactions by search query, credit/debit type, category, date, and amount range
 */
export function filterTransactions(transactions, filters = {}) {
  const {
    search = '',
    type = 'all',
    category = 'all',
    paymentMethod = 'all',
    dateFrom = null,
    dateTo = null,
    minAmount = null,
    maxAmount = null
  } = filters;

  return transactions.filter(tx => {
    // 1. Text Search across description, category, and payment method
    if (search && search.trim() !== '') {
      const q = search.toLowerCase().trim();
      const match = 
        tx.description.toLowerCase().includes(q) ||
        tx.category.toLowerCase().includes(q) ||
        tx.payment_method.toLowerCase().includes(q) ||
        String(tx.amount).includes(q);
      if (!match) return false;
    }

    // 2. Type Filter (credit vs debit)
    if (type && type !== 'all' && tx.type !== type) {
      return false;
    }

    // 3. Category Filter
    if (category && category !== 'all' && category !== 'All Categories') {
      if (tx.category.toLowerCase() !== category.toLowerCase()) {
        return false;
      }
    }

    // 4. Payment Method Filter
    if (paymentMethod && paymentMethod !== 'all' && paymentMethod !== 'All Methods') {
      if (tx.payment_method.toUpperCase() !== paymentMethod.toUpperCase()) {
        return false;
      }
    }

    // 5. Date Range Filter
    if (dateFrom) {
      if (new Date(tx.date) < new Date(dateFrom)) return false;
    }
    if (dateTo) {
      if (new Date(tx.date) > new Date(dateTo)) return false;
    }

    // 6. Amount Range Filter
    if (minAmount !== null && minAmount !== undefined && minAmount !== '') {
      if (tx.amount < Number(minAmount)) return false;
    }
    if (maxAmount !== null && maxAmount !== undefined && maxAmount !== '') {
      if (tx.amount > Number(maxAmount)) return false;
    }

    return true;
  });
}

/**
 * Sort transactions by date or amount in ascending or descending order
 */
export function sortTransactions(transactions, { sortBy = 'date', sortOrder = 'desc' } = {}) {
  const sorted = [...transactions];
  sorted.sort((a, b) => {
    let comparison = 0;
    if (sortBy === 'date') {
      comparison = new Date(a.date).getTime() - new Date(b.date).getTime();
    } else if (sortBy === 'amount') {
      comparison = a.amount - b.amount;
    }

    return sortOrder === 'desc' ? -comparison : comparison;
  });
  return sorted;
}

/**
 * Paginate transaction dataset
 */
export function paginateTransactions(transactions, { page = 1, pageSize = 5 } = {}) {
  const totalItems = transactions.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const currentPage = Math.min(Math.max(1, page), totalPages);

  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const items = transactions.slice(startIndex, endIndex);

  return {
    items,
    totalItems,
    totalPages,
    currentPage,
    pageSize
  };
}

/**
 * Compute aggregated Financial KPIs from transaction set
 */
export function calculateFinancialKPIs(transactions) {
  let totalCredits = 0;
  let totalDebits = 0;
  let largestExpense = 0;
  const categoryMap = {};

  transactions.forEach(tx => {
    const amt = Number(tx.amount) || 0;
    if (tx.type === 'credit') {
      totalCredits += amt;
    } else if (tx.type === 'debit') {
      totalDebits += amt;
      if (amt > largestExpense) {
        largestExpense = amt;
      }
      categoryMap[tx.category] = (categoryMap[tx.category] || 0) + amt;
    }
  });

  const netCashFlow = totalCredits - totalDebits;

  return {
    totalCredits,
    totalDebits,
    netCashFlow,
    transactionCount: transactions.length,
    largestExpense,
    categoryMap
  };
}

/**
 * Export filtered transactions to CSV string
 */
export function exportTransactionsCSV(transactions) {
  const headers = ['Date', 'Description', 'Category', 'Type', 'Payment Method', 'Amount (INR)', 'Balance (INR)', 'Source Reference'];
  const rows = transactions.map(tx => [
    tx.date,
    `"${tx.description.replace(/"/g, '""')}"`,
    tx.category,
    tx.type.toUpperCase(),
    tx.payment_method,
    tx.amount.toFixed(2),
    tx.balance ? tx.balance.toFixed(2) : 'N/A',
    `"${tx.source_file} (Row ${tx.source_row})"`
  ]);

  return [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
}

/**
 * Fetch transactions for user (with mock or live Supabase)
 */
export async function getTransactions(userId = 'usr-fingenie-demo-001') {
  return mockDb.transactions.filter(tx => tx.user_id === userId);
}
