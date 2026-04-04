#!/usr/bin/env python3
"""박주민 서울시장 후보 — 정책전문가 전략 분석 엔진
Claude API를 활용한 일일 전략 브리핑 생성"""

import os, sys, json, argparse
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

    prompt = f"""당신은 대한민국 선거 전문 정치컨설턴트이자 데이터 사이언티스트입니다.
아래는 2026년 서울시장 선거 후보 '박주민'에 대한 {target_date} 일일 수집 데이터입니다.

## 오늘의 데이터 요약

### 뉴스 현황
- 전체 관련 기사: {stats.get('total_articles', 0)}건
- 박주민 직접 언급: {stats.get('parkjoomin_articles', 0)}건
- 감성 분포: 긍정 {stats.get('sentiment', {}).get('pos_pct', 0)}% / 부정 {stats.get('sentiment', {}).get('neg_pct', 0)}% / 중립 {stats.get('sentiment', {}).get('neu_pct', 0)}%
- 전일 대비: 기사 {trends.get('article_change', 0):+d}건, 긍정률 {trends.get('sentiment_change', 0):+d}%p
- 댓글 반응: 총 {stats.get('comments', {}).get('total', 0)}건 (긍정 {stats.get('comments', {}).get('pos_pct', 0)}%)

### 주요 기사 TOP 10
{top_articles_text}

### SNS 반응
{social_summary}

### 급상승 키워드
{keywords_text}

### 경쟁자 미디어 노출
{exposure_text}

### 위기 알림
경보 수준: {trends.get('alert_level', 'normal')}
{chr(10).join(trends.get('alerts', ['없음']))}

---

위 데이터를 기반으로 아래 형식에 맞춰 일일 전략 브리핑을 작성해주세요:

1. **오늘의 핵심 진단** (2-3문장): 박주민 후보의 오늘 미디어/여론 상황을 정책전문가 관점에서 진단

2. **최우선 과제** (1가지): 오늘 가장 시급하게 대응해야 할 것

3. **실행 액션 3가지**: 구체적이고 실행 가능한 액션
   - [긴급] 24시간 내 실행
   - [중요] 이번 주 내 실행
   - [전략] 중장기 포석

4. **위기/기회 알림**: 현재 감지된 위기와 기회 각 1-2개

5. **경쟁자 동향 분석**: 오세훈 등 주요 경쟁자의 움직임과 대응 방향

6. **내일 주목 포인트**: 내일 주의 깊게 봐야 할 것

반드시 데이터에 기반해서 분석하고, 추상적 제안이 아닌 구체적 실행 방안을 제시하세요.
한국어로 작성하세요."""

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

    # 상황별 진단
    if neg_pct > 40:
        strategy["core_diagnosis"] = (
            f"부정 여론이 {neg_pct}%로 경고 수준입니다. "
            f"부정 기사 {len(negative_articles)}건이 확인되며, 적극적 대응이 필요합니다."
        )
        strategy["top_priority"] = "부정 여론 확산 차단 및 해명 콘텐츠 즉시 배포"
        strategy["actions"] = [
            "[긴급] 부정 기사 관련 공식 입장문/해명 영상 제작",
            "[중요] 지지층 결집 메시지 SNS 집중 배포",
            "[전략] 정책 비전 재정립 — 긍정 의제 선점",
        ]
    elif pos_pct > 60:
        strategy["core_diagnosis"] = (
            f"긍정 여론 {pos_pct}%로 양호한 흐름입니다. "
            f"이 모멘텀을 유지하며 부동층 공략을 강화할 시점입니다."
        )
        strategy["top_priority"] = "긍정 흐름 유지 + 부동층 타겟 콘텐츠 확대"
        strategy["actions"] = [
            "[긴급] 호응 받은 정책 관련 후속 콘텐츠 제작",
            "[중요] 부동층 대상 비교 콘텐츠 (vs 오세훈) 준비",
            "[전략] 지지율 상승 시나리오별 경선 전략 점검",
        ]
    else:
        strategy["core_diagnosis"] = (
            f"중립적 여론 상황 (긍정 {pos_pct}%/부정 {neg_pct}%)입니다. "
            f"적극적 의제 선점으로 여론 주도권을 확보할 필요가 있습니다."
        )
        strategy["top_priority"] = "차별화된 정책 의제 발굴 및 미디어 노출 확대"
        strategy["actions"] = [
            "[긴급] 주요 현안 관련 논평/기자회견 기획",
            "[중요] SNS 콘텐츠 다양화 (숏폼/카드뉴스/라이브)",
            "[전략] 핵심 지지층 네트워크 확대 — 시민단체/직능단체 접촉",
        ]

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
