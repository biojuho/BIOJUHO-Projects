import { describe, it, expect } from 'vitest';
import { calculatePrice } from './formatters';

// describe: 연관된 테스트들을 하나의 그룹으로 묶어주는 역할입니다. (예: calculatePrice 함수와 관련된 테스트 모음)
describe('calculatePrice (단위 테스트)', () => {
  // 정상적인 값들이 들어왔을 때의 케이스들을 묶습니다.
  describe('정상 케이스', () => {
    // it: 개별 테스트 케이스 하나를 의미합니다. 우리가 검증하고 싶은 하나의 상황을 적습니다.
    it('일반적인 가격과 할인율이 주어지면 할인된 가격을 반환한다', () => {
      // expect: 결과값을 검증합니다. 
      // calculatePrice(10000, 10)의 결과가 9000이 될 것(toBe)이라고 기대(expect)합니다.
      expect(calculatePrice(10000, 10)).toBe(9000);
    });
    
    it('할인율이 0%일 경우 원래 가격을 그대로 반환한다', () => {
      expect(calculatePrice(5000, 0)).toBe(5000);
    });
    
    it('할인율이 100%일 경우 0을 반환한다', () => {
      expect(calculatePrice(20000, 100)).toBe(0);
    });
  });

  // 엣지 케이스 (Edge Case): 보통 발생하지 않지만 극단적인 값(빈 값, 아주 크거나 작은 값 등)이 들어왔을 때의 상황을 말합니다.
  describe('엣지 케이스', () => {
    it('비정상적인 타입이나 빈 문자열이 들어와도 NaN을 반환해야 한다', () => {
      // toBeNaN(): 결과값이 숫자가 아닌 것(NaN, Not-A-Number)인지 확인합니다.
      expect(calculatePrice('', 10)).toBeNaN();
      expect(calculatePrice('invalid', 10)).toBeNaN();
    });

    it('할인 계산 중 소수점이 발생하는 경계값을 정확하게 처리한다 (반올림)', () => {
      // 9900 * 0.15 = 1485, 9900 - 1485 = 8415
      expect(calculatePrice(9900, 15)).toBe(8415);
      // 100 * 0.33 = 33, 100 - 33 = 67
      expect(calculatePrice(100, 33)).toBe(67);
    });
  });

  describe('에러 케이스', () => {
    it('파라미터로 null이나 undefined가 전달되면 에러를 발생시킨다', () => {
      expect(() => calculatePrice(null, 10)).toThrow('Invalid input');
      expect(() => calculatePrice(1000, undefined)).toThrow('Invalid input');
    });

    it('가격이나 할인율이 음수인 경우 에러를 발생시킨다', () => {
      expect(() => calculatePrice(-1000, 10)).toThrow('Input cannot be negative');
      expect(() => calculatePrice(1000, -10)).toThrow('Input cannot be negative');
    });
  });
});
