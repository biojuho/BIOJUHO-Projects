# Implement OpenAI/Gemini Batch API for Cost Optimization

**Labels**: `enhancement`, `cost-optimization`, `backend`
**Priority**: 🔥 **High** - 2주 내 완료

---

## Description

OpenAI와 Gemini Batch API를 통합하여 비동기 작업의 비용을 50% 절감합니다.

---

## Current Cost Analysis (30일)

| Provider | Calls | Cost | Percentage |
|----------|-------|------|------------|
| **Claude Sonnet 4** | 1,245 | $3.80 | 94% |
| **DeepSeek** | 890 | $0.18 | 4% |
| **Others** | 367 | $0.08 | 2% |
| **Total** | 2,502 | **$4.06** | 100% |

---

## Potential Savings

### Batch API Pricing

| Provider | Real-time | Batch | Discount |
|----------|-----------|-------|----------|
| **OpenAI** | $2.50/1M input | $1.25/1M | **50% off** |
| **Gemini** | $0.075/1M input | $0.0375/1M | **50% off** |

### 예상 절감액

- 백그라운드 작업 비율: **50%** (DailyNews 콘텐츠 생성, 벡터 임베딩 등)
- 월간 Batch 가능 비용: $2.03
- **예상 절감**: **$1.00~$1.50/월** (Batch 전환 시)
- **연간 절감**: **$12~$18**

---

## Tasks

### Phase 1: API 클라이언트 구현 (Week 1)

- [ ] OpenAI Batch API 클라이언트 구현
- [ ] Gemini Batch API 클라이언트 구현
- [ ] `shared/llm/batch.py` 모듈 생성
- [ ] Batch 작업 큐잉 로직 구현
- [ ] Batch 결과 폴링 및 재시도 로직

### Phase 2: 통합 및 테스트 (Week 2)

- [ ] 비동기 작업 식별 (DailyNews, 벡터 임베딩 등)
- [ ] 기존 코드에 Batch 모드 통합
- [ ] 비용 추적 업데이트 (`cost_intelligence.py`)
- [ ] 단위 테스트 작성
- [ ] 1주일 A/B 테스트 (Batch vs 실시간)

---

## Implementation

### `shared/llm/batch.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict
import asyncio

class BatchClient(ABC):
    """Batch API 추상 클래스"""

    @abstractmethod
    async def submit_batch(self, requests: List[dict]) -> str:
        """
        Batch 작업 제출

        Args:
            requests: API 요청 리스트

        Returns:
            batch_id: Batch 작업 ID
        """
        pass

    @abstractmethod
    async def check_batch(self, batch_id: str) -> dict:
        """
        Batch 상태 확인

        Returns:
            {"status": "completed|failed|in_progress", "progress": 0-100}
        """
        pass

    @abstractmethod
    async def retrieve_batch(self, batch_id: str) -> List[dict]:
        """
        완료된 Batch 결과 가져오기

        Returns:
            results: API 응답 리스트
        """
        pass


class OpenAIBatchClient(BatchClient):
    """OpenAI Batch API 클라이언트"""

    def __init__(self, api_key: str):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key)

    async def submit_batch(self, requests: List[dict]) -> str:
        # JSONL 파일 생성
        import tempfile
        import json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for req in requests:
                f.write(json.dumps(req) + '\n')
            file_path = f.name

        # 파일 업로드
        with open(file_path, 'rb') as f:
            file_obj = await self.client.files.create(
                file=f,
                purpose='batch'
            )

        # Batch 제출
        batch = await self.client.batches.create(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )

        return batch.id

    async def check_batch(self, batch_id: str) -> dict:
        batch = await self.client.batches.retrieve(batch_id)
        return {
            "status": batch.status,
            "progress": batch.request_counts.completed / batch.request_counts.total * 100
        }

    async def retrieve_batch(self, batch_id: str) -> List[dict]:
        batch = await self.client.batches.retrieve(batch_id)
        if batch.status != "completed":
            raise ValueError(f"Batch {batch_id} not completed yet")

        # 결과 파일 다운로드
        file_response = await self.client.files.content(batch.output_file_id)
        results = []
        for line in file_response.text.split('\n'):
            if line.strip():
                results.append(json.loads(line))
        return results


