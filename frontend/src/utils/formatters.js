/**
 * Indian Financial Formatters
 * Handles INR currency, Lakh/Crore numbering conventions, and dates
 */

/**
 * Formats a number to Indian Rupee (INR) representation
 * Example: 125000 -> "₹1,25,000.00"
 * Example: 15000000 -> "₹1,50,00,000.00"
 */
export function formatINR(amount, options = {}) {
  const { includeDecimals = true, showSign = false } = options;

  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return '₹0.00';
  }

  const num = Number(amount);
  const isNegative = num < 0;
  const absNum = Math.abs(num);

  const [integerPart, decimalPart] = absNum.toFixed(2).split('.');

  // Indian numbering grouping: 3 digits for first group from right, then 2 digits for preceding groups
  let lastThree = integerPart.substring(integerPart.length - 3);
  const otherNumbers = integerPart.substring(0, integerPart.length - 3);

  if (otherNumbers !== '') {
    lastThree = ',' + lastThree;
  }

  const formattedInteger = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree;

  let result = `₹${formattedInteger}`;
  if (includeDecimals) {
    result += `.${decimalPart}`;
  }

  if (isNegative) {
    return `-${result}`;
  }
  if (showSign && num > 0) {
    return `+${result}`;
  }

  return result;
}

/**
 * Formats large amounts into compact Indian currency strings (Lakhs and Crores)
 * Example: 125000 -> "₹1.25 L"
 * Example: 15000000 -> "₹1.50 Cr"
 */
export function formatCompactINR(amount) {
  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return '₹0';
  }

  const num = Number(amount);
  const abs = Math.abs(num);
  const prefix = num < 0 ? '-' : '';

  if (abs >= 10000000) {
    return `${prefix}₹${(abs / 10000000).toFixed(2)} Cr`;
  }
  if (abs >= 100000) {
    return `${prefix}₹${(abs / 100000).toFixed(2)} L`;
  }
  if (abs >= 1000) {
    return `${prefix}₹${(abs / 1000).toFixed(1)} K`;
  }

  return `${prefix}₹${abs.toFixed(0)}`;
}

/**
 * Formats standard ISO date strings (YYYY-MM-DD) into readable Indian banking format
 * Example: "2026-10-24" -> "24 Oct 2026"
 */
export function formatDate(dateString) {
  if (!dateString) return '—';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString;

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const day = String(date.getDate()).padStart(2, '0');
  const month = months[date.getMonth()];
  const year = date.getFullYear();

  return `${day} ${month} ${year}`;
}

/**
 * Parses numeric currency strings back into raw numbers
 */
export function parseINR(str) {
  if (typeof str === 'number') return str;
  if (!str) return 0;
  const clean = str.replace(/[₹,\s]/g, '');
  const val = parseFloat(clean);
  return isNaN(val) ? 0 : val;
}
