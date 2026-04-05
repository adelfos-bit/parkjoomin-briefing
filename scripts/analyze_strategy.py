#!/usr/bin/env python3
"""박주민 서울시장 후보 — 정책전문가 전략 분석 엔진
Claude API를 활용한 일일 전략 브리핑 생성"""

import os, sys, json, argparse, requests
from datetime import datetime, timedelta

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

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

def load_daily_data(target_date):
    """당일 수집 데이터 로드"""
    news_path = os.path.join(BASE_DIR, "data", "news_daily", f"{target_date}.json")
    social_path = os.path.join(BASE_DIR, "data", "social_daily", f"{target_date}.json")

    news_data = {}
    social_data = {}

    if os.path.exists(news_path):
        with open(news_path, 'r', encoding='utf-8') as f:
            news_data = json.load(f)
    else:
        print(f"[WARN] 뉴스 데이터 없음: {news_path}")

    if os.path.exists(social_path):
        with open(social_path, 'r', encoding='utf-8') as f:
            social_data = json.load(f)
    else:
        print(f"[WARN] SNS 데이터 없음: {social_path}")

    return news_data, social_data

def load_previous_data(target_date):
    """전일 데이터 로드 (트렌드 비교용)"""
    prev_date = (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    news_path = os.path.join(BASE_DIR, "data", "news_daily", f"{prev_date}.json")
    if os.path.exists(news_path):
        with open(news_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def compute_trends(today_stats, prev_data):
    """전일 대비 트렌드 계산"""
    trends = {
        "article_change": 0,
        "sentiment_change": 0,
        "comment_change": 0,
        "alert_level": "normal",  # normal, warning, critical
        "alerts": [],
    }

    if not prev_data or "stats" not in prev_data:
        return trends

    prev_stats = prev_data["stats"]

    # 기사 수 변화
    today_count = today_stats.get("parkjoomin_articles", 0)
    prev_count = prev_stats.get("parkjoomin_articles", 0)
    trends["article_change"] = today_count - prev_count

    # 감성 변화
    today_pos = today_stats.get("sentiment", {}).get("pos_pct", 0)
    prev_pos = prev_stats.get("sentiment", {}).get("pos_pct", 0)
    trends["sentiment_change"] = today_pos - prev_pos

    # 위기 감지
    today_neg = today_stats.get("sentiment", {}).get("neg_pct", 0)
    if today_neg > 50:
        trends["alert_level"] = "critical"
        trends["alerts"].append("부정 여론 50% 초과 — 즉시 대응 필요")
    elif today_neg > 35:
        trends["alert_level"] = "warning"
        trends["alerts"].append("부정 여론 상승 경고 — 모니터링 강화")

    # 급상승 부정 기사 감지
    if trends["sentiment_change"] < -15:
        trends["alert_level"] = "critical"
        trends["alerts"].append(f"긍정률 급락 ({trends['sentiment_change']:+d}%p) — 원인 파악 시급")

    return trends

def build_strategy_prompt(news_data, social_data, trends, target_date):
    """Claude API용 전략 분석 프롬프트 생성"""
    stats = news_data.get("stats", {})
    articles = news_data.get("articles", [])

    # 주요 기사 요약 (상위 10건)
    top_articles_text = ""
    for i, art in enumerate(stats.get("top_articles", [])[:10], 1):
        sentiment_emoji = {"긍정": "😊", "부정": "😟", "중립": "🔵"}.get(art["sentiment"], "🔵")
        top_articles_text += f"{i}. [{art['sentiment']}{sentiment_emoji}] {art['title']}\n"
        top_articles_text += f"   댓글 {art['comments']['count']}건 (긍정 {art['comments']['pos_pct']}%)\n"

    # SNS 요약
    social_summary = ""
    channels = social_data.get("channels", {})
    if "youtube" in channels:
        yt = channels["youtube"]["data"]
        social_summary += f"유튜브: 관련 영상 {len(yt.get('videos', []))}건, 총 조회 {yt.get('total_views', 0):,}회\n"
    if "twitter" in channels:
        tw = channels["twitter"]["data"]
        social_summary += f"X(트위터): 멘션 {tw.get('total', 0)}건\n"
    if "community" in channels:
        cm = channels["community"]["data"]
        social_summary += f"커뮤니티: 게시글 {cm.get('total', 0)}건\n"

    # 키워드
    keywords_text = ", ".join([f"{k}({v}회)" for k, v in stats.get("top_keywords", [])])

    # 경쟁자 노출
    exposure = stats.get("candidate_exposure", {})
    exposure_text = ", ".join([f"{k}: {v}건" for k, v in sorted(exposure.items(), key=lambda x: -x[1])])

    # 부정 기사 리스트
    neg_articles = [a for a in articles if a.get("sentiment") == "부정" and a.get("is_parkjoomin")]
    neg_text = "\n".join([f"  - [{a['sentiment']}] {a['title']}" for a in neg_articles[:5]]) or "없음"

    # 경쟁자별 부정 기사 (공격 포인트)
    comp_weaknesses = ""
    for comp_name in ["오세훈", "정원오", "전현희"]:
        comp_neg = [a for a in articles if a.get("sentiment") == "부정" and comp_name in a.get("candidates_mentioned", [])]
        if comp_neg:
            comp_weaknesses += f"\n  {comp_name} 약점 기사: {comp_neg[0]['title']}"

    d_day = (datetime(2026, 6, 3) - datetime.strptime(target_date, '%Y-%m-%d')).days

    prompt = f"""당신은 박주민 서울시장 후보 캠프의 수석 전략참모입니다.
당신의 유일한 목표는 박주민의 당선입니다. 아래 오늘({target_date}, D-{d_day}) 수집 데이터를 분석해서 박주민 캠프에 전략 지시를 내려주세요.

## 오늘의 데이터

### 박주민 현황
- 기사 {stats.get('parkjoomin_articles', 0)}건 / 전체 {stats.get('total_articles', 0)}건
- 감성: 긍정 {stats.get('sentiment', {}).get('pos_pct', 0)}% / 부정 {stats.get('sentiment', {}).get('neg_pct', 0)}%
- 댓글 {stats.get('comments', {}).get('total', 0)}건: 👍{stats.get('comments', {}).get('pos_pct', 0)}% 👎{stats.get('comments', {}).get('neg_pct', 0)}%
- 전일 대비: 기사 {trends.get('article_change', 0):+d}건, 감성 {trends.get('sentiment_change', 0):+d}%p

### 박주민 관련 주요 기사 (감성 태그 포함)
{top_articles_text}

### 박주민 부정 기사 (위기 모니터링)
{neg_text}

### 경쟁자 미디어 노출 (위협도 순)
{exposure_text}

### 경쟁자 약점 (공격 포인트)
{comp_weaknesses if comp_weaknesses else "오늘 탐지된 약점 없음"}

### SNS 반응
{social_summary}

### 트렌드 키워드
{keywords_text}

---

아래 형식으로 **박주민 캠프 전략 지시서**를 작성하세요. 텔레그램 메시지로 전송되므로 간결하게 핵심만 작성하세요.

━━━ 핵심 진단 ━━━
(2-3문장. 오늘 박주민에게 가장 중요한 상황 판단. 수치 기반.)

🎯 핵심 미션
"(한 문장. 오늘 박주민이 집중해야 할 것)"

✅ 즉시 실행
⚡ (긴급 — 오늘 안에. 구체적으로 "무엇을" "어떻게")
📋 (중요 — 이번 주. 구체적 콘텐츠/행동)
🎯 (전략 — 경쟁자 대응. 누구를 어떻게)

⚡ 위기/기회
🔴 위기: (구체적 기사/이슈 기반)
🟢 기회: (활용 가능한 포인트)

🔮 내일 주목
(내일 모니터링해야 할 것 1-2개)

주의사항:
- "SNS 콘텐츠 다양화" 같은 뻔한 말 금지. 구체적 행동만.
- 경쟁자 약점이 있으면 활용 방법 제시
- 댓글 부정률이 높으면 왜 부정인지 분석하고 대응 방향 제시
- 모든 제안은 "박주민이 오늘/이번주 실행 가능한 것"이어야 함
- 800자 이내로 작성"""

    return prompt

def call_claude_api(prompt):
    """Claude API 호출"""
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.startswith("여기에"):
        print("[WARN] Claude API 키 없음 — 기본 전략 템플릿 사용")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except ImportError:
        # anthropic 라이브러리 없으면 requests로 직접 호출
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            data = resp.json()
            return data.get("content", [{}])[0].get("text", "")
        except Exception as e:
            print(f"[ERROR] Claude API 호출 실패: {e}")
            return None

def generate_fallback_strategy(news_data, trends):
    """API 없을 때 규칙 기반 전략 생성"""
    stats = news_data.get("stats", {})
    pos_pct = stats.get("sentiment", {}).get("pos_pct", 0)
    neg_pct = stats.get("sentiment", {}).get("neg_pct", 0)
    articles = stats.get("top_articles", [])

    # 부정 기사 중 가장 영향력 큰 것
    negative_articles = [a for a in articles if a.get("sentiment") == "부정"]
    positive_articles = [a for a in articles if a.get("sentiment") == "긍정"]

    strategy = {
        "core_diagnosis": "",
        "top_priority": "",
        "actions": [],
        "risks": [],
        "opportunities": [],
        "competitor_analysis": "",
        "tomorrow_focus": "",
    }

    # 키워드 감지
    keywords = [kw for kw, _ in stats.get("top_keywords", [])]
    pj_count = stats.get("parkjoomin_articles", 0)
    total = stats.get("total_articles", 0)
    exposure = stats.get("candidate_exposure", {})
    top_comp = max([(k, v) for k, v in exposure.items() if k != "박주민"], key=lambda x: x[1], default=("오세훈", 0))

    # 상황별 진단 (다층 분석)
    if neg_pct > 40:
        neg_title = negative_articles[0]['title'][:30] if negative_articles else "부정 기사"
        strategy["core_diagnosis"] = (
            f"🔴 위기 상황. 부정 여론 {neg_pct}%로 경고 수준. "
            f"'{neg_title}' 등 부정 기사 {len(negative_articles)}건 확인. 즉시 대응 필요."
        )
        strategy["top_priority"] = "부정 여론 확산 차단 — 해명 콘텐츠 3시간 내 배포"
    elif neg_pct > 25:
        strategy["core_diagnosis"] = (
            f"⚠️ 주의 필요. 부정 {neg_pct}%로 상승세. "
            f"부정 기사 {len(negative_articles)}건 모니터링 중. 선제 대응이 확산을 막는 열쇠."
        )
        strategy["top_priority"] = "부정 이슈 확산 전 선제 해명 + 긍정 의제 투입"
    elif pos_pct > 60:
        pos_title = positive_articles[0]['title'][:25] if positive_articles else "긍정 기사"
        strategy["core_diagnosis"] = (
            f"✅ 긍정 흐름 {pos_pct}%. '{pos_title}' 등 호응. "
            f"모멘텀 유지하며 부동층 공략 강화할 적기."
        )
        strategy["top_priority"] = "긍정 모멘텀 극대화 — 후속 콘텐츠 + 부동층 타겟"
    elif "경선" in keywords or "토론" in keywords:
        strategy["core_diagnosis"] = (
            f"📊 경선/토론 국면. 기사 {pj_count}건 중 경선·토론 키워드 집중. "
            f"당내 경쟁 속 차별화 메시지가 핵심. {top_comp[0]} {top_comp[1]}건 노출 중."
        )
        strategy["top_priority"] = "경선 토론 차별화 — 정책 비전 1~2개에 집중"
    elif "공약" in keywords or "부동산" in keywords or "주거" in keywords:
        strategy["core_diagnosis"] = (
            f"📋 정책 경쟁 국면. 공약/부동산/주거 관련 보도 집중. "
            f"구체적 수치와 실행력으로 차별화해야 함."
        )
        strategy["top_priority"] = "핵심 공약 숏폼 콘텐츠 — 경쟁자 대비 구체성 강조"
    else:
        strategy["core_diagnosis"] = (
            f"📊 보합세. 긍정 {pos_pct}%/부정 {neg_pct}%. "
            f"박주민 {pj_count}건 vs {top_comp[0]} {top_comp[1]}건. "
            f"적극적 의제 선점으로 여론 주도권 확보 필요."
        )
        strategy["top_priority"] = "차별화 의제 발굴 + 미디어 노출 확대"

    # 위기/기회
    if negative_articles:
        strategy["risks"].append(f"'{negative_articles[0]['title'][:30]}...' 관련 여론 악화 가능성")
    if positive_articles:
        strategy["opportunities"].append(f"'{positive_articles[0]['title'][:30]}...' 호응 → 추가 콘텐츠 기회")

    # 경쟁자
    exposure = stats.get("candidate_exposure", {})
    top_competitor = max(
        [(k, v) for k, v in exposure.items() if k != "박주민"],
        key=lambda x: x[1], default=("오세훈", 0)
    )
    strategy["competitor_analysis"] = (
        f"{top_competitor[0]} 미디어 노출 {top_competitor[1]}건으로 가장 활발. "
        f"대응 포인트 점검 필요."
    )

    strategy["tomorrow_focus"] = "내일 뉴스 트렌드 변화 및 경쟁자 공약 발표 모니터링"

    return strategy

def analyze(target_date):
    """전략 분석 실행"""
    news_data, social_data = load_daily_data(target_date)
    prev_data = load_previous_data(target_date)

    if not news_data:
        print("[ERROR] 뉴스 데이터가 없어 분석을 중단합니다.")
        return None

    stats = news_data.get("stats", {})
    trends = compute_trends(stats, prev_data)

    # Claude API 전략 분석
    prompt = build_strategy_prompt(news_data, social_data, trends, target_date)
    ai_strategy = call_claude_api(prompt)

    # API 실패 시 규칙 기반 fallback
    if not ai_strategy:
        fallback = generate_fallback_strategy(news_data, trends)
        ai_strategy = None
    else:
        fallback = None

    result = {
        "date": target_date,
        "analyzed_at": datetime.now().isoformat(),
        "news_stats": stats,
        "trends": trends,
        "social_summary": {
            ch: {
                "status": data.get("status", ""),
                "count": len(data.get("data", {}).get("videos", data.get("data", {}).get("mentions", data.get("data", {}).get("posts", [])))),
            }
            for ch, data in social_data.get("channels", {}).items()
        },
        "ai_strategy": ai_strategy,
        "fallback_strategy": fallback,
    }

    # 저장
    data_dir = os.path.join(BASE_DIR, "data", "strategy_daily")
    os.makedirs(data_dir, exist_ok=True)
    filepath = os.path.join(data_dir, f"{target_date}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[OK] 전략 분석 저장: {filepath}")

    return result

def main():
    parser = argparse.ArgumentParser(description="박주민 전략 분석")
    parser.add_argument("--date", default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()

    print(f"[START] 전략 분석 시작 — {args.date}")
    result = analyze(args.date)
    if result:
        level = result["trends"]["alert_level"]
        print(f"[INFO] 경보 수준: {level}")
        print("[DONE] 전략 분석 완료")
    else:
        print("[FAIL] 전략 분석 실패")

if __name__ == "__main__":
    main()
