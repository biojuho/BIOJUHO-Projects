/** // d:\AI 프로젝트\AgriGuard\frontend\src\utils\formatters.js
 * Calculates the final price after discount.
 * @param {number} price - Original price
 * @param {number} discountRate - Discount percentage (0-100)
 * @returns {number} Final price
 */
export const calculatePrice = (price, discountRate) => {
  if (price === null || price === undefined || discountRate === null || discountRate === undefined) {
    throw new Error('Invalid input');
  }

  if (price === '' || discountRate === '') {
    return NaN;
  }

  const numPrice = Number(price);
  const numDiscount = Number(discountRate);

  if (Number.isNaN(numPrice) || Number.isNaN(numDiscount)) {
    return NaN;
  }

  if (numPrice < 0 || numDiscount < 0) {
    throw new Error('Input cannot be negative');
  }

  const discountAmount = numPrice * (numDiscount / 100);
  return Math.round(numPrice - discountAmount);
};

/**
 * Formats moisture level to strictly 1 decimal place with percentage.
 * @param {number|string} level - Moisture level
 * @returns {string} Formatted string e.g. "45.2%"
 */
export const formatMoisture = (level) => {
  if (level === null || level === undefined) return 'N/A';
  const num = Number(level);
  return Number.isNaN(num) ? 'N/A' : `${num.toFixed(1)}%`;
};

/**
 * Formats ISO date string to a readable format.
 * @param {string} isoString - Date string like "2026-02-24T09:00:00Z"
 * @returns {string} Localized date string
 */
export const formatDate = (isoString) => {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    return date.toLocaleString();
  } catch (error) {
    console.warn('Date formatting error:', error);
    return isoString;
  }
};

/**
 * Formats critical alert count.
 * @param {number} count - Number of alerts
 * @returns {string} Feedback string
 */
export const formatAlert = (count) => {
  if (!count) return 'Healthy (0 Alerts)';
  return `${count} Critical Alert${count > 1 ? 's' : ''}`;
};
