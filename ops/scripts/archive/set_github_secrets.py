"""
GitHub Secrets 일괄 등록 스크립트
- git credential의 기존 토큰으로 GitHub API 직접 호출
- NaCl/libsodium로 secret 값 암호화 후 PUT
"""
import os, sys, json, base64, subprocess

# === Config ===
REPO = "biojuho/BIOJUHO-Projects"
ROOT = r"d:\AI project"

def get_git_token():
    """git credential에서 GitHub 토큰 추출"""
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        capture_output=True, text=True, cwd=ROOT
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise RuntimeError("No git credential found")

def load_env(path):
    """간단한 .env 파서"""
    result = {}
    if not os.path.exists(path):
        return result
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip("'").strip('"')
            result[key.strip()] = val
    return result

def main():
    import urllib.request

    token = get_git_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 1. Get repo public key for encryption
    print("Fetching repo public key...")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/secrets/public-key",
        headers=headers
    )
    with urllib.request.urlopen(req) as resp:
        pub_key_data = json.loads(resp.read())
    
    pub_key = base64.b64decode(pub_key_data["key"])
    key_id = pub_key_data["key_id"]
    print(f"  Key ID: {key_id}")

    # 2. Encrypt using PyNaCl (sealed box)
    try:
        from nacl.public import SealedBox, PublicKey
    except ImportError:
        print("Installing PyNaCl...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pynacl", "-q"])
        from nacl.public import SealedBox, PublicKey

    public_key = PublicKey(pub_key)
    sealed_box = SealedBox(public_key)

    # 3. Load secrets from local .env files
    root_env = load_env(os.path.join(ROOT, ".env"))
    gdt_env = load_env(os.path.join(ROOT, "automation", "getdaytrends", ".env"))

    secrets_map = {
        # REQUIRED
        "ANTHROPIC_API_KEY":    root_env.get("ANTHROPIC_API_KEY"),
        "GOOGLE_API_KEY":       root_env.get("GOOGLE_API_KEY"),
        "NOTION_TOKEN":         gdt_env.get("NOTION_TOKEN"),
        "NOTION_DATABASE_ID":   gdt_env.get("NOTION_DATABASE_ID"),
        # RECOMMENDED
        "OPENAI_API_KEY":       root_env.get("OPENAI_API_KEY"),
        "XAI_API_KEY":          root_env.get("XAI_API_KEY"),
        "DEEPSEEK_API_KEY":     root_env.get("DEEPSEEK_API_KEY"),
        "TELEGRAM_BOT_TOKEN":   root_env.get("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID":     root_env.get("TELEGRAM_CHAT_ID"),
        "TWITTER_BEARER_TOKEN": gdt_env.get("TWITTER_BEARER_TOKEN"),
        # OPTIONAL
        "CONTENT_HUB_DATABASE_ID": gdt_env.get("CONTENT_HUB_DATABASE_ID"),
        "IMGBB_API_KEY":        gdt_env.get("IMGBB_API_KEY"),
    }

    # 4. Set each secret
    ok = 0; skip = 0; fail = 0
    for name, value in secrets_map.items():
        if not value:
            print(f"  SKIP {name} (no value)")
            skip += 1
            continue

        encrypted = sealed_box.encrypt(value.encode("utf-8"))
        encrypted_b64 = base64.b64encode(encrypted).decode("utf-8")

        payload = json.dumps({
            "encrypted_value": encrypted_b64,
            "key_id": key_id,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/actions/secrets/{name}",
            data=payload,
            headers={**headers, "Content-Type": "application/json"},
            method="PUT"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
            icon = "OK" if status in (201, 204) else "WARN"
            print(f"  [{icon}] {name} -> HTTP {status}")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {name} -> {e}")
            fail += 1

    print(f"\nResults: {ok} set, {skip} skipped, {fail} failed")
    return 0 if fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