class GeminiBatchClient(BatchClient):
    """Gemini Batch API 클라이언트"""

    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.client = genai

    async def submit_batch(self, requests: List[dict]) -> str:
        # Gemini Batch API 구현 (문서 확인 필요)
        raise NotImplementedError("Gemini Batch API 구현 필요")

    async def check_batch(self, batch_id: str) -> dict:
        raise NotImplementedError("Gemini Batch API 구현 필요")

    async def retrieve_batch(self, batch_id: str) -> List[dict]:
        raise NotImplementedError("Gemini Batch API 구현 필요")
```

---

## Usage Example

### DailyNews 콘텐츠 생성 (Batch 모드)

```python
from shared.llm.batch import OpenAIBatchClient

# 1. Batch 요청 준비
requests = [
    {
        "custom_id": f"tweet-{i}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a tweet writer."},
                {"role": "user", "content": f"Write a tweet about: {topic}"}
            ]
        }
    }
    for i, topic in enumerate(topics)
]

# 2. Batch 제출
batch_client = OpenAIBatchClient(api_key=os.getenv("OPENAI_API_KEY"))
batch_id = await batch_client.submit_batch(requests)
print(f"Batch submitted: {batch_id}")

# 3. 상태 폴링 (24시간 이내 완료)
while True:
    status = await batch_client.check_batch(batch_id)
    if status["status"] == "completed":
        break
    print(f"Progress: {status['progress']}%")
    await asyncio.sleep(60)  # 1분마다 확인

# 4. 결과 가져오기
results = await batch_client.retrieve_batch(batch_id)
for result in results:
    print(result['response']['body']['choices'][0]['message']['content'])
```

---

## Cost Tracking Update

### `scripts/cost_intelligence.py` 수정

```python
# 기존
cost_by_provider = {
    "claude": 3.80,
    "deepseek": 0.18,
    # ...
}

# 추가
cost_by_mode = {
    "realtime": 2.03,  # 실시간 API
    "batch": 1.01,     # Batch API (50% 할인)
}

savings = cost_by_mode["realtime"] * 0.5 - cost_by_mode["batch"]
print(f"Batch API 절감액: ${savings:.2f}")
```

---

## A/B Testing Plan

### Week 1: Baseline (실시간 API)
- DailyNews 콘텐츠 생성 100건
- 비용 측정

### Week 2: Batch API
- 동일 작업을 Batch API로 실행
- 비용 측정
- 지연시간 측정 (24시간 이내 완료)

### 성공 기준
- ✅ Batch API 비용이 실시간 API보다 **40% 이상 저렴**
- ✅ 오류율 < **5%**
- ✅ 24시간 이내 **95% 완료**

---

## Acceptance Criteria

- ✅ `shared/llm/batch.py` 모듈 구현 완료
- ✅ OpenAI Batch API 통합 완료
- ✅ Gemini Batch API 통합 완료 (또는 문서화된 이유로 보류)
- ✅ DailyNews에 Batch 모드 적용
- ✅ 1주일 A/B 테스트 완료 (비용 40% 이상 절감 확인)
- ✅ `cost_intelligence.py` 리포트에 Batch 비용 별도 표시
- ✅ 문서화 (API 사용법, 비용 비교)

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **24시간 지연** | 실시간 응답 불가 | 실시간/Batch 하이브리드 전략 |
| **Batch 실패** | 비용 손실 | 재시도 로직 + 실시간 폴백 |
| **API 변경** | 코드 수정 필요 | 버전 고정 + 모니터링 |

---

## API References

- [OpenAI Batch API](https://platform.openai.com/docs/guides/batch)
- [Gemini Batch API](https://ai.google.dev/gemini-api/docs/batch)

---

**Estimated Time**: 5-7일
**Blockers**: Gemini Batch API 문서 확인 필요
**Next Steps**: Cost Intelligence Dashboard (향후)
