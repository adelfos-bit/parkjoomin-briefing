#!/usr/bin/env python3
"""박주민 캠프 일일 전략 보고서 — 텔레그램 브리핑 v3 (박주민 전용)"""

import os, sys, json, argparse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
ELECTION_DATE = datetime(2026, 6, 3)

def bar(value, max_val=100, length=10):
    filled = int(value / max_val * length) if max_val > 0 else 0
    return "█" * min(filled, length) + "░" * (length - min(filled, length))

def fmt(n):
    if n >= 10000: return f"{n/10000:.1f}만"
    if n >= 1000: return f"{n:,}"
    return str(n)

def delta(change):
    if change > 0: return f"+{change}▲"
    if change < 0: return f"{change}▼"
    return "→"

# ═══════════════════════════════════════════════════
#  헤더
# ═══════════════════════════════════════════════════
def section_header(target_date):
    dt = datetime.strptime(target_date, '%Y-%m-%d')
    d = (ELECTION_DATE - dt).days
    return f"""━━━━━━━━━━━━━━━━━━━━━━━━━
📅 {target_date} ({WEEKDAYS[dt.weekday()]})
🔵 박주민 일일 전략 보고서
🗳️ 6.3 지방선거 D-{d}
━━━━━━━━━━━━━━━━━━━━━━━━━"""

# ═══════════════════════════════════════════════════
#  1. 오늘의 박주민
# ═══════════════════════════════════════════════════
def section_today(stats, trends):
    s = stats.get("sentiment", {})
    pos, neg = s.get("pos_pct", 0), s.get("neg_pct", 0)
    c = stats.get("comments", {})
    c_total, c_pos, c_neg = c.get("total", 0), c.get("pos_pct", 0), c.get("neg_pct", 0)
    pj = stats.get("parkjoomin_articles", 0)
    total = stats.get("total_articles", 0)

    # 종합 점수 (간이)
    score = min(100, int(pos * 0.4 + (100 - neg) * 0.3 + min(pj, 100) * 0.3))

    return f"""
📊 【1. 오늘의 박주민】

  📈 종합지수 {score}/100  {bar(score)}
  ┌─────────────────────────
  │ 기사  {pj}건 ({delta(trends.get('article_change', 0))})
  │ 댓글  {fmt(c_total)}건
  │ 감성  긍정{pos}% {bar(pos)}
  │       부정{neg}% {bar(neg)}
  │ 댓글  👍{c_pos}% 👎{c_neg}% {bar(c_pos)}
  └─────────────────────────"""

# ═══════════════════════════════════════════════════
#  2. 박주민 핵심 뉴스
# ═══════════════════════════════════════════════════
def section_news(stats, all_articles):
    # 박주민 기사만 + 댓글 많은 순
    pj = [a for a in all_articles if a.get("is_parkjoomin")]
    pj.sort(key=lambda x: x.get("comments", {}).get("count", 0), reverse=True)

    text = "\n📰 【2. 박주민 핵심 뉴스】\n"
    for i, art in enumerate(pj[:5], 1):
        emoji = {"긍정": "😊", "부정": "😟", "중립": "🔵"}.get(art.get("sentiment", "중립"), "🔵")
        cc = art.get("comments", {}).get("count", 0)
        if cc > 0:
            cp = art["comments"].get("pos_pct", 0)
            cn = art["comments"].get("neg_pct", 0)
            cstr = f" 💬{cc}건 👍{cp}%👎{cn}%"
        else:
            cstr = ""
        text += f"  {i}. {emoji} {art['title'][:42]}{cstr}\n"

    return text

