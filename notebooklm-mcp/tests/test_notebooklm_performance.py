import os
import sys
import time
from dotenv import load_dotenv

# 윈도우 인코딩 설정
def _ensure_utf8_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

_ensure_utf8_streams()

# Google Credentials 환경변수 설정 (현재 디렉토리 기준)
current_dir = os.path.dirname(os.path.abspath(__file__))
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(current_dir, "credentials.json")

print(f"[INFO] Credentials Path: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")

try:
    from notebooklm_mcp.server import get_client
except ImportError:
    print("[FAIL] notebooklm_mcp 패키지를 찾을 수 없습니다. venv 환경에서 실행해주세요.")
    sys.exit(1)

def test_performance():
    print("\n🚀 [Step 1] NotebookLM 클라이언트 연결 중...")
    try:
        client = get_client()
        user_info = client.get_user_info() if hasattr(client, 'get_user_info') else "User info not available"
        print(f"✅ [성공] 인증 완료! (User: {user_info})")
    except Exception as e:
        print(f"❌ [실패] 인증 오류 발생: {e}")
        print("  -> 'authenticate_notebooklm.bat'를 실행하여 다시 로그인해주세요.")
        return

    print("\n📔 [Step 2] 테스트용 노트북 생성 중...")
    try:
        title = "[Antigravity] Performance Test 🧪"
        notebook = client.create_notebook(title=title)
        print(f"✅ [성공] 노트북 생성됨: {notebook.title}")
        print(f"   -> ID: {notebook.id}")
        print(f"   -> URL: https://notebooklm.google.com/notebook/{notebook.id}")
    except Exception as e:
        print(f"❌ [실패] 노트북 생성 오류: {e}")
        return

    print("\n📄 [Step 3] 소스 데이터 추가 (Antigravity 프로젝트 정보)...")
    try:
        # 테스트용 문서 데이터
        project_overview = """
        프로젝트명: Antigravity (반중력)
        
        [개요]
        Antigravity 프로젝트는 AI 에이전트 '라프(Raf)'와 함께 개인의 생산성을 극대화하고, 
        세상의 트렌드를 빠르게 포착하여 인사이트를 제공하는 시스템입니다.
        
        [핵심 모듈]
        1. Notion MCP: 
           - 개인의 할 일(Task), 아이디어, 버그 리포트 등을 Notion 데이터베이스에 자동으로 기록합니다.
           - V2 업데이트를 통해 날짜, 목표, 달성 내용 등의 상세 속성을 지원합니다.
           
        2. NotebookLM MCP:
           - 구글의 NotebookLM과 연동하여 방대한 문서를 이해하고 질의응답할 수 있습니다.
           - 사용자가 직접 문서를 읽지 않아도 핵심 내용을 요약해주고, 복잡한 질문에 답해줍니다.
           
        3. X(Twitter) Trend Analysis (예정):
           - Brave Search를 통해 실시간 트렌드를 파악하고, 인사이트 리포트를 작성합니다.
        
        [팀원]
        - User: 프로젝트 총괄 및 의사결정
        - Raf (AI): 개발, 기획, 실행을 담당하는 최고의 파트너
        """
        
        source = client.add_text_source(notebook.id, project_overview, title="Antigravity Project Overview")
        # 반환값이 dict일 경우 처리
        if isinstance(source, dict):
             source_title = source.get('title', 'Unknown Title')
        else:
             source_title = source.title
             
        print(f"✅ [성공] 소스 추가됨: {source_title}")
        print("   -> 내용 처리를 위해 잠시 대기합니다 (5초)...")
        time.sleep(5) 
    except Exception as e:
        print(f"❌ [실패] 소스 추가 오류: {e}")
        return

    print("\n💬 [Step 4] AI 질의응답 테스트...")
    questions = [
        "이 프로젝트의 핵심 모듈 3가지는 무엇인가요?",
        "라프(Raf)의 역할은 뭐야?"
    ]
    
    for q in questions:
        print(f"\nQ: {q}")
        try:
            # query 메서드는 dict가 아니라 객체를 반환할 수도 있고 dict를 반환할 수도 있음.
            # server.py 로직상 client.query() 호출 결과를 그대로 씀.
            # NotebookLMClient.query의 반환값을 확인해야 함. 보통 dict임.
            answer_obj = client.query(notebook.id, q)
            
            # answer_obj가 dict인지 객체인지 확인하여 처리
            answer_text = ""
            if isinstance(answer_obj, dict):
                answer_text = answer_obj.get("answer", "No answer found")
            else:
                answer_text = getattr(answer_obj, "answer", str(answer_obj))
                
            print(f"A: {answer_text}")
            print("-" * 50)
        except Exception as e:
            print(f"❌ [실패] 질의 오류: {e}")

    print("\n✨ [완료] 모든 테스트가 종료되었습니다.")

if __name__ == "__main__":
    test_performance()
