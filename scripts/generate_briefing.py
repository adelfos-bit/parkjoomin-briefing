#!/usr/bin/env python3
"""박주민 서울시장 후보 — 텔레그램 브리핑 메시지 생성기 (v2 대폭 개선)"""

import os, sys, json, argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
ELECTION_DATE = datetime(2026, 6, 3)  # 6.3 지방선거

def bar(value, max_val=100, length=15):
    filled = int(value / max_val * length) if max_val > 0 else 0
    filled = min(filled, length)
    return "█" * filled + "░" * (length - filled)

def trend_arrow(change):
    if change > 0:
        return f"+{change} ▲"
    elif change < 0:
        return f"{change} ▼"
    return "→"

def format_number(n):
    if n >= 10000:
        return f"{n/10000:.1f}만"
    elif n >= 1000:
        return f"{n:,}"
    return str(n)

# ──────────────────── 헤더 + D-day ────────────────────
def generate_header(target_date):
    dt = datetime.strptime(target_date, '%Y-%m-%d')
    weekday = WEEKDAYS[dt.weekday()]
    d_day = (ELECTION_DATE - dt).days

    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {target_date} ({weekday}) 박주민 일일 브리핑
🗳️ 6.3 지방선거 D-{d_day}
━━━━━━━━━━━━━━━━━━━━━━━━━"""

# ──────────────────── 섹션1: 현황 대시보드 ────────────────────
def generate_section1_dashboard(stats, trends):
    sentiment = stats.get("sentiment", {})
    pos = sentiment.get("pos_pct", 0)
    neg = sentiment.get("neg_pct", 0)
    neu = sentiment.get("neu_pct", 0)
    comments = stats.get("comments", {})
    exposure = stats.get("candidate_exposure", {})

    sentiment_change = trends.get("sentiment_change", 0)

    # 경쟁 구도 — 0건 후보 자동 숨김
    sorted_candidates = sorted(exposure.items(), key=lambda x: -x[1])
    active_candidates = [(name, count) for name, count in sorted_candidates if count > 0]

    competition_text = ""
    max_count = active_candidates[0][1] if active_candidates else 1
    pj_rank = 0
    for i, (name, count) in enumerate(active_candidates[:6], 1):
        if name == "박주민":
            emoji = "🔵"
            pj_rank = i
        else:
            emoji = "⚪"
        cbar = bar(count, max_count, 10)
        competition_text += f"  {i}위 {emoji}{name} {cbar} {count}건\n"

    # 댓글 감성
    c_total = comments.get('total', 0)
    c_pos = comments.get('pos_pct', 0)
    c_neg = comments.get('neg_pct', 0)
    c_neu = comments.get('neu_pct', 0)

    alert_emoji = {"normal": "🟢", "warning": "🟡", "critical": "🔴"}.get(
        trends.get("alert_level", "normal"), "🟢"
    )
    alert_text = chr(10).join('  ⚠️ ' + a for a in trends.get('alerts', []))

    return f"""
📊 【1. 현황 대시보드】

🔥 기사 감성
  {bar(pos)} 긍정 {pos}%
  긍정 {pos}% | 부정 {neg}% | 중립 {neu}%
  전일 대비: {trend_arrow(sentiment_change)}

📰 미디어 노출
  전체 {stats.get('total_articles', 0)}건 | 박주민 {stats.get('parkjoomin_articles', 0)}건 ({trend_arrow(trends.get('article_change', 0))})

💬 댓글 ({format_number(c_total)}건)
  {bar(c_pos)} 👍{c_pos}% 👎{c_neg}% 중립{c_neu}%