# ═══════════════════════════════════════════════════
#  3. 경쟁자 위협 분석 (핵심 변경!)
# ═══════════════════════════════════════════════════
def section_competitors(stats, all_articles):
    exposure = stats.get("candidate_exposure", {})
    pj_count = exposure.get("박주민", 0)

    # 경쟁자를 위협도 순으로 (노출 많은 순, 0건 제외)
    competitors = []
    for name, count in exposure.items():
        if name == "박주민" or count == 0:
            continue
        competitors.append((name, count))
    competitors.sort(key=lambda x: -x[1])

    if not competitors:
        return "\n🔍 【3. 경쟁자】\n  오늘 경쟁자 노출 없음\n"

    # 경선 vs 본선 구분
    민주 = ["정원오", "전현희", "우상호", "송영길", "김두관"]
    국힘 = ["오세훈"]

    text = "\n🔍 【3. 경쟁자 위협 분석】\n"

    for name, count in competitors[:4]:
        gap = count - pj_count
        if gap > 0:
            gap_str = f"박주민보다 +{gap}건"
        elif gap < 0:
            gap_str = f"박주민보다 {gap}건"
        else:
            gap_str = "박주민과 동률"

        # 경선/본선 라벨
        if name in 국힘:
            label = "본선 상대"
        elif name in 민주:
            label = "경선 경쟁"
        else:
            label = "기타"

        # 해당 경쟁자 TOP 기사 1건 (박주민과 무관한 기사)
        comp_articles = [a for a in all_articles
                        if name in a.get("candidates_mentioned", [])
                        and not a.get("is_parkjoomin")]
        if not comp_articles:
            comp_articles = [a for a in all_articles
                           if name in a.get("candidates_mentioned", [])]

        news_title = comp_articles[0]["title"][:35] if comp_articles else "관련 기사 없음"

        # 부정 기사 찾기 → 공격 포인트
        comp_neg = [a for a in comp_articles if a.get("sentiment") == "부정"]
        if comp_neg:
            attack = f"💡 약점: \"{comp_neg[0]['title'][:30]}\""
        else:
            attack = ""

        # 위협도 바 (박주민 대비)
        threat_pct = min(100, int(count / max(pj_count, 1) * 100))
        threat_bar = bar(threat_pct)

        text += f"\n  ⚔️ {name} [{label}]\n"
        text += f"    위협도 {threat_bar} {count}건 ({gap_str})\n"
        text += f"    📰 \"{news_title}\"\n"
        if attack:
            text += f"    {attack}\n"

    return text

