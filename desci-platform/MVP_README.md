# Regulatory Collaboration MVP

## 로컬 실행 방법

### 1) 백엔드 (FastAPI + SQLite)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2) 프론트엔드 (Next.js)

```bash
cd mvp-frontend
npm install
npm run dev
```

기본적으로 프론트는 `http://localhost:3000`, 백엔드는 `http://localhost:8000`으로 통신합니다.

### 3) 환경 변수 (선택)

`mvp-frontend/.env.local`
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

`backend/.env`
```
ALLOWED_ORIGINS=http://localhost:3000
```
