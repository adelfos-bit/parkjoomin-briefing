#!/usr/bin/env python3
"""박주민 서울시장 후보 — 텔레그램 브리핑 메시지 생성기 (도식화)"""

import os, sys, json, argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

def bar(value, max_val=100, length=15):
    """텍스트 막대그래프"""
    filled = int(value / max_val * length) if max_val > 0 else 0
    filled = min(filled, length)
    return "█" * filled + "░" * (length - filled)

def trend_arrow(change):
    """변화량 화살표"""
    if change > 0:
        return f"+{change} ▲"
    elif change < 0:
        return f"{change} ▼"
    return "→ 변동없음"

def format_number(n):
    """숫자 포맷"""
    if n >= 10000:
        return f"{n/10000:.1f}만"
    elif n >= 1000:
        return f"{n:,}"
    return str(n)

def generate_header(target_date):
    """헤더"""
    dt = datetime.strptime(target_date, '%Y-%m-%d')
    weekday = WEEKDAYS[dt.weekday()]
    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {target_date} ({weekday}) 박주민 일일 브리핑
━━━━━━━━━━━━━━━━━━━━━━━━━"""

def generate_section1_dashboard(stats, trends):
    """섹션1: 일일 현황 대시보드"""
    sentiment = stats.get("sentiment", {})
    pos = sentiment.get("pos_pct", 0)
    neg = sentiment.get("neg_pct", 0)
    neu = sentiment.get("neu_pct", 0)
    comments = stats.get("comments", {})
    exposure = stats.get("candidate_exposure", {})

    # 여론 온도계
    sentiment_bar = bar(pos)
    sentiment_change = trends.get("sentiment_change", 0)

    # 경쟁 구도 (노출 기준)
    sorted_candidates = sorted(exposure.items(), key=lambda x: -x[1])

    competition_text = ""
    for name, count in sorted_candidates[:5]:
        emoji = "🔵" if name == "박주민" else "⚪"
        cbar = bar(count, max(exposure.values()) if exposure else 1, 12)
        competition_text += f"  {emoji} {name:6s} {cbar} {count}건\n"

    alert_emoji = {"normal": "🟢", "warning": "🟡", "critical": "🔴"}.get(
        trends.get("alert_level", "normal"), "🟢"
    )

    return f"""
📊 【1. 일일 현황 대시보드】

🔥 여론 온도계
  {sentiment_bar} 긍정 {pos}%
  전일 대비: {trend_arrow(sentiment_change)}
  긍정 {pos}% | 부정 {neg}% | 중립 {neu}%

📰 미디어 노출
  전체 기사: {stats.get('total_articles', 0)}건
  박주민 언급: {stats.get('parkjoomin_articles', 0)}건 ({trend_arrow(trends.get('article_change', 0))})

💬 댓글 반응
  총 댓글: {format_number(comments.get('total', 0))}건
  {bar(comments.get('pos_pct', 0))}
  긍정 {comments.get('pos_pct', 0)}% | 부정 {100 - comments.get('pos_pct', 0) - comments.get('neu_pct', 0) if comments.get('total', 0) > 0 else 0}% | 중립 {comments.get('neu_pct', 0) if comments.get('total', 0) > 0 else 0}%

🏆 미디어 노출 경쟁
{competition_text}
{alert_emoji} 경보: {trends.get('alert_level', 'normal').upper()}
{chr(10).join('  ⚠️ ' + a for a in trends.get('alerts', [])) if trends.get('alerts') else '  상태 양호'}"""

def generate_section2_trends(stats, trends):
    """섹션2: 트렌드 분석"""
    keywords = stats.get("top_keywords", [])
    keywords_text = ""
    for i, (kw, count) in enumerate(keywords[:7], 1):
        keywords_text += f"  {i}. \"{kw}\" ({count}회)\n"

    return f"""
📈 【2. 트렌드 분석】

🔑 주요 키워드 TOP 7
{keywords_text}"""

def generate_section3_news(stats):
    """섹션3: 주요 뉴스 TOP 5"""
    articles = stats.get("top_articles", [])[:5]
    news_text = ""
    for i, art in enumerate(articles, 1):
        emoji = {"긍정": "😊", "부정": "😟", "중립": "🔵"}.get(art.get("sentiment", "중립"), "🔵")
        comment_info = art.get("comments", {})
        c_count = comment_info.get('count', 0)
        c_pos = comment_info.get('pos_pct', 0)
        c_neg = 100 - c_pos - comment_info.get('neu_pct', 0) if c_count > 0 else 0
        comment_str = f"댓글 {c_count}건 (👍{c_pos}% 👎{c_neg}%)" if c_count > 0 else "댓글 없음"
        news_text += f"""
  {i}. [{art['sentiment']}{emoji}] {art['title'][:50]}
     {comment_str}"""

    return f"""
