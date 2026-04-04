#!/usr/bin/env python3
"""박주민 브리핑 시스템 — 로컬 서버 + 스케줄러"""

import os, sys, time, subprocess, threading
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 3002
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SCRIPT_DIR, "scripts")

# .env 로드
env_path = os.path.join(SCRIPT_DIR, '.env')
if os.path.exists(env_path):
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

def run_collector(script_name, args=None, timeout=180):
    """수집 스크립트 실행"""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script_name)]
    if args:
        cmd.extend(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', env=os.environ.copy()
        )
        if result.returncode == 0:
            print(f"[OK] {script_name} 성공")
        else:
            stderr = result.stderr[:300] if result.stderr else "Unknown"
            print(f"[WARN] {script_name} 실패: {stderr}")
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"[WARN] {script_name} 타임아웃 ({timeout}s)")
        return -1
    except Exception as e:
        print(f"[ERROR] {script_name}: {e}")
        return -1

def daily_briefing_scheduler():
    """매일 아침 8:30에 파이프라인 실행, 9:00에 발송"""
    time.sleep(10)
    print("[SCHEDULER] 일일 브리핑 스케줄러 시작 (매일 08:30 KST)")

    while True:
        now = datetime.now()
        # 08:30에 수집+분석 시작
        if now.hour == 8 and now.minute == 30:
            today = now.strftime('%Y-%m-%d')
            print(f"\n[SCHEDULER] === 일일 브리핑 시작 ({today}) ===")

            run_collector("collect_news.py", ["--date", today])
            run_collector("collect_social.py", ["--date", today])
            run_collector("analyze_strategy.py", ["--date", today])
            run_collector("generate_briefing.py", ["--date", today])

            # 09:00까지 대기 후 발송
            wait_until_9 = max(0, (9 * 60 - (now.hour * 60 + now.minute)) * 60)
            if wait_until_9 > 0 and wait_until_9 < 3600:
                print(f"[SCHEDULER] 09:00까지 {wait_until_9//60}분 대기...")
                time.sleep(wait_until_9)

            run_collector("send_telegram.py", ["--send-only", "--date", today])
            print(f"[SCHEDULER] === 일일 브리핑 완료 ({today}) ===\n")

            # 다음날까지 대기 (23시간)
            time.sleep(23 * 3600)
        else:
            time.sleep(30)

def manual_run():
    """수동 즉시 실행"""
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"[MANUAL] 즉시 실행 — {today}")
    run_collector("send_telegram.py", ["--now", "--date", today])

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--run-now":
        manual_run()
        return

    # 스케줄러 스레드 시작
    scheduler_thread = threading.Thread(target=daily_briefing_scheduler, daemon=True)
    scheduler_thread.start()

    # HTTP 서버 시작
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[SERVER] http://127.0.0.1:{PORT}/ 에서 실행 중")
    print(f"[SERVER] 수동 실행: python serve.py --run-now")
    print(f"[SERVER] 자동 발송: 매일 KST 09:00")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] 종료")
        server.server_close()

if __name__ == "__main__":
    main()
