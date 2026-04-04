#!/usr/bin/env python3
"""박주민 서울시장 후보 SNS 전 채널 수집기"""

import os, sys, json, re, time, argparse
from datetime import datetime, timedelta
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

YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ──────────────────── 박주민 SNS 계정 ────────────────────
# 참고: 실제 계정 정보는 수집 시 확인 후 업데이트 필요
ACCOUNTS = {
    "youtube": {
        "channel_id": "",  # 실제 채널 ID 확인 후 입력
        "handle": "박주민",  # 검색용
        "search_keywords": ["박주민", "박주민 서울시장"],
    },
    "facebook": {
        "page_url": "",  # 실제 페이지 URL 확인 후 입력
        "search_keywords": ["박주민"],
    },
    "instagram": {
        "username": "",  # 실제 계정 확인 후 입력
    },
    "twitter": {
        "username": "",  # 실제 X 계정 확인 후 입력
        "search_keywords": ["박주민", "박주민 서울시장"],
    },
    "blog": {
        "url": "",  # 네이버 블로그 URL
    },
    "tiktok": {
        "username": "",  # 틱톡 계정
    },
}

# ──────────────────── 유튜브 수집 ────────────────────
def collect_youtube():
    """유튜브 — 박주민 관련 영상 + 댓글 수집"""
    result = {
        "platform": "youtube",
        "status": "수집완료",
        "data": {"videos": [], "total_views": 0, "total_comments": 0},
    }

    # 유튜브 검색 API로 관련 영상 수집
    if YOUTUBE_API_KEY:
        for keyword in ["박주민 서울시장", "박주민"]:
            try:
                url = "https://www.googleapis.com/youtube/v3/search"
                params = {
                    "part": "snippet",
                    "q": keyword,
                    "type": "video",
                    "order": "date",
                    "maxResults": 10,
                    "publishedAfter": (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%dT00:00:00Z'),
                    "key": YOUTUBE_API_KEY,
                }
                resp = requests.get(url, params=params, timeout=10)
                data = resp.json()
                for item in data.get("items", []):
                    vid = item["id"]["videoId"]
                    snippet = item["snippet"]
                    # 영상 통계
                    stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={vid}&key={YOUTUBE_API_KEY}"
                    stats_resp = requests.get(stats_url, timeout=10)
                    stats = stats_resp.json().get("items", [{}])[0].get("statistics", {})

                    # 댓글 수집
                    comments = collect_youtube_comments(vid)

                    result["data"]["videos"].append({
                        "title": snippet.get("title", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "published": snippet.get("publishedAt", ""),
                        "url": f"https://youtube.com/watch?v={vid}",
                        "views": int(stats.get("viewCount", 0)),
                        "likes": int(stats.get("likeCount", 0)),
                        "comment_count": int(stats.get("commentCount", 0)),
                        "top_comments": comments[:5],
                    })
                    result["data"]["total_views"] += int(stats.get("viewCount", 0))
                    result["data"]["total_comments"] += len(comments)
                    time.sleep(0.2)
            except Exception as e:
                print(f"[WARN] 유튜브 검색 실패: {e}")
    else:
        result["status"] = "API키_없음"

    return result

def collect_youtube_comments(video_id, max_results=20):
    """유튜브 영상 댓글 수집"""
    if not YOUTUBE_API_KEY:
        return []
    try:
        url = "https://www.googleapis.com/youtube/v3/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": max_results,
            "order": "relevance",
            "key": YOUTUBE_API_KEY,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        comments = []
        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "text": snippet.get("textDisplay", ""),
                "likes": snippet.get("likeCount", 0),
                "date": snippet.get("publishedAt", ""),
            })
        return comments
    except:
        return []

# ──────────────────── X(트위터) / SNS 언급 수집 ────────────────────
def collect_twitter():
    """X(트위터) + SNS 언급 — 네이버 검색 API 활용"""
    result = {
        "platform": "twitter_sns",
        "status": "수집완료",
        "data": {"mentions": [], "total": 0},
    }

    naver_id = os.environ.get('NAVER_CLIENT_ID', '')
    naver_secret = os.environ.get('NAVER_CLIENT_SECRET', '')
    if not naver_id:
        result["status"] = "API키_없음"
        return result

    headers = {
        "X-Naver-Client-Id": naver_id,
        "X-Naver-Client-Secret": naver_secret,
    }

    # 네이버 웹검색으로 X/트위터 + SNS 언급 수집
    search_queries = [
        "박주민 site:x.com",
        "박주민 site:twitter.com",
        "박주민 서울시장 트위터",
        "박주민 서울시장 SNS 반응",
    ]

    seen_links = set()
    for query in search_queries:
        try:
            url = "https://openapi.naver.com/v1/search/webkr.json"
            params = {"query": query, "display": 10, "sort": "date"}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            data = resp.json()
            for item in data.get("items", []):
                link = item.get("link", "")
                if link in seen_links:
                    continue
                seen_links.add(link)
                title = re.sub(r'<[^>]+>', '', item.get("title", ""))
                desc = re.sub(r'<[^>]+>', '', item.get("description", ""))
                result["data"]["mentions"].append({
                    "text": f"{title} — {desc[:100]}",
                    "link": link,
                    "source": "x.com" if "x.com" in link or "twitter.com" in link else "web",
                })
            time.sleep(0.15)
        except Exception as e:
            print(f"[WARN] X/SNS 검색 실패 ({query}): {e}")

    result["data"]["total"] = len(result["data"]["mentions"])
    result["data"]["x_count"] = sum(1 for m in result["data"]["mentions"] if m.get("source") == "x.com")
    result["data"]["web_count"] = sum(1 for m in result["data"]["mentions"] if m.get("source") == "web")

    if result["data"]["total"] == 0:
        result["status"] = "결과없음"

    return result

