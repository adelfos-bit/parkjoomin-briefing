#!/usr/bin/env python3
"""박주민 서울시장 후보 뉴스 수집기 — 네이버 뉴스 API + 댓글 크롤링 + 감성분석"""

import os, sys, json, re, time, argparse
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

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

NAVER_CLIENT_ID = os.environ.get('NAVER_CLIENT_ID', '')
NAVER_CLIENT_SECRET = os.environ.get('NAVER_CLIENT_SECRET', '')

# ──────────────────── 검색 키워드 ────────────────────
PRIMARY_KEYWORDS = [
    "박주민", "박주민 서울시장", "박주민 후보", "박주민 공약",
    "박주민 출마", "박주민 민주당",
]
COMPETITOR_KEYWORDS = [
    "서울시장 선거 2026", "서울시장 후보",
    "서울시장 오세훈", "서울시장 여론조사",
    "서울시장 민주당 경선",
]
ISSUE_KEYWORDS = [
    "서울시장 교통", "서울시장 주거", "서울시장 청년",
    "서울시장 재개발", "서울시장 기후", "서울시장 복지",
]
ALL_KEYWORDS = PRIMARY_KEYWORDS + COMPETITOR_KEYWORDS + ISSUE_KEYWORDS

# ──────────────────── 감성분석 사전 ────────────────────
POSITIVE_WORDS = {
    # 정책/공약 관련 (가중치 2)
    "공약": 2, "정책": 2, "비전": 2, "혁신": 2, "개혁": 2,
    "청년": 1, "복지": 1, "교통": 1, "주거": 1, "일자리": 1,
    # 평가 관련
    "지지": 2, "호응": 2, "기대": 2, "환영": 2, "성과": 2,
    "능력": 1, "전문": 1, "경험": 1, "리더십": 1, "소통": 1,
    "압도": 2, "선두": 2, "약진": 2, "상승": 1, "강세": 1,
    "호감": 1, "신뢰": 2, "청렴": 2, "도덕": 1, "원칙": 1,
    "참신": 1, "젊은": 1, "변화": 1, "희망": 1, "가능성": 1,
    "당선": 1, "유력": 1, "적합": 2, "적임": 2,
}
NEGATIVE_WORDS = {
    "논란": 2, "비판": 2, "반발": 2, "갈등": 2, "위기": 2,
    "실패": 2, "문제": 1, "우려": 1, "부족": 1, "한계": 1,
    "의혹": 2, "수사": 2, "기소": 2, "재판": 1, "비리": 2,
    "사퇴": 1, "사직": 1, "탈당": 1, "분열": 2, "내홍": 2,
    "하락": 1, "추락": 2, "열세": 1, "고전": 1, "부진": 1,
    "거짓": 2, "허위": 2, "기만": 2, "무능": 2, "무책임": 2,
    "포퓰리즘": 2, "막말": 2, "독선": 2, "오만": 1,
    "낙선": 1, "탈락": 1, "부적합": 2,
}

# 2026 서울시장 선거 후보 (민주당 경선 + 국힘 현직)
CANDIDATE_NAMES = [
    "박주민", "오세훈",       # 핵심 양자 구도
    "우상호", "전현희", "정원오",  # 민주당 경선 후보
    "송영길", "김두관",        # 민주당 경선 후보
]