📰 【3. 주요 뉴스 TOP 5】
{news_text}"""

def generate_section4_social(social_data):
    """섹션4: SNS 반응 요약"""
    channels = social_data.get("channels", {})
    text = "\n📱 【4. SNS 반응】\n"

    if "youtube" in channels:
        yt = channels["youtube"]["data"]
        videos = yt.get("videos", [])
        text += f"\n  ▶️ 유튜브: 관련 영상 {len(videos)}건"
        if videos:
            text += f", 총 조회 {format_number(yt.get('total_views', 0))}회"

    if "twitter_sns" in channels:
        tw = channels["twitter_sns"]["data"]
        x_count = tw.get('x_count', 0)
        web_count = tw.get('web_count', 0)
        text += f"\n  🐦 X(트위터): {x_count}건 | SNS 언급: {web_count}건"
    elif "twitter" in channels:
        tw = channels["twitter"]["data"]
        text += f"\n  🐦 X(트위터): 멘션 {tw.get('total', 0)}건"

    if "community" in channels:
        cm = channels["community"]["data"]
        text += f"\n  🗣️ 커뮤니티: 게시글 {cm.get('total', 0)}건"

    if "naver_comments" in channels:
        nc = channels["naver_comments"]["data"]
        text += f"\n  💬 네이버 댓글: {format_number(nc.get('total_reactions', 0))}건"

    return text

def generate_section5_strategy(strategy_data):
    """섹션5: 정책전문가 전략 (핵심!)"""
    # AI 전략이 있으면 그대로 사용
    ai = strategy_data.get("ai_strategy")
    if ai:
        # AI 응답을 적절히 잘라서 텔레그램 제한에 맞춤
        lines = ai.strip().split('\n')
        truncated = '\n'.join(lines[:50])  # 최대 50줄
        return f"""
🧠 【5. 정책전문가 일일 전략】

{truncated}"""

    # Fallback 전략
    fb = strategy_data.get("fallback_strategy", {})
    if not fb:
        return "\n🧠 【5. 전략 분석】\n  데이터 부족으로 분석 보류"

    actions_text = "\n".join(f"  {a}" for a in fb.get("actions", []))
    risks_text = "\n".join(f"  🔴 {r}" for r in fb.get("risks", ["없음"]))
    opps_text = "\n".join(f"  🟢 {o}" for o in fb.get("opportunities", ["없음"]))

    return f"""
🧠 【5. 정책전문가 일일 전략】

━━━ 오늘의 핵심 진단 ━━━
{fb.get('core_diagnosis', '')}

🎯 최우선 과제
  {fb.get('top_priority', '')}

✅ 실행 액션
{actions_text}

⚡ 위기/기회 알림
{risks_text}
{opps_text}

🏁 경쟁자 동향
  {fb.get('competitor_analysis', '')}

📌 내일 주목 포인트
  {fb.get('tomorrow_focus', '')}"""

def generate_footer():
    """푸터"""
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 자동 생성 | {datetime.now().strftime('%H:%M')} 기준
📊 정책전문가 + 데이터사이언티스트 이중 분석
━━━━━━━━━━━━━━━━━━━━━━━━━"""

def generate_full_briefing(target_date):
    """전체 브리핑 메시지 생성"""
    # 데이터 로드
    strategy_path = os.path.join(BASE_DIR, "data", "strategy_daily", f"{target_date}.json")
    news_path = os.path.join(BASE_DIR, "data", "news_daily", f"{target_date}.json")
    social_path = os.path.join(BASE_DIR, "data", "social_daily", f"{target_date}.json")

    strategy_data = {}
    news_data = {}
    social_data = {}

    for path, target in [(strategy_path, "strategy"), (news_path, "news"), (social_path, "social")]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                if target == "strategy":
                    strategy_data = json.load(f)
                elif target == "news":
                    news_data = json.load(f)
                else:
                    social_data = json.load(f)

    stats = news_data.get("stats", strategy_data.get("news_stats", {}))
    trends = strategy_data.get("trends", {})

    # 각 섹션 생성
    header = generate_header(target_date)
    section1 = generate_section1_dashboard(stats, trends)
    section2 = generate_section2_trends(stats, trends)
    section3 = generate_section3_news(stats)
    section4 = generate_section4_social(social_data)
    section5 = generate_section5_strategy(strategy_data)
    footer = generate_footer()

    full_message = header + section1 + section2 + section3 + section4 + section5 + footer

    # 텔레그램 메시지 분할 (4096자 제한)
    messages = split_telegram_message(full_message)

    # 아카이브 저장
    archive_dir = os.path.join(BASE_DIR, "data", "briefing_archive")
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, f"{target_date}.json")
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump({
            "date": target_date,
            "generated_at": datetime.now().isoformat(),
            "messages": messages,
            "full_text": full_message,
        }, f, ensure_ascii=False, indent=2)

    print(f"[OK] 브리핑 생성 완료 — {len(messages)}개 메시지, 총 {len(full_message)}자")
    return messages

def split_telegram_message(text, max_length=4000):
    """텔레그램 4096자 제한에 맞춰 메시지 분할"""
    if len(text) <= max_length:
        return [text]

    messages = []
    sections = text.split("\n\n")
    current = ""

    for section in sections:
        if len(current) + len(section) + 2 > max_length:
            if current:
                messages.append(current.strip())
            current = section
        else:
            current += "\n\n" + section if current else section

    if current.strip():
        messages.append(current.strip())

    # 분할된 메시지에 번호 표시
    if len(messages) > 1:
        for i in range(len(messages)):
            messages[i] = f"[{i+1}/{len(messages)}]\n{messages[i]}"

    return messages

def main():
    parser = argparse.ArgumentParser(description="박주민 브리핑 생성기")
    parser.add_argument("--date", default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()

    print(f"[START] 브리핑 생성 — {args.date}")
    messages = generate_full_briefing(args.date)
    for i, msg in enumerate(messages):
        print(f"\n{'='*50}")
        print(f"메시지 {i+1}/{len(messages)}:")
        print(msg)
    print(f"\n[DONE] 브리핑 생성 완료")

if __name__ == "__main__":
    main()
