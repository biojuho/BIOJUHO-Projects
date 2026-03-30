"""BitNet 환경 설정 스크립트.

이 스크립트는 BitNet b1.58을 로컬에 설정합니다:
1. BitNet 리포지토리 클론
2. conda 환경 생성 (선택)
3. 모델 다운로드 (BitNet-b1.58-2B-4T)
4. 프로젝트 빌드

사전 요구사항:
  - Git
  - Python 3.9+
  - Visual Studio 2022 (C++ 데스크톱 개발 워크로드)
  - conda (권장)

사용법:
  python setup_bitnet.py --check   # 환경 확인만
  python setup_bitnet.py --install # 전체 설치
"""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BITNET_DIR = ROOT / "BitNet"
MODEL_DIR = BITNET_DIR / "models" / "BitNet-b1.58-2B-4T"
MODEL_GGUF = MODEL_DIR / "ggml-model-i2_s.gguf"


def check_tool(cmd: list[str], name: str) -> bool:
    """Check if a CLI tool is available."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        print(f"  ✅ {name}: available")
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"  ❌ {name}: NOT FOUND")
        return False


def check_environment() -> dict:
    """Check all prerequisites."""
    print("\n🔍 BitNet 환경 점검\n" + "=" * 50)

    checks = {}
    checks["git"] = check_tool(["git", "--version"], "Git")
    checks["python"] = check_tool(["python", "--version"], "Python")
    checks["conda"] = check_tool(["conda", "--version"], "Conda")
    checks["cmake"] = check_tool(["cmake", "--version"], "CMake")
    checks["clang"] = check_tool(["clang", "--version"], "Clang")

    # Check VS2022
    vs_paths = [
        r"C:\Program Files\Microsoft Visual Studio\2022\Community",
        r"C:\Program Files\Microsoft Visual Studio\2022\Professional",
        r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise",
    ]
    vs_found = any(Path(p).exists() for p in vs_paths)
    if vs_found:
        print("  ✅ Visual Studio 2022: found")
    else:
        print("  ❌ Visual Studio 2022: NOT FOUND")
    checks["vs2022"] = vs_found

    # Check BitNet repo
    if BITNET_DIR.exists():
        print(f"  ✅ BitNet repo: {BITNET_DIR}")
    else:
        print("  ⬜ BitNet repo: not cloned yet")
    checks["repo"] = BITNET_DIR.exists()

    # Check model
    if MODEL_GGUF.exists():
        size_mb = MODEL_GGUF.stat().st_size / (1024 * 1024)
        print(f"  ✅ Model: {MODEL_GGUF.name} ({size_mb:.0f} MB)")
    else:
        print("  ⬜ Model: not downloaded yet")
    checks["model"] = MODEL_GGUF.exists()

    # Overall
    required = ["git", "python"]
    build_required = ["cmake", "clang", "vs2022"]

    print("\n" + "=" * 50)
    if all(checks.get(k) for k in required):
        print("✅ 기본 요구사항 충족")
    else:
        missing = [k for k in required if not checks.get(k)]
        print(f"❌ 필수 도구 누락: {', '.join(missing)}")

    if not all(checks.get(k) for k in build_required):
        missing = [k for k in build_required if not checks.get(k)]
        print(f"⚠️  빌드 도구 누락: {', '.join(missing)}")
        print("   → conda 설치: https://docs.conda.io/en/latest/miniconda.html")
        print("   → VS2022:     https://visualstudio.microsoft.com/downloads/")
        print("   → cmake/clang은 conda 환경에서 자동 설치됩니다.")

    if checks.get("repo") and checks.get("model"):
        print("\n🎉 BitNet 사용 준비 완료!")
    elif checks.get("repo"):
        print("\n📥 모델 다운로드 필요: python setup_bitnet.py --install")
    else:
        print("\n🔧 설치 필요: python setup_bitnet.py --install")

    return checks


def clone_repo():
    """Clone the BitNet repository."""
    if BITNET_DIR.exists():
        print(f"✅ BitNet repo already exists at {BITNET_DIR}")
        return

    print(f"\n📦 Cloning BitNet to {BITNET_DIR}...")
    subprocess.run(
        ["git", "clone", "--recursive", "https://github.com/microsoft/BitNet.git", str(BITNET_DIR)],
        check=True,
    )
    print("✅ Clone complete")


def setup_conda_env():
    """Create and activate conda environment."""
    print("\n🐍 Setting up conda environment...")
    try:
        # Check if env already exists
        result = subprocess.run(["conda", "env", "list"], capture_output=True, text=True)
        if "bitnet-cpp" in result.stdout:
            print("✅ Conda env 'bitnet-cpp' already exists")
            return

        subprocess.run(
            ["conda", "create", "-n", "bitnet-cpp", "python=3.9", "-y"],
            check=True,
        )
        print("✅ Conda env 'bitnet-cpp' created")
        print("   → 활성화: conda activate bitnet-cpp")
    except FileNotFoundError:
        print("⚠️  conda not found, skipping conda setup")
        print("   pip install -r requirements.txt 를 직접 실행하세요")


def install_deps():
    """Install Python dependencies."""
    print("\n📦 Installing dependencies...")
    req_file = BITNET_DIR / "requirements.txt"
    if req_file.exists():
        subprocess.run(
            ["pip", "install", "-r", str(req_file)],
            check=True,
            cwd=str(BITNET_DIR),
        )
        print("✅ Dependencies installed")
    else:
        print("⚠️  requirements.txt not found")


def download_model():
    """Download the BitNet-b1.58-2B-4T model."""
    if MODEL_GGUF.exists():
        print(f"✅ Model already exists: {MODEL_GGUF}")
        return

    print("\n📥 Downloading BitNet-b1.58-2B-4T model...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "python",
            "-m",
            "huggingface_hub",
            "download",
            "microsoft/BitNet-b1.58-2B-4T-gguf",
            "--local-dir",
            str(MODEL_DIR),
        ],
        check=True,
        cwd=str(BITNET_DIR),
    )
    print(f"✅ Model downloaded to {MODEL_DIR}")


def build_project():
    """Build bitnet.cpp using setup_env.py."""
    print("\n🔨 Building bitnet.cpp...")
    setup_script = BITNET_DIR / "setup_env.py"
    if not setup_script.exists():
        print("❌ setup_env.py not found")
        return

    subprocess.run(
        [
            "python",
            str(setup_script),
            "-md",
            str(MODEL_DIR),
            "-q",
            "i2_s",
        ],
        check=True,
        cwd=str(BITNET_DIR),
    )
    print("✅ Build complete")


def write_env_config():
    """Write BitNet configuration to .env."""
    env_file = ROOT / ".env"
    bitnet_vars = {
        "BITNET_MODEL_PATH": str(MODEL_GGUF),
        "BITNET_BINARY_DIR": str(BITNET_DIR),
        "BITNET_THREADS": "4",
        "BITNET_CTX_SIZE": "2048",
    }

    existing = ""
    if env_file.exists():
        existing = env_file.read_text(encoding="utf-8")

    additions = []
    for key, value in bitnet_vars.items():
        if key not in existing:
            additions.append(f"{key}={value}")

    if additions:
        with open(env_file, "a", encoding="utf-8") as f:
            f.write("\n# BitNet Local Inference Configuration\n")
            for line in additions:
                f.write(f"{line}\n")
        print(f"✅ .env에 BitNet 설정 추가 ({len(additions)}개 항목)")
    else:
        print("✅ .env에 BitNet 설정 이미 존재")


def main():
    parser = argparse.ArgumentParser(description="BitNet 환경 설정")
    parser.add_argument("--check", action="store_true", help="환경 확인만")
    parser.add_argument("--install", action="store_true", help="전체 설치")
    parser.add_argument("--model-only", action="store_true", help="모델만 다운로드")
    args = parser.parse_args()

    if args.check or not (args.install or args.model_only):
        check_environment()
        return

    if args.install:
        checks = check_environment()
        print("\n" + "=" * 50)
        print("🚀 BitNet 설치 시작\n")

        clone_repo()
        setup_conda_env()
        install_deps()
        download_model()
        build_project()
        write_env_config()

        print("\n" + "=" * 50)
        print("🎉 BitNet 설치 완료!")
        print(f"   모델: {MODEL_DIR}")
        print('   테스트: python -c "from shared.llm.bitnet_runner import is_available; print(is_available())"')

    elif args.model_only:
        clone_repo()
        download_model()
        write_env_config()


if __name__ == "__main__":
    main()
