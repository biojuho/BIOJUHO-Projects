# 🚀 Quick Fix: Docker WSL Service (2분 소요)

**문제**: WslService가 비활성화되어 Docker가 시작되지 않습니다.

---

## ⚡ 빠른 해결 방법 (추천)

### 방법 1: 한 줄 명령어 (가장 빠름)

**1단계**: 다음 버튼을 눌러주세요:
- `Win + X` 키 → **"터미널 (관리자)"** 또는 **"PowerShell (관리자)"** 클릭
- UAC 프롬프트에서 **"예"** 클릭

**2단계**: 아래 명령어를 복사해서 붙여넣고 Enter:

```powershell
Set-Service -Name WslService -StartupType Manual; Start-Service WslService; Start-Service vmcompute; Start-Service com.docker.service; docker version
```

**3단계**: 출력에서 `Server:` 섹션이 보이면 성공! ✅

---

### 방법 2: GUI로 수정 (명령어 없이)

**1단계**: `Win + R` → `services.msc` 입력 → Enter

**2단계**: 다음 서비스를 찾아서 각각:
1. **Windows Subsystem for Linux** (WslService)
   - 더블클릭 → **시작 유형**을 **"수동"**으로 변경
   - **시작** 버튼 클릭 → **확인**

2. **Hyper-V Host Compute Service** (vmcompute)
   - 더블클릭 → **시작** 버튼 클릭 → **확인**

3. **Docker Desktop Service** (com.docker.service)
   - 더블클릭 → **시작** 버튼 클릭 → **확인**

**3단계**: PowerShell에서 확인:
```powershell
docker version
```

---

## ✅ 성공 확인

이렇게 보이면 성공입니다:
```
Client:
 Version:           29.2.1
 ...

Server:               # ← 이 섹션이 보여야 합니다!
 Engine:
  Version:          29.2.1
  ...
```

---

## 🐘 다음 단계: AgriGuard Week 2

Docker가 작동하면 다음 명령어를 실행해주세요:

```powershell
cd "d:\AI 프로젝트"
powershell -ExecutionPolicy Bypass -File AgriGuard\validate_postgres_week2.ps1
```

---

## 🆘 문제가 계속되면

1. **PC 재부팅** (WSL 기능 활성화가 필요할 수 있음)
2. **WSL 재설치**:
   ```powershell
   wsl --install
   ```
3. **대안**: SQLite 모드로 계속 진행 (PostgreSQL 없이)

---

**예상 소요 시간**: 2-5분
**필요한 것**: 관리자 권한만 있으면 됩니다!

🤖 이 파일은 자동으로 생성되었습니다.