def load_env():
    """환경변수 검증"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("[ERROR] 네이버 API 키가 설정되지 않았습니다.")
        sys.exit(1)

def search_naver_news(keyword, display=100, start=1, sort="date"):
    """네이버 뉴스 API 검색"""
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": display, "start": start, "sort": sort}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Exception as e:
        print(f"[WARN] 네이버 검색 실패 ({keyword}): {e}")
        return []

def clean_html(text):
    """HTML 태그 제거"""
    return re.sub(r'<[^>]+>', '', text).replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')

def parse_date(date_str):
    """네이버 API 날짜 파싱"""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str).strftime('%Y-%m-%d')
    except:
        return datetime.now().strftime('%Y-%m-%d')

def extract_naver_article_id(link):
    """네이버 뉴스 기사 ID 추출 (댓글 수집용)"""
    if not link or 'naver.com' not in link:
        return None, None
    # n.news.naver.com/mnews/article/011/0004607007 또는 /article/011/0004607007
    match = re.search(r'article/(\d+)/(\d+)', link)
    if match:
        return match.group(1), match.group(2)
    # news.naver.com/main/read.naver?...oid=011&aid=0004607007
    parsed = urlparse(link)
    qs = parse_qs(parsed.query)
    oid = qs.get('oid', [None])[0]
    aid = qs.get('aid', [None])[0]
    if oid and aid:
        return oid, aid
    return None, None

def fetch_naver_comments(oid, aid, max_comments=30):
    """네이버 뉴스 댓글 수집"""
    if not oid or not aid:
        return []
    url = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"
    params = {
        "ticket": "news",
        "templateId": "default_politics",
        "pool": "cbox5",
        "lang": "ko",
        "country": "KR",
        "objectId": f"news{oid},{aid}",
        "pageSize": max_comments,
        "indexSize": 10,
        "page": 1,
        "sort": "FAVORITE",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"https://n.news.naver.com/article/{oid}/{aid}",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        text = resp.text
        # JSONP 파싱
        json_match = re.search(r'\((\{.*\})\)', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
            comments = data.get("result", {}).get("commentList", [])
            result = []
            for c in comments[:max_comments]:
                result.append({
                    "text": c.get("contents", ""),
                    "likes": c.get("sympathyCount", 0),
                    "dislikes": c.get("antipathyCount", 0),
                    "date": c.get("regTime", ""),
                })
            return result
    except Exception as e:
        print(f"[WARN] 댓글 수집 실패 ({oid}/{aid}): {e}")
    return []

def analyze_sentiment(text, target_candidate="박주민"):
    """감성분석 — 가중치 키워드 + 문맥 근접도"""
    pos_score = 0
    neg_score = 0
    text_lower = text.lower()

    for word, weight in POSITIVE_WORDS.items():
        count = text_lower.count(word)
        if count > 0:
            # 후보명 근접도 체크 (30자 이내)
            for match in re.finditer(re.escape(word), text_lower):
                start = max(0, match.start() - 30)
                end = min(len(text_lower), match.end() + 30)
                context = text_lower[start:end]
                if target_candidate in context:
                    pos_score += weight * 2  # 근접 시 가중치 2배
                else:
                    pos_score += weight

    for word, weight in NEGATIVE_WORDS.items():
        count = text_lower.count(word)
        if count > 0:
            for match in re.finditer(re.escape(word), text_lower):
                start = max(0, match.start() - 30)
                end = min(len(text_lower), match.end() + 30)
                context = text_lower[start:end]
                if target_candidate in context:
                    neg_score += weight * 2
                else:
                    neg_score += weight

    total = pos_score + neg_score
    if total == 0:
        return "중립", 0, 0
    pos_pct = round(pos_score / total * 100)
    neg_pct = round(neg_score / total * 100)

    if pos_score > neg_score * 1.3:
        return "긍정", pos_pct, neg_pct
    elif neg_score > pos_score * 1.3:
        return "부정", pos_pct, neg_pct
    else:
        return "중립", pos_pct, neg_pct

def analyze_comment_sentiment(comments):
    """댓글 목록의 전체 감성 분석"""
    if not comments:
        return {"total": 0, "positive": 0, "negative": 0, "neutral": 0, "pos_pct": 0}
    pos = neg = neu = 0
    for c in comments:
        sentiment, _, _ = analyze_sentiment(c.get("text", ""))
        if sentiment == "긍정":
            pos += 1
        elif sentiment == "부정":
            neg += 1
        else:
            neu += 1
    total = len(comments)
    return {
        "total": total,
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "pos_pct": round(pos / total * 100) if total > 0 else 0,
    }

def collect_all_news(target_date):
    """전체 뉴스 수집 + 중복 제거"""
    all_articles = {}
    for kw in ALL_KEYWORDS:
        items = search_naver_news(kw, display=100)
        for item in items:
            link = item.get("link", "")
            if link in all_articles:
                continue
            pub_date = parse_date(item.get("pubDate", ""))
            # 오늘/어제 기사만 수집
            if pub_date < (datetime.strptime(target_date, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d'):
                continue

            title = clean_html(item.get("title", ""))
            desc = clean_html(item.get("description", ""))
            full_text = title + " " + desc

            # 박주민 또는 서울시장 관련 기사만
            is_relevant = any(name in full_text for name in CANDIDATE_NAMES) or "서울시장" in full_text
            if not is_relevant:
                continue

            # 무관 기사 필터링 (선거와 무관한 기사 제거)
            IRRELEVANT_WORDS = [
                "벚꽃", "날씨", "기온", "꽃놀이", "미세먼지", "황사",
                "스포츠", "야구", "축구", "농구", "프로야구",
                "연예", "드라마", "영화", "아이돌", "콘서트",
                "맛집", "여행", "관광", "축제",
            ]
            if not any(name in full_text for name in CANDIDATE_NAMES):
                # 후보 이름이 없으면서 무관 키워드가 있으면 제거
                if any(iw in full_text for iw in IRRELEVANT_WORDS):
                    continue

            # 감성분석
            sentiment, pos_pct, neg_pct = analyze_sentiment(full_text)

            # 언급된 후보
            mentioned = [name for name in CANDIDATE_NAMES if name in full_text]

            # 네이버 뉴스 댓글 수집 — link(네이버 URL)에서 ID 추출, 실패 시 originallink
            oid, aid = extract_naver_article_id(link)
            if not oid:
                oid, aid = extract_naver_article_id(item.get("originallink", ""))
            comments = fetch_naver_comments(oid, aid, max_comments=20)
            comment_sentiment = analyze_comment_sentiment(comments)

            all_articles[link] = {
                "title": title,
                "description": desc,
                "link": link,
                "originallink": item.get("originallink", link),
                "pubDate": pub_date,
                "sentiment": sentiment,
                "pos_pct": pos_pct,
                "neg_pct": neg_pct,
                "candidates_mentioned": mentioned,
                "is_parkjoomin": "박주민" in full_text,
                "comments": {
                    "count": comment_sentiment["total"],
                    "positive": comment_sentiment["positive"],
                    "negative": comment_sentiment["negative"],
                    "neutral": comment_sentiment["neutral"],
                    "pos_pct": comment_sentiment["pos_pct"],
                    "top_comments": comments[:5],
                },
            }
        time.sleep(0.15)  # API rate limit

    articles = list(all_articles.values())
    articles.sort(key=lambda x: x.get("pubDate", ""), reverse=True)
    return articles

def compute_daily_stats(articles, target_date):
    """일일 통계 계산"""
    pj_articles = [a for a in articles if a.get("is_parkjoomin")]
    total = len(articles)
    pj_total = len(pj_articles)

    # 감성 비율
    sentiments = {"긍정": 0, "부정": 0, "중립": 0}
    for a in pj_articles:
        sentiments[a.get("sentiment", "중립")] += 1

    total_comments = sum(a["comments"]["count"] for a in pj_articles)
    pos_comments = sum(a["comments"]["positive"] for a in pj_articles)
    neg_comments = sum(a["comments"]["negative"] for a in pj_articles)
    neu_comments = sum(a["comments"]["neutral"] for a in pj_articles)

    # 경쟁자별 노출 횟수
    candidate_exposure = {}
    for name in CANDIDATE_NAMES:
        count = sum(1 for a in articles if name in a.get("candidates_mentioned", []))
        candidate_exposure[name] = count

    # 주요 키워드 추출
    keyword_freq = {}
    issue_words = ["교통", "주거", "청년", "재개발", "기후", "복지", "일자리", "경제",
                   "안전", "환경", "교육", "의료", "문화", "디지털", "소통", "개혁",
                   "경선", "여론조사", "토론", "공약", "비전", "리더십"]
    for a in pj_articles:
        text = a["title"] + " " + a["description"]
        for w in issue_words:
            if w in text:
                keyword_freq[w] = keyword_freq.get(w, 0) + 1

    top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:10]

    pos_pct = round(sentiments["긍정"] / pj_total * 100) if pj_total > 0 else 0
    neg_pct = round(sentiments["부정"] / pj_total * 100) if pj_total > 0 else 0
    neu_pct = 100 - pos_pct - neg_pct

    return {
        "date": target_date,
        "total_articles": total,
        "parkjoomin_articles": pj_total,
        "sentiment": {
            "positive": sentiments["긍정"],
            "negative": sentiments["부정"],
            "neutral": sentiments["중립"],
            "pos_pct": pos_pct,
            "neg_pct": neg_pct,
            "neu_pct": neu_pct,
        },
        "comments": {
            "total": total_comments,
            "positive": pos_comments,
            "negative": neg_comments,
            "neutral": neu_comments,
            "pos_pct": round(pos_comments / total_comments * 100) if total_comments > 0 else 0,
            "neg_pct": round(neg_comments / total_comments * 100) if total_comments > 0 else 0,
            "neu_pct": round(neu_comments / total_comments * 100) if total_comments > 0 else 0,
        },
        "candidate_exposure": candidate_exposure,
        "top_keywords": top_keywords,
        "top_articles": pj_articles[:10],
    }

def save_data(stats, articles, target_date):
    """데이터 저장"""
    data_dir = os.path.join(BASE_DIR, "data", "news_daily")
    os.makedirs(data_dir, exist_ok=True)

    output = {
        "meta": {
            "date": target_date,
            "collected_at": datetime.now().isoformat(),
            "total_articles": len(articles),
        },
        "stats": stats,
        "articles": articles,
    }

    filepath = os.path.join(data_dir, f"{target_date}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] 뉴스 데이터 저장: {filepath} ({len(articles)}건)")
    return filepath

def main():
    parser = argparse.ArgumentParser(description="박주민 뉴스 수집기")
    parser.add_argument("--date", default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()

    load_env()
    print(f"[START] 박주민 뉴스 수집 시작 — {args.date}")

    articles = collect_all_news(args.date)
    print(f"[INFO] 수집된 기사: {len(articles)}건")

    stats = compute_daily_stats(articles, args.date)
    print(f"[INFO] 박주민 관련: {stats['parkjoomin_articles']}건 "
          f"(긍정 {stats['sentiment']['pos_pct']}% / 부정 {stats['sentiment']['neg_pct']}%)")

    save_data(stats, articles, args.date)
    print("[DONE] 뉴스 수집 완료")

if __name__ == "__main__":
    main()
