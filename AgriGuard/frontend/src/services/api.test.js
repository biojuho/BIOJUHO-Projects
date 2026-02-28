import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { productApi } from './api';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002';

// MSW (Mock Service Worker): 백엔드 서버가 아직 없거나 테스트 환경일 때,
// 프론트엔드에서 보내는 웹 요청을 중간에 가로채서 백엔드인 척 가짜 응답을 내려주는 환상적인 도구입니다.
// 핸들러(handlers) 셋업: "만약 이 주소로 GET 요청이 오면 이렇게 응답해줄게!" 라고 규칙을 정의합니다.
const handlers = [
  http.get(`${API_URL}/products/:id`, ({ params }) => {
    const { id } = params;
    
    // 성공 케이스
    if (id === '1') {
      return HttpResponse.json({ id: '1', title: 'Success Product' }, { status: 200 });
    }
    // 유효성 검사 실패 케이스
    if (id === 'invalid') {
      return HttpResponse.json({ message: 'Invalid ID format' }, { status: 400 });
    }
    // 서버 에러 케이스
    return HttpResponse.json({ message: 'Internal Server Error' }, { status: 500 });
  })
];

// 정의한 핸들러(규칙)들을 바탕으로 가짜 서버를 만듭니다.
const server = setupServer(...handlers);

// beforeAll: 보통 테스트 파일 맨 처음에, 모든 테스트가 시작되기 전 딱 한 번 실행됩니다. (가짜 서버 켜기)
beforeAll(() => server.listen());

// afterEach: 각각의 테스트 블록(it)이 하나 끝날 때마다 실행됩니다. 
// (테스트끼리 서로 영향을 주지 않도록 가짜 서버의 핸들러 상태를 중간중간 초기화 해줍니다)
afterEach(() => server.resetHandlers());

// afterAll: 모든 테스트가 다 끝나고 나서 마지막에 딱 한 번 실행됩니다. (가짜 서버 끄기)
afterAll(() => server.close());

describe('productApi API 테스트', () => {
  // 1. 200 성공 응답
  it('요청이 성공하면 200 응답과 함께 올바른 데이터를 반환한다', async () => {
    const response = await productApi.getById('1');
    expect(response.status).toBe(200);
    expect(response.data.title).toBe('Success Product');
  });

  // 2. 400 유효성 검사 실패
  it('잘못된 파라미터를 보내면 400 에러를 반환해야 한다', async () => {
    try {
      await productApi.getById('invalid');
      // Should not reach here
      expect(true).toBe(false);
    } catch (error) {
      expect(error.response.status).toBe(400);
      expect(error.response.data.message).toBe('Invalid ID format');
    }
  });

  // 3. 500 서버 에러 케이스
  it('서버에서 문제가 발생하면 500 에러를 반환해야 한다', async () => {
    try {
      await productApi.getById('error_trigger');
      // Should not reach here
      expect(true).toBe(false);
    } catch (error) {
      expect(error.response.status).toBe(500);
      expect(error.response.data.message).toBe('Internal Server Error');
    }
  });
});