# ═══════════════════════════════════════════════════
#  4. 오늘의 전략 지시
# ═══════════════════════════════════════════════════
def section_strategy(strategy_data, stats, all_articles):
    ai = strategy_data.get("ai_strategy")
    if ai:
        lines = ai.strip().split('\n')
        return "\n🧠 【4. 오늘의 전략 지시】\n\n" + '\n'.join(lines[:45])

    # ── Fallback 전략 (데이터 기반) ──
    exposure = stats.get("candidate_exposure", {})
    pj_count = exposure.get("박주민", 0)
    s = stats.get("sentiment", {})
    pos, neg = s.get("pos_pct", 0), s.get("neg_pct", 0)
    c = stats.get("comments", {})
    keywords = [kw for kw, _ in stats.get("top_keywords", [])]

    # 경쟁자 위협 1위
    top_threat = max(
        [(k, v) for k, v in exposure.items() if k != "박주민" and v > 0],
        key=lambda x: x[1], default=("없음", 0)
    )

    # 박주민 부정/긍정 기사
    pj_neg = [a for a in all_articles if a.get("sentiment") == "부정" and a.get("is_parkjoomin")]
    pj_pos = [a for a in all_articles if a.get("sentiment") == "긍정" and a.get("is_parkjoomin")]

    # ── 핵심 미션 (상황별) ──
    if neg > 30:
        mission = f"부정 여론({neg}%) 긴급 방어 — 해명 콘텐츠 즉시 배포"
    elif "경선" in keywords or "토론" in keywords:
        if top_threat[0] in ["정원오", "전현희"]:
            mission = f"경선 토론에서 {top_threat[0]}과 차별화 — 정책 구체성으로 승부"
        else:
            mission = "경선 토론 차별화 — 핵심 정책 비전 1~2개 집중"
    elif "공약" in keywords or "부동산" in keywords:
        mission = "공약 경쟁 주도 — 구체적 수치와 실행력으로 차별화"
    elif pos > 60:
        mission = "긍정 모멘텀 극대화 — 후속 콘텐츠 + 부동층 공략"
    else:
        mission = f"의제 선점으로 {top_threat[0]}({top_threat[1]}건) 추격"

    # ── 즉시 실행 (오늘 데이터 기반) ──
    actions = []

    # 액션1: 가장 긴급한 것
    if pj_neg:
        actions.append(f"⚡ \"{pj_neg[0]['title'][:25]}\" 관련 입장 정리/반박")
    elif "토론" in keywords:
        actions.append("⚡ 토론 하이라이트 숏폼 → 유튜브/인스타 즉시 배포")
    else:
        actions.append("⚡ 오늘 뉴스 사이클 대응 논평 SNS 배포")

    # 액션2: 공약/콘텐츠
    if pj_pos:
        actions.append(f"📋 \"{pj_pos[0]['title'][:25]}\" 후속 카드뉴스 제작")
    elif "공약" in keywords:
        actions.append("📋 공약 비교 콘텐츠 — 경쟁자 대비 차별점 시각화")
    else:
        actions.append("📋 이번 주 핵심 이슈 선점 콘텐츠 기획")

    # 액션3: 경쟁자 대응
    comp_neg = [a for a in all_articles if a.get("sentiment") == "부정"
                and top_threat[0] in a.get("candidates_mentioned", [])
                and not a.get("is_parkjoomin")]
    if comp_neg:
        actions.append(f"🎯 {top_threat[0]} 약점 \"{comp_neg[0]['title'][:20]}\" 활용 대비")
    elif top_threat[1] > pj_count:
        actions.append(f"🎯 {top_threat[0]}({top_threat[1]}건) 미디어 추격 — 인터뷰/기고 기획")
    else:
        actions.append("🎯 지지층 결집 메시지 + 부동층 타겟 비교 콘텐츠")

    actions_text = "\n".join(f"  {a}" for a in actions)

    # ── 위기/기회 ──
    risk = ""
    if pj_neg:
        c_info = pj_neg[0].get("comments", {})
        if c_info.get("count", 0) > 0:
            risk = f"  🔴 \"{pj_neg[0]['title'][:30]}\" 댓글 부정{c_info.get('neg_pct',0)}% — 확산 주의"
        else:
            risk = f"  🔴 \"{pj_neg[0]['title'][:30]}\" — 모니터링 필요"
    elif c.get("neg_pct", 0) > 30:
        risk = f"  🔴 댓글 부정률 {c['neg_pct']}% — 여론 반전 주의"
    else:
        risk = "  🔴 특별한 위기 없음"

    if pj_pos:
        opp = f"  🟢 \"{pj_pos[0]['title'][:30]}\" → 후속 콘텐츠 적기"
    else:
        opp = "  🟢 긍정 기사 부족 → 의제 선점 콘텐츠 필요"

    return f"""
🧠 【4. 오늘의 전략 지시】

  🎯 핵심 미션
  "{mission}"

  ✅ 즉시 실행
{actions_text}

  ⚡ 위기/기회
{risk}
{opp}"""

