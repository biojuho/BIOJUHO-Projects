import os
import requests
import base64
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv, set_key
from token_store import save_token

# 설정 로드
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
env_path = os.path.join(parent_dir, ".env")
load_dotenv(env_path)

CLIENT_ID = os.getenv("CANVA_CLIENT_ID")
CLIENT_SECRET = os.getenv("CANVA_CLIENT_SECRET")
REDIRECT_URI = os.getenv("CANVA_REDIRECT_URI", "http://127.0.0.1:8080/oauth/callback")

# 포트 번호 추출 (기본 8080)
try:
    PORT = int(urllib.parse.urlparse(REDIRECT_URI).port or 8080)
except Exception:
    PORT = 8080

def generate_auth_url():
    """
    브라우저에서 열 인증 URL을 생성합니다.
    (권한: design:meta:read, design:content:read, design:content:write 등 필요한 스코프 추가)
    자세한 스코프 목록: https://www.canva.com/developers/docs/connect/api-reference/
    """
    scopes = "design:meta:read design:content:read design:content:write"
    
    # Canva Connect URL 포맷에 맞게 쿼리 인코딩
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": scopes,
        # code_challenge 및 code_challenge_method는 PKCE 방식 필수 (문서 확인 후 필요 시 구현)
        "state": "antigravity_auth_test"
    }
    
    # PKCE 요구조건을 맞추기 위한 임시 간단한 해시 생성 (보안 목적으로는 random 생성 필요)
    import hashlib
    import secrets
    import string
    
    code_verifier = ''.join(secrets.choice(string.ascii_letters + string.digits + '-._~') for _ in range(43))
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip("=")
    
    params["code_challenge"] = code_challenge
    params["code_challenge_method"] = "S256"
    
    # 전역변수로 저장하여 token 교환 시 사용
    global VERIFIER
    VERIFIER = code_verifier
    
    auth_url = f"https://www.canva.com/api/oauth/authorize?{urllib.parse.urlencode(params)}"
    return auth_url

def exchange_code_for_token(code):
    url = "https://api.canva.com/rest/v1/oauth/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": VERIFIER
    }
    
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        token_data = response.json()
        print("\n\n[SUCCESS] Canva 토큰을 정상적으로 받아왔습니다!")
        refresh_tok = token_data.get('refresh_token', '')
        print(f"Refresh Token: {refresh_tok[:15]}... (생략됨)")

        # Save to token_store (encrypted JSON) and .env (fallback)
        try:
            save_token("CANVA_REFRESH_TOKEN", refresh_tok)
            print("[SAVED] token_store에 CANVA_REFRESH_TOKEN 이 성공적으로 저장되었습니다.")
        except Exception:
            pass
        try:
            set_key(env_path, "CANVA_REFRESH_TOKEN", refresh_tok)
            print("[SAVED] .env 파일에도 CANVA_REFRESH_TOKEN 이 백업 저장되었습니다.")
        except Exception as e:
            print("[WARN] .env 자동 저장에 실패했습니다. 아래 토큰을 수동으로 복사해서 .env 파일에 추가해 주세요:")
            print(f"CANVA_REFRESH_TOKEN={refresh_tok}")

    else:
        print(f"\n[FAIL] 토큰 교환 중 오류 발생: {response.text}")

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        queries = urllib.parse.parse_qs(parsed_path.query)
        
        if "error" in queries:
            self.send_response(400)
            self.end_headers()
            self.wfile.write("Authorization failed or denied by user.".encode("utf-8"))
            print("\n[ERROR] 사용자가 권한을 거부했거나 오류가 발생했습니다:", queries.get("error")[0])
            
        elif "code" in queries:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write("<h1>인증이 완료되었습니다.</h1><p>이 창을 닫고 터미널 창을 확인해 주세요.</p>".encode("utf-8"))
            
            code = queries["code"][0]
            print(f"\n[INFO] Call back received. Auth Code: {code[:10]}...")
            exchange_code_for_token(code)
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write("Not Found".encode("utf-8"))
            
        # 서버 인스턴스를 하나만 받고 종료하게 함 (임시용이므로)
        import threading
        threading.Thread(target=self.server.shutdown).start()

    # 로그 출력 방지용
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not CLIENT_ID or not CLIENT_SECRET:
        print("[ERROR] .env 파일에 CANVA_CLIENT_ID 혹은 CANVA_CLIENT_SECRET 이 세팅되지 않았습니다.")
        sys.exit(1)

    auth_url = generate_auth_url()

    # Save URL to file so the assistant can read it cleanly
    url_path = os.path.join(parent_dir, "canva_url.txt")
    with open(url_path, "w", encoding="utf-8") as f:
        f.write(auth_url)

    print("\n" + "="*80)
    print("[Canva] API 연동을 위한 로컬 서버를 시작합니다.")
    print("="*80)
    print("아래 링크를 복사하여 웹 브라우저 주소창에 붙여넣기 한 뒤, 권한 승인 버튼을 눌러주세요.")
    print("\n[AUTH URL]:")
    print(auth_url)
    print("\n" + "="*80)
    print(f"포트 {PORT}에서 요청 대기 중... (취소하려면 Ctrl+C)")

    server_address = ('127.0.0.1', PORT)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] 서버 강제 종료 됨.")
