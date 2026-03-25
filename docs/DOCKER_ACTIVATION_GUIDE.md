# Docker Desktop 활성화 가이드

**작성일**: 2026-03-26
**대상**: Windows 환경에서 Docker Desktop 활성화가 필요한 팀원

---

## 문제 상황

Docker Desktop이 실행되지 않아 다음과 같은 오류가 발생합니다:

```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
The system cannot find the file specified.
```

PostgreSQL 컨테이너가 실행되지 않아 AgriGuard 백엔드가 데이터베이스에 연결할 수 없습니다.

---

## 근본 원인

Windows `WslService`가 **DISABLED** 상태로 설정되어 있습니다:

```powershell
# 확인 방법
Get-Service WslService | Select-Object Name, Status, StartType

# 결과 예시:
# Name       Status  StartType
# ----       ------  ---------
# WslService Stopped Disabled
```

이로 인해 Docker Desktop의 Linux 엔진이 시작할 수 없습니다.

---

## 해결 방법 (4단계)

### 1단계: 관리자 권한 PowerShell 실행

1. Windows 검색창에서 "PowerShell" 입력
2. "Windows PowerShell"을 **우클릭** → "관리자 권한으로 실행" 선택
3. UAC 프롬프트가 나타나면 "예" 클릭

### 2단계: WslService 활성화

```powershell
# WslService를 수동 시작 모드로 변경
Set-Service -Name WslService -StartupType Manual

# 변경 확인
Get-Service WslService | Select-Object Name, Status, StartType
# StartType이 Manual로 변경되었는지 확인
```

### 3단계: 필수 서비스 시작

```powershell
# WslService 시작
Start-Service WslService

# Docker 관련 서비스 시작
Start-Service vmcompute
Start-Service com.docker.service

# 서비스 상태 확인
Get-Service WslService, vmcompute, com.docker.service | Format-Table Name, Status, StartType
```

**예상 출력**:
```
Name                Status  StartType
----                ------  ---------
WslService          Running Manual
vmcompute           Running Automatic
com.docker.service  Running Automatic
```

### 4단계: Docker Desktop 확인

```powershell
# Docker 버전 확인
docker --version

# Docker 컨테이너 목록 확인
docker ps

# AgriGuard PostgreSQL 컨테이너 시작
cd "d:\AI 프로젝트\AgriGuard"
docker compose up -d postgres
```

**예상 출력**:
```
[+] Running 2/2
 ✔ Network agriguard_default      Created
 ✔ Container agriguard-postgres-1 Started
```

---

## 검증

### PostgreSQL 연결 테스트

```powershell
# Python에서 PostgreSQL 연결 테스트
python -c "import psycopg2; conn = psycopg2.connect('postgresql://agriguard:agriguard_secret@localhost:5432/agriguard'); print('✅ PostgreSQL 연결 성공'); conn.close()"
```

### AgriGuard QC 재실행

```powershell
cd "d:\AI 프로젝트"
$env:DATABASE_URL = "postgresql://agriguard:agriguard_secret@localhost:5432/agriguard"
python AgriGuard/backend/scripts/qc_postgres_migration.py --sqlite-db AgriGuard/backend/agriguard.db.resync_candidate_20260325_200555
```

**예상 결과**: `5/5 checks passed`

---

## 문제 해결 (Troubleshooting)

### Q1: "권한이 부족합니다" 오류

**원인**: PowerShell이 관리자 권한으로 실행되지 않았습니다.

**해결**:
- PowerShell을 닫고 "관리자 권한으로 실행"으로 다시 열기

### Q2: `Start-Service WslService` 실패

**에러 메시지**:
```
Start-Service : Service 'Windows Subsystem for Linux (WslService)' cannot be started due to the following error: Cannot start service WslService on computer '.'.
```

**해결**:
1. Windows 기능에서 WSL이 활성화되어 있는지 확인:
   ```powershell
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   ```
2. 시스템 재부팅
3. 재부팅 후 다시 `Start-Service WslService` 실행

### Q3: Docker Desktop이 여전히 시작되지 않음

**해결**:
1. Docker Desktop 애플리케이션을 수동으로 실행:
   - 시작 메뉴 → "Docker Desktop" 클릭
2. Docker Desktop 설정 확인:
   - Settings → General → "Use the WSL 2 based engine" 체크되어 있는지 확인
3. Docker Desktop 재시작:
   - 시스템 트레이 아이콘 우클릭 → "Restart"

### Q4: PostgreSQL 포트 5432가 이미 사용 중

**에러**:
```
Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:5432 -> 0.0.0.0:0: listen tcp 0.0.0.0:5432: bind: An attempt was made to access a socket in a way forbidden by its access permissions.
```

**해결**:
```powershell
# 포트 5432 사용 프로세스 확인
netstat -ano | findstr :5432

# 프로세스 종료 (PID는 위 명령에서 확인)
taskkill /PID <PID> /F

# 또는 다른 포트 사용 (docker-compose.yml 수정)
# ports:
#   - "5433:5432"  # 호스트 포트 5433 사용
```

---

## 영구적 해결 (선택 사항)

매번 수동으로 서비스를 시작하기 싫다면:

### WslService를 자동 시작으로 설정

```powershell
Set-Service -Name WslService -StartupType Automatic
```

**⚠️ 주의**: 시스템 부팅 시 자동으로 WSL이 시작되어 메모리를 더 사용합니다.

### Docker Desktop 자동 시작 설정

1. Docker Desktop 실행
2. Settings → General → "Start Docker Desktop when you log in" 체크
3. Apply & Restart

---

## 다음 단계

Docker가 정상 작동하면:

1. **전체 개발 환경 시작**:
   ```powershell
   cd "d:\AI 프로젝트"
   .\scripts\setup_dev_environment.ps1
   ```

2. **AgriGuard 백엔드 시작**:
   ```powershell
   cd "d:\AI 프로젝트\AgriGuard"
   docker compose up -d
   ```

3. **모니터링 스택 시작** (선택):
   ```powershell
   cd "d:\AI 프로젝트"
   docker compose -f docker-compose.dev.yml --profile monitoring up -d
   ```

---

## 참고 문서

- [DOCKER_SETUP_GUIDE.md](DOCKER_SETUP_GUIDE.md) - Docker Compose 사용법
- [HANDOFF.md](../HANDOFF.md) - 현재 프로젝트 상태
- [TASKS.md](../TASKS.md) - 진행 중인 작업
- [AgriGuard POSTGRES_MIGRATION_QC_REPORT.md](../AgriGuard/POSTGRES_MIGRATION_QC_REPORT.md) - PostgreSQL 마이그레이션 상태

---

**작성자**: Backend Team
**마지막 업데이트**: 2026-03-26
**문의**: 팀 채널에 질문 남기기
