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
