import os
import requests
import argparse
from dotenv import load_dotenv

def get_telegram_creds():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    env_path = os.path.join(parent_dir, ".env")
    load_dotenv(env_path)
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return bot_token, chat_id

def send_telegram_message(message: str, parse_mode: str = "HTML") -> bool:
    """
    텔레그램 봇 API를 사용하여 메시지를 전송합니다.
    :param message: 전송할 메시지 내용 (포맷팅 가능)
    :param parse_mode: HTML 또는 MarkdownV2
    :return: 성공 여부 (bool)
    """
    bot_token, chat_id = get_telegram_creds()
    
    if not bot_token or not chat_id:
        print("[WARNING] Telegram credentials (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) are missing. Skipping notification.")
        return False
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("[SUCCESS] Telegram notification sent.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
        # 응답 본문이 있으면 추가 출력하여 디버깅을 돕습니다.
        if hasattr(e, 'response') and e.response is not None:
            print(f"[DEBUG] Telegram API Response: {e.response.text}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a message to the configured Telegram chat.")
    parser.add_argument("--test", required=True, help="Message to send")
    args = parser.parse_args()
    
    success = send_telegram_message(args.test)
    if not success:
        import sys
        sys.exit(1)
