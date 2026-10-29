/**
 * Safe Financial Formatters for Indian Banking & Multi-Currency Standards
 */

export function formatCurrency(amount, currency = 'INR', options = {}) {
  const { includeDecimals = true, showSign = false } = options;

  if (amount === null || amount === undefined || isNaN(Number(amount))) {
    return '—';
  }

  const num = Number(amount);
  const isNegative = num < 0;
  const absNum = Math.abs(num);

  const [integerPart, decimalPart] = absNum.toFixed(2).split('.');

  let formattedInteger;
  if (currency === 'INR') {
    let lastThree = integerPart.substring(integerPart.length - 3);
    const otherNumbers = integerPart.substring(0, integerPart.length - 3);
    if (otherNumbers !== '') {
      lastThree = ',' + lastThree;
    }
    formattedInteger = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + lastThree;
  } else {
    formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }

  const symbol = currency === 'INR' ? '₹' : `${currency} `;
  let result = `${symbol}${formattedInteger}`;
  if (includeDecimals) {
    result += `.${decimalPart}`;
  }

  if (isNegative) return `-${result}`;
  if (showSign && num > 0) return `+${result}`;
  return result;
}

export function formatBalance(balance, currency = 'INR') {
  if (balance === null || balance === undefined || balance === '') {
    return '—';
  }
  return formatCurrency(balance, currency);
}

export function formatDate(dateString) {
  if (!dateString) return '—';
  
  if (typeof dateString === 'string' && /^\d{4}-\d{2}-\d{2}/.test(dateString)) {
    const [year, month, day] = dateString.substring(0, 10).split('-').map(Number);
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${String(day).padStart(2, '0')} ${months[month - 1]} ${year}`;
  }

  const date = new Date(dateString);
  if (isNaN(date.getTime())) return String(dateString);
  return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