# ──────────────────── 커뮤니티 수집 ────────────────────
def collect_community():
    """주요 커뮤니티 박주민 언급 수집"""
    result = {
        "platform": "community",
        "status": "수집완료",
        "data": {"posts": [], "total": 0, "sources": []},
    }

    # 네이버 카페/블로그 검색
    naver_id = os.environ.get('NAVER_CLIENT_ID', '')
    naver_secret = os.environ.get('NAVER_CLIENT_SECRET', '')

    if naver_id and naver_secret:
        for search_type in ["cafearticle", "blog"]:
            try:
                url = f"https://openapi.naver.com/v1/search/{search_type}.json"
                headers = {
                    "X-Naver-Client-Id": naver_id,
                    "X-Naver-Client-Secret": naver_secret,
                }
                params = {"query": "박주민 서울시장", "display": 20, "sort": "date"}
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                data = resp.json()
                source_name = "네이버카페" if search_type == "cafearticle" else "네이버블로그"
                for item in data.get("items", []):
                    title = re.sub(r'<[^>]+>', '', item.get("title", ""))
                    desc = re.sub(r'<[^>]+>', '', item.get("description", ""))
                    result["data"]["posts"].append({
                        "title": title,
                        "description": desc[:100],
                        "source": source_name,
                        "link": item.get("link", ""),
                        "date": item.get("postdate", ""),
                    })
                result["data"]["sources"].append(source_name)
                time.sleep(0.15)
            except Exception as e:
                print(f"[WARN] {search_type} 검색 실패: {e}")

    result["data"]["total"] = len(result["data"]["posts"])
    return result

# ──────────────────── 네이버 실시간 반응 ────────────────────
def collect_naver_reactions():
    """네이버 뉴스 댓글 트렌드 (별도 수집)"""
    result = {
        "platform": "naver_comments",
        "status": "수집완료",
        "data": {"trending_comments": [], "total_reactions": 0},
    }

    naver_id = os.environ.get('NAVER_CLIENT_ID', '')
    naver_secret = os.environ.get('NAVER_CLIENT_SECRET', '')
    if not naver_id:
        result["status"] = "API키_없음"
        return result

    # 최신 박주민 뉴스에서 인기 댓글 추출
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": naver_id,
        "X-Naver-Client-Secret": naver_secret,
    }
    params = {"query": "박주민", "display": 5, "sort": "date"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        items = resp.json().get("items", [])
        for item in items:
            link = item.get("originallink", item.get("link", ""))
            # 네이버 뉴스 링크에서 댓글 추출
            match = re.search(r'article/(\d+)/(\d+)', link)
            if match:
                from collect_news import fetch_naver_comments, analyze_comment_sentiment
                oid, aid = match.groups()
                comments = fetch_naver_comments(oid, aid, 10)
                if comments:
                    sentiment = analyze_comment_sentiment(comments)
                    result["data"]["trending_comments"].append({
                        "article_title": re.sub(r'<[^>]+>', '', item.get("title", "")),
                        "comment_count": sentiment["total"],
                        "pos_pct": sentiment["pos_pct"],
                        "top_comment": comments[0]["text"][:100] if comments else "",
                    })
                    result["data"]["total_reactions"] += sentiment["total"]
    except Exception as e:
        print(f"[WARN] 네이버 반응 수집 실패: {e}")

    return result

# ──────────────────── 종합 수집 ────────────────────
def collect_all(target_date):
    """전 채널 수집"""
    print("[1/4] 유튜브 수집...")
    youtube = collect_youtube()
    print(f"  → 영상 {len(youtube['data']['videos'])}건")

    print("[2/4] X(트위터) 수집...")
    twitter = collect_twitter()
    print(f"  → 멘션 {twitter['data']['total']}건")

    print("[3/4] 커뮤니티 수집...")
    community = collect_community()
    print(f"  → 게시글 {community['data']['total']}건")

    print("[4/4] 네이버 반응 수집...")
    naver = collect_naver_reactions()
    print(f"  → 댓글 {naver['data']['total_reactions']}건")

    return {
        "youtube": youtube,
        "twitter": twitter,
        "community": community,
        "naver_comments": naver,
    }

def save_data(social_data, target_date):
    """데이터 저장"""
    data_dir = os.path.join(BASE_DIR, "data", "social_daily")
    os.makedirs(data_dir, exist_ok=True)

    output = {
        "meta": {
            "date": target_date,
            "collected_at": datetime.now().isoformat(),
        },
        "channels": social_data,
    }

    filepath = os.path.join(data_dir, f"{target_date}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] SNS 데이터 저장: {filepath}")
    return filepath

def main():
    parser = argparse.ArgumentParser(description="박주민 SNS 수집기")
    parser.add_argument("--date", default=datetime.now().strftime('%Y-%m-%d'))
    args = parser.parse_args()

    print(f"[START] 박주민 SNS 수집 시작 — {args.date}")
    social_data = collect_all(args.date)
    save_data(social_data, args.date)
    print("[DONE] SNS 수집 완료")

if __name__ == "__main__":
    main()