🏆 미디어 경쟁 (박주민 {pj_rank}위)
{competition_text}
{alert_emoji} {trends.get('alert_level', 'normal').upper()}{(' | ' + alert_text.strip()) if alert_text.strip() else ''}"""

# ──────────────────── 섹션2: 주요 뉴스 + 경쟁자 동향 ────────────────────
def generate_section2_news(stats, all_articles):
    # 박주민 관련 TOP 5 (댓글 있는 기사 우선)
    pj_articles = [a for a in stats.get("top_articles", []) if a.get("is_parkjoomin")]
    # 댓글 있는 기사를 앞으로
    pj_articles.sort(key=lambda x: x.get("comments", {}).get("count", 0), reverse=True)
    top5 = pj_articles[:5]

    news_text = ""
    for i, art in enumerate(top5, 1):
        emoji = {"긍정": "😊", "부정": "😟", "중립": "🔵"}.get(art.get("sentiment", "중립"), "🔵")
        c = art.get("comments", {})
        c_count = c.get('count', 0)
        if c_count > 0:
            c_pos = c.get('pos_pct', 0)
            c_neg = 100 - c_pos - c.get('neu_pct', 0) if c_count > 0 else 0
            comment_str = f"💬{c_count}건 👍{c_pos}% 👎{c_neg}%"
        else:
            comment_str = ""
        news_text += f"  {i}. [{art['sentiment']}{emoji}] {art['title'][:45]}\n"
        if comment_str:
            news_text += f"     {comment_str}\n"

    # 경쟁자 TOP 뉴스 (후보별 최신 1건)
    competitor_text = ""
    competitors = ["오세훈", "정원오", "전현희", "우상호", "송영길", "김두관"]
    for comp in competitors:
        comp_articles = [a for a in all_articles if comp in a.get("candidates_mentioned", []) and not a.get("is_parkjoomin")]
        if comp_articles:
            top = comp_articles[0]
            competitor_text += f"  ▸ {comp}: {top['title'][:40]}\n"

    section = f"""
📰 【2. 박주민 주요 뉴스】
{news_text}"""

    if competitor_text:
        section += f"""
🔍 경쟁자 동향
{competitor_text}"""

    return section

# ──────────────────── 섹션3: 키워드 + SNS ────────────────────
def generate_section3_trends_social(stats, social_data):
    keywords = stats.get("top_keywords", [])
    kw_text = " | ".join([f"#{kw}({count})" for kw, count in keywords[:7]])

    channels = social_data.get("channels", {})
    social_lines = []

    if "youtube" in channels:
        yt = channels["youtube"]["data"]
        videos = yt.get("videos", [])
        if videos:
            social_lines.append(f"  ▶️ 유튜브 {len(videos)}건, 조회 {format_number(yt.get('total_views', 0))}회")
            # 인기 영상 1개
            top_vid = max(videos, key=lambda v: v.get("views", 0))
            social_lines.append(f"     🔥 \"{top_vid['title'][:35]}\" ({format_number(top_vid['views'])}회)")

    if "twitter_sns" in channels:
        tw = channels["twitter_sns"]["data"]
        x_count = tw.get('x_count', 0)
        total = tw.get('total', 0)
        if total > 0:
            social_lines.append(f"  🐦 X {x_count}건 + SNS 언급 {total - x_count}건")
    elif "twitter" in channels:
        tw = channels["twitter"]["data"]
        if tw.get('total', 0) > 0:
            social_lines.append(f"  🐦 X(트위터) {tw['total']}건")

    if "community" in channels:
        cm = channels["community"]["data"]
        if cm.get('total', 0) > 0:
            social_lines.append(f"  🗣️ 커뮤니티 {cm['total']}건")

    social_text = "\n".join(social_lines) if social_lines else "  수집 데이터 없음"

    return f"""
📈 【3. 키워드 & SNS】
  {kw_text}

📱 SNS 반응
{social_text}"""

# ──────────────────── 섹션4: 전략 (핵심) ────────────────────
def generate_section4_strategy(strategy_data, stats, all_articles):
    # AI 전략
    ai = strategy_data.get("ai_strategy")
    if ai:
        lines = ai.strip().split('\n')
        truncated = '\n'.join(lines[:45])
        return f"""
🧠 【4. 정책전문가 전략】

