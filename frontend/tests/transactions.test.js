import test from 'node:test';
import assert from 'node:assert';
import {
  filterTransactions,
  sortTransactions,
  paginateTransactions,
  calculateFinancialKPIs,
  exportTransactionsCSV
} from '../src/services/transactionService.js';

const SAMPLE_TXS = [
  {
    id: 'tx-1',
    date: '2026-10-24',
    description: 'UPI/Zomato Media Ltd/Order-94821',
    category: 'Dining',
    type: 'debit',
    payment_method: 'UPI',
    amount: 649.00,
    balance: 142350.50,
    source_file: 'HDFC_Statement.csv',
    source_row: 142
  },
  {
    id: 'tx-2',
    date: '2026-10-22',
    description: 'TCS LTD / OCT SALARY / CMS NEFT',
    category: 'Salary',
    type: 'credit',
    payment_method: 'NEFT',
    amount: 125000.00,
    balance: 142999.50,
    source_file: 'HDFC_Statement.csv',
    source_row: 141
  },
  {
    id: 'tx-3',
    date: '2026-10-15',
    description: 'RENT PAYMENT TO LANDLORD S BALAJI',
    category: 'Rent',
    type: 'debit',
    payment_method: 'IMPS',
    amount: 28000.00,
    balance: 45419.50,
    source_file: 'HDFC_Statement.csv',
    source_row: 140
  }
];

test('filterTransactions filters by search keyword', () => {
  const result = filterTransactions(SAMPLE_TXS, { search: 'Zomato' });
  assert.strictEqual(result.length, 1);
  assert.strictEqual(result[0].id, 'tx-1');
});

test('filterTransactions filters by transaction type credit/debit', () => {
  const credits = filterTransactions(SAMPLE_TXS, { type: 'credit' });
  assert.strictEqual(credits.length, 1);
  assert.strictEqual(credits[0].category, 'Salary');

  const debits = filterTransactions(SAMPLE_TXS, { type: 'debit' });
  assert.strictEqual(debits.length, 2);
});

test('filterTransactions filters by category and amount threshold', () => {
  const rentOnly = filterTransactions(SAMPLE_TXS, { category: 'Rent' });
  assert.strictEqual(rentOnly.length, 1);

  const highValue = filterTransactions(SAMPLE_TXS, { minAmount: 10000 });
  assert.strictEqual(highValue.length, 2); // 125000 and 28000
});

test('sortTransactions accurately orders by amount and date', () => {
  const byAmountDesc = sortTransactions(SAMPLE_TXS, { sortBy: 'amount', sortOrder: 'desc' });
  assert.strictEqual(byAmountDesc[0].amount, 125000.00);
  assert.strictEqual(byAmountDesc[2].amount, 649.00);

  const byDateAsc = sortTransactions(SAMPLE_TXS, { sortBy: 'date', sortOrder: 'asc' });
  assert.strictEqual(byDateAsc[0].id, 'tx-3'); // 2026-10-15
});

test('paginateTransactions correctly computes pages and bounds', () => {
  const page1 = paginateTransactions(SAMPLE_TXS, { page: 1, pageSize: 2 });
  assert.strictEqual(page1.items.length, 2);
  assert.strictEqual(page1.totalPages, 2);
  assert.strictEqual(page1.currentPage, 1);

  const page2 = paginateTransactions(SAMPLE_TXS, { page: 2, pageSize: 2 });
  assert.strictEqual(page2.items.length, 1);
});

test('calculateFinancialKPIs preserves mathematical integrity', () => {
  const kpis = calculateFinancialKPIs(SAMPLE_TXS);
  assert.strictEqual(kpis.totalCredits, 125000.00);
  assert.strictEqual(kpis.totalDebits, 28649.00);
  assert.strictEqual(kpis.netCashFlow, 96351.00);
  assert.strictEqual(kpis.transactionCount, 3);
  assert.strictEqual(kpis.largestExpense, 28000.00);
});

test('exportTransactionsCSV produces valid tabular CSV string', () => {
  const csv = exportTransactionsCSV(SAMPLE_TXS);
  assert.ok(csv.includes('Date,Description,Category,Type,Payment Method,Amount (INR),Balance (INR)'));
  assert.ok(csv.includes('125000.00'));
  assert.ok(csv.includes('Zomato Media Ltd'));
});