# ═══════════════════════════════════════════════════
#  5. SNS 전황
# ═══════════════════════════════════════════════════
def section_sns(social_data, stats=None):
    channels = social_data.get("channels", {})
    lines = []

    # 키워드 트렌드 (stats에서)
    if stats:
        keywords = stats.get("top_keywords", [])
        if keywords:
            kw_text = " ".join([f"#{kw}({c})" for kw, c in keywords[:5]])
            lines.append(f"  🔑 {kw_text}")

    if "youtube" in channels:
        yt = channels["youtube"]["data"]
        videos = yt.get("videos", [])
        if videos:
            top = max(videos, key=lambda v: v.get("views", 0))
            lines.append(f"  ▶️ 유튜브 {len(videos)}건 | 🔥 \"{top['title'][:30]}\" {fmt(top['views'])}회")

    if "twitter_sns" in channels:
        tw = channels["twitter_sns"]["data"]
        if tw.get("total", 0) > 0:
            lines.append(f"  🐦 X {tw.get('x_count',0)}건 + SNS {tw['total'] - tw.get('x_count',0)}건")

    if "community" in channels:
        cm = channels["community"]["data"]
        if cm.get("total", 0) > 0:
            lines.append(f"  🗣️ 커뮤니티 {cm['total']}건")

    if not lines:
        return ""

    return "\n📱 【5. SNS 전황】\n" + "\n".join(lines)

# ═══════════════════════════════════════════════════
#  푸터
# ═══════════════════════════════════════════════════
def section_footer(target_date):
    dt = datetime.strptime(target_date, '%Y-%m-%d')
    d = (ELECTION_DATE - dt).days
    return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━
🗳️ D-{d} | 박주민 캠프 전략실
━━━━━━━━━━━━━━━━━━━━━━━━━"""

# ═══════════════════════════════════════════════════
#  전체 조립
# ═══════════════════════════════════════════════════
def generate_full_briefing(target_date):
    strategy_path = os.path.join(BASE_DIR, "data", "strategy_daily", f"{target_date}.json")
    news_path = os.path.join(BASE_DIR, "data", "news_daily", f"{target_date}.json")
    social_path = os.path.join(BASE_DIR, "data", "social_daily", f"{target_date}.json")

    strategy_data, news_data, social_data = {}, {}, {}
    for path, target in [(strategy_path, "strategy"), (news_path, "news"), (social_path, "social")]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                d = json.load(f)
                if target == "strategy": strategy_data = d
                elif target == "news": news_data = d
                else: social_data = d

    stats = news_data.get("stats", strategy_data.get("news_stats", {}))
    trends = strategy_data.get("trends", {})
    articles = news_data.get("articles", [])

    parts = [
        section_header(target_date),
        section_today(stats, trends),
        section_news(stats, articles),
        section_competitors(stats, articles),
        section_strategy(strategy_data, stats, articles),
        section_sns(social_data, stats),
        section_footer(target_date),
    ]

    full = "".join(p for p in parts if p)
    messages = split_message(full)

    archive_dir = os.path.join(BASE_DIR, "data", "briefing_archive")
    os.makedirs(archive_dir, exist_ok=True)
    with open(os.path.join(archive_dir, f"{target_date}.json"), 'w', encoding='utf-8') as f:
        json.dump({"date": target_date, "generated_at": datetime.now().isoformat(),
                    "messages": messages, "full_text": full}, f, ensure_ascii=False, indent=2)

    print(f"[OK] 브리핑 생성 완료 — {len(messages)}개 메시지, 총 {len(full)}자")
    return messages

def split_message(text, limit=4000):
    if len(text) <= limit:
        return [text]
    msgs, cur = [], ""
    for sec in text.split("\n\n"):
        if len(cur) + len(sec) + 2 > limit:
            if cur: msgs.append(cur.strip())
            cur = sec
        else:
            cur += "\n\n" + sec if cur else sec
    if cur.strip(): msgs.append(cur.strip())
    if len(msgs) > 1:
        msgs = [f"[{i+1}/{len(msgs)}]\n{m}" for i, m in enumerate(msgs)]
    return msgs

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()
    print(f"[START] 브리핑 생성 — {args.date}")
    msgs = generate_full_briefing(args.date)
    for i, m in enumerate(msgs):
        print(f"\n{'='*50}\n메시지 {i+1}/{len(msgs)}:\n{m}")
    print(f"\n[DONE] 브리핑 생성 완료")

if __name__ == "__main__":
    main()