{truncated}"""

    # Fallback — 고도화 버전
    fb = strategy_data.get("fallback_strategy", {})
    if not fb:
        return "\n🧠 【4. 전략】\n  데이터 부족"

    # 경쟁자별 핵심 동향 파악
    exposure = stats.get("candidate_exposure", {})
    pj_count = exposure.get("박주민", 0)
    top_comp_name, top_comp_count = "오세훈", 0
    for name, count in exposure.items():
        if name != "박주민" and count > top_comp_count:
            top_comp_name, top_comp_count = name, count

    # 노출 격차 분석
    gap = top_comp_count - pj_count
    if gap > 20:
        gap_analysis = f"⚠️ {top_comp_name} 대비 {gap}건 뒤처짐 — 미디어 노출 강화 시급"
    elif gap > 0:
        gap_analysis = f"📊 {top_comp_name}과 {gap}건 차이 — 추격 가능 범위"
    elif gap == 0:
        gap_analysis = f"📊 {top_comp_name}과 동률 — 모멘텀 확보가 관건"
    else:
        gap_analysis = f"✅ {top_comp_name} 대비 {-gap}건 앞서는 중 — 흐름 유지"

    # 부정 기사 탐지 → 구체적 위기
    neg_articles = [a for a in all_articles if a.get("sentiment") == "부정" and a.get("is_parkjoomin")]
    pos_articles = [a for a in all_articles if a.get("sentiment") == "긍정" and a.get("is_parkjoomin")]

    risk_text = ""
    if neg_articles:
        top_neg = neg_articles[0]
        risk_text = f"  🔴 \"{top_neg['title'][:35]}\" — 부정 확산 주의"
    else:
        risk_text = "  🔴 현재 특별한 위기 없음"

    opp_text = ""
    if pos_articles:
        top_pos = pos_articles[0]
        opp_text = f"  🟢 \"{top_pos['title'][:35]}\" — 후속 콘텐츠 기회"
    else:
        opp_text = "  🟢 긍정 기사 부족 — 의제 선점 필요"

    # 키워드 기반 구체적 액션
    keywords = [kw for kw, _ in stats.get("top_keywords", [])]
    if "경선" in keywords or "토론" in keywords:
        action1 = "[긴급] 경선 토론 준비 — 핵심 차별화 메시지 3개 정리"
    elif neg_articles:
        action1 = f"[긴급] \"{neg_articles[0]['title'][:20]}...\" 관련 해명/입장 정리"
    else:
        action1 = "[긴급] 오늘 뉴스 사이클 대응 — 논평/SNS 콘텐츠 배포"

    if "공약" in keywords or "정책" in keywords:
        action2 = "[중요] 공약 후속 콘텐츠 — 카드뉴스/숏폼 제작 배포"
    elif "부동산" in keywords or "주거" in keywords:
        action2 = "[중요] 부동산/주거 정책 비교표 — 오세훈 대비 차별점 부각"
    else:
        action2 = "[중요] 이번 주 핵심 이슈 선점 콘텐츠 기획"

    if pj_count < top_comp_count:
        action3 = f"[전략] 미디어 노출 강화 — {top_comp_name}({top_comp_count}건) 추격 필요"
    else:
        action3 = "[전략] 지지층 결집 + 부동층 공략 — 비교 콘텐츠 강화"

    return f"""
🧠 【4. 정책전문가 전략】

━━━ 핵심 진단 ━━━
{fb.get('core_diagnosis', '')}
{gap_analysis}

🎯 최우선: {fb.get('top_priority', '')}

✅ 오늘의 액션
  {action1}
  {action2}
  {action3}

⚡ 위기/기회
{risk_text}
{opp_text}

🏁 {top_comp_name} 동향: 노출 {top_comp_count}건"""

# ──────────────────── 푸터 ────────────────────
def generate_footer(target_date):
    dt = datetime.strptime(target_date, '%Y-%m-%d')
    d_day = (ELECTION_DATE - dt).days
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 자동생성 | {datetime.now().strftime('%H:%M')} 기준
🗳️ D-{d_day} | 정책전문가 + 데이터사이언티스트 분석
━━━━━━━━━━━━━━━━━━━━━━━━━"""

# ──────────────────── 전체 생성 ────────────────────
def generate_full_briefing(target_date):
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
    all_articles = news_data.get("articles", [])

    header = generate_header(target_date)
    s1 = generate_section1_dashboard(stats, trends)
    s2 = generate_section2_news(stats, all_articles)
    s3 = generate_section3_trends_social(stats, social_data)
    s4 = generate_section4_strategy(strategy_data, stats, all_articles)
    footer = generate_footer(target_date)

    full_message = header + s1 + s2 + s3 + s4 + footer

    messages = split_telegram_message(full_message)

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
