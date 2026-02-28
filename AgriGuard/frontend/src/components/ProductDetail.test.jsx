import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ProductDetail from './ProductDetail';
import { productApi } from '../services/api';

// vi.mock (모킹/Mocking): 실제 API 서버로 진짜 요청을 보내지 않고, 
// 테스트용 가짜(Mock) 함수를 만들어서 우리가 원하는 가짜 응답을 주도록 흉내 내는 설정입니다.
vi.mock('../services/api', () => ({
  productApi: {
    getById: vi.fn(), // vi.fn(): 지금은 아무 동작도 하지 않는 가짜 껍데기 함수를 생성합니다.
    getHistory: vi.fn(),
    addTracking: vi.fn(),
    addCertification: vi.fn()
  }
}));

const renderWithRouter = (ui, { route = '/product/1' } = {}) => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/product/:id" element={ui} />
      </Routes>
    </MemoryRouter>
  );
};

const mockProduct = {
  id: '1',
  name: 'Organic Apples',
  category: 'Fruit',
  origin: 'Seoul Farm',
  qr_code: 'QR-12345',
  requires_cold_chain: true,
  description: 'Fresh organic apples'
};

const mockHistory = [
  { 
    block: 1, 
    data: { action: 'REGISTERED', location: 'Farm' }, 
    timestamp: new Date().toISOString(),
    tx_hash: '0x1234567890'
  }
];

describe('ProductDetail 컴포넌트', () => {
  // beforeEach: 각각의 테스트(it)가 하나씩 실행되기 직전에 매번 실행되는 코드입니다.
  // 여기서는 이전 테스트에서 사용했던 가짜 함수(Mock)들의 기록을 깔끔하게 지워줍니다. (독립적인 테스트 환경 구성)
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 1. 렌더링 확인 (Success state)
  it('상품 정보가 주어졌을 때 화면에 정상적으로 렌더링된다', async () => {
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });

    // renderWithRouter: 컴포넌트를 테스트용 가상 화면(DOM)에 그리는(렌더링) 역할을 합니다.
    renderWithRouter(<ProductDetail />);
    
    // Shows loading initially
    // screen.queryByRole: 가상 화면(screen)에서 특정 요소를 찾습니다.
    // toBeNull(): 요소가 화면에 없어야 함을 의미합니다. (로딩 중에는 다른 버튼들이 안 보여야 함)
    expect(screen.queryByRole('button', { hidden: true })).toBeNull(); 

    // waitFor: 데이터 로딩 등 비동기 작업이 끝날 때까지 기다려주는 함수입니다.
    await waitFor(() => {
      // toBeInTheDocument(): 가상 화면(Document) 안에 해당 텍스트나 요소가 존재하는지 확인합니다.
      expect(screen.getByText('Organic Apples')).toBeInTheDocument();
      expect(screen.getByText('Seoul Farm')).toBeInTheDocument();
      // Ensure specific buttons are rendered
      expect(screen.getByRole('button', { name: /Add Tracking Event/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Add Certification/i })).toBeInTheDocument();
    });
  });

  // 2. 버튼 클릭 이벤트
  it('Add Tracking Event 버튼 클릭 시 폼이 표시된다', async () => {
    productApi.getById.mockResolvedValueOnce({ data: mockProduct });
    productApi.getHistory.mockResolvedValueOnce({ data: { history: mockHistory } });

    renderWithRouter(<ProductDetail />);

    await waitFor(() => {
      expect(screen.getByText('Organic Apples')).toBeInTheDocument();
    });

    // 폼은 처음에 보이지 않아야 함
    expect(screen.queryByPlaceholderText(/Location/i)).not.toBeInTheDocument();

    // 버튼 클릭
    const trackingBtn = screen.getByRole('button', { name: /Add Tracking Event/i });
    fireEvent.click(trackingBtn);

    // 폼이 표시되는지 확인
    expect(screen.getByPlaceholderText(/Location/i)).toBeInTheDocument();
  });

  // 3. props가 없을 때 fallback UI 확인 (Not found state)
  // Fallback UI란?: 에러가 나거나 화면에 그릴 데이터가 없을 때, 화면이 하얗게 멈춰버리지 않고 
  // 대신 안전하게 보여주는 '대체 화면' (예: 404 Not Found 안내 페이지)을 의미합니다.
  it('상품 데이터를 불러오지 못하면 빈 화면 또는 Not Found fallback UI를 렌더링한다', async () => {
    // 가짜 함수가 에러를 뱉어내도록(Rejected) 설정합니다.
    productApi.getById.mockRejectedValueOnce(new Error('Not Found'));
    productApi.getHistory.mockRejectedValueOnce(new Error('Not Found'));

    renderWithRouter(<ProductDetail />);

    await waitFor(() => {
      expect(screen.getByText('Product Not Found')).toBeInTheDocument();
      expect(screen.getByText(/Back to Dashboard/i)).toBeInTheDocument();
      // 구매 버튼이나 트래킹 폼 관련 버튼은 화면에 없어야 함
      expect(screen.queryByRole('button', { name: /Add Tracking Event/i })).not.toBeInTheDocument();
    });
  });
});
