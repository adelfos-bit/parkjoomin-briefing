#!/usr/bin/env python3
"""박주민 서울시장 후보 — 텔레그램 브리핑 발송"""

import os, sys, json, argparse, time
from datetime import datetime
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

# .env 로드
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

def send_message(text, parse_mode=None):
    """텔레그램 메시지 발송"""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("여기에"):
        print("[ERROR] 텔레그램 봇 토큰이 설정되지 않았습니다.")
        print("  → .env 파일에 TELEGRAM_BOT_TOKEN을 입력하세요.")
        return False
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID.startswith("여기에"):
        print("[ERROR] 텔레그램 채팅 ID가 설정되지 않았습니다.")
        print("  → .env 파일에 TELEGRAM_CHAT_ID를 입력하세요.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if data.get("ok"):
            return True
        else:
            print(f"[ERROR] 텔레그램 발송 실패: {data.get('description', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"[ERROR] 텔레그램 통신 오류: {e}")
        return False

def send_briefing(target_date):
    """브리핑 메시지 발송"""
    # 브리핑 아카이브에서 로드
    archive_path = os.path.join(BASE_DIR, "data", "briefing_archive", f"{target_date}.json")

    if not os.path.exists(archive_path):
        print(f"[ERROR] 브리핑 파일 없음: {archive_path}")
        print("  → generate_briefing.py를 먼저 실행하세요.")
        return False

    with open(archive_path, 'r', encoding='utf-8') as f:
        briefing = json.load(f)

    messages = briefing.get("messages", [])
    if not messages:
        print("[ERROR] 브리핑 메시지가 비어있습니다.")
        return False

    print(f"[INFO] {len(messages)}개 메시지 발송 시작...")

    success = 0
    for i, msg in enumerate(messages):
        ok = send_message(msg)
        if ok:
            success += 1
            print(f"  [{i+1}/{len(messages)}] 발송 성공 ✓")
        else:
            print(f"  [{i+1}/{len(messages)}] 발송 실패 ✗")
        time.sleep(1)  # 텔레그램 rate limit 방지

    print(f"[DONE] 발송 완료 — {success}/{len(messages)}건 성공")
    return success == len(messages)

def run_full_pipeline(target_date):
    """전체 파이프라인 실행: 수집 → 분석 → 브리핑 → 발송"""
    import subprocess

    scripts = [
        ("뉴스 수집", ["python", os.path.join(SCRIPT_DIR, "collect_news.py"), "--date", target_date]),
        ("SNS 수집", ["python", os.path.join(SCRIPT_DIR, "collect_social.py"), "--date", target_date]),
        ("전략 분석", ["python", os.path.join(SCRIPT_DIR, "analyze_strategy.py"), "--date", target_date]),
        ("브리핑 생성", ["python", os.path.join(SCRIPT_DIR, "generate_briefing.py"), "--date", target_date]),
    ]

    for name, cmd in scripts:
        print(f"\n{'='*40}")
        print(f"▶ {name} 시작...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180, encoding='utf-8')
            if result.returncode == 0:
                print(f"  ✓ {name} 완료")
            else:
                print(f"  ✗ {name} 실패: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"  ✗ {name} 타임아웃 (3분)")
        except Exception as e:
            print(f"  ✗ {name} 오류: {e}")

    # 텔레그램 발송
    print(f"\n{'='*40}")
    print("▶ 텔레그램 발송...")
    return send_briefing(target_date)

def main():
    parser = argparse.ArgumentParser(description="박주민 텔레그램 브리핑 발송")
    parser.add_argument("--date", default=datetime.now().strftime('%Y-%m-%d'))
    parser.add_argument("--now", action="store_true", help="전체 파이프라인 즉시 실행")
    parser.add_argument("--send-only", action="store_true", help="발송만 실행 (기생성 브리핑)")
    args = parser.parse_args()

    if args.now:
        print(f"[START] 전체 파이프라인 실행 — {args.date}")
        run_full_pipeline(args.date)
    elif args.send_only:
        print(f"[START] 브리핑 발송 — {args.date}")
        send_briefing(args.date)
    else:
        print("사용법:")
        print("  --now       : 수집→분석→브리핑→발송 전체 실행")
        print("  --send-only : 이미 생성된 브리핑 발송만")

if __name__ == "__main__":
    main()
