import os
import feedparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
import hashlib
from openai import OpenAI

# ====================== Secrets ======================
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====================== 키워드 ======================
KEYWORDS = [
    "iran", "hormuz", "strait of hormuz", "tehran", "iran war", "iran conflict",
    "tanker", "vlcc", "suezmax", "aframax", "oil", "crude", "brent", "wti",
    "trump", "geopolit", "persian gulf", "bab al-mandeb", "houthi", "saudi",
    "uae", "iraq", "kuwait", "qatar", "cosco", "cmes", "shipping", "maritime"
]

# ====================== 피드 ======================
FEEDS = [
    # 주요 직접 RSS
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Maritime Executive", "https://maritime-executive.com/articles.rss"),
    ("Splash247", "https://splash247.com/feed/"),
    
    # Google News 타겟팅 (요청 사이트 + UKMTO)
    ("UKMTO Warnings", "https://news.google.com/rss/search?q=UKMTO+(warning+OR+attack+OR+advisory)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Reuters (Iran/Hormuz)", "https://news.google.com/rss/search?q=site:reuters.com+(Iran+OR+Hormuz+OR+tanker+OR+oil)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("CNBC World", "https://news.google.com/rss/search?q=site:cnbc.com+(Iran+OR+Hormuz+OR+oil+OR+tanker)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("The Guardian", "https://news.google.com/rss/search?q=site:theguardian.com+(Iran+OR+Hormuz)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Iran International", "https://news.google.com/rss/search?q=site:iranintl.com+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("General Iran/Hormuz", "https://news.google.com/rss/search?q=(Iran+OR+Hormuz+OR+%22Strait+of+Hormuz%22)+(war+OR+tanker+OR+oil+OR+Trump)+when:1d&hl=en-US&gl=US&ceid=US:en"),
]

def is_relevant(title, summary=""):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in KEYWORDS)

def summarize_korean(title, summary):
    try:
        prompt = f"""다음 뉴스 제목과 요약을 한국어로 4~5줄 정도로 자연스럽고 간결하게 요약해줘.
해운·유조선·원유 시장·지정학적 영향이 있으면 반드시 포함해.
불필요한 인사말이나 "요약하면" 같은 표현 없이 내용만 작성해.

제목: {title}
내용: {summary}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=320
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Summary error: {e}")
        return "요약 생성 중 오류가 발생했습니다."

def get_entries(hours=26):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    seen = set()
    ukmto_items = []
    normal_items = []

    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                title_hash = hashlib.md5(title.lower().encode()).hexdigest()
                if title_hash in seen:
                    continue

                published = None
                if hasattr(entry, "published"):
                    try:
                        published = date_parser.parse(entry.published)
                        if published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)
                    except:
                        published = None

                if published and published < cutoff:
                    continue

                summary = entry.get("summary", "")[:450]
                if not is_relevant(title, summary) and "UKMTO" not in source:
                    continue

                seen.add(title_hash)
                item = {
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": summary,
                    "published": published
                }

                if "UKMTO" in source or "ukmto" in title.lower() or "warning" in title.lower() and "attack" in title.lower():
                    ukmto_items.append(item)
                else:
                    normal_items.append(item)

        except Exception as e:
            print(f"Error fetching {source}: {e}")

    # 최신순 정렬
    ukmto_items.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    normal_items.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return ukmto_items[:8], normal_items[:12]

def create_html(ukmto_items, normal_items):
    now = datetime.now().strftime("%d / %B / %Y")
    
    html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.65; color: #333; max-width: 720px; margin: 0 auto; background: #f4f6f8;">
        
        <!-- 헤더 -->
        <div style="background: white; padding: 22px 28px; border-bottom: 3px solid #c0392b; margin-bottom: 22px;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td style="vertical-align: middle; width: 58%;">
                        <img src="https://raw.githubusercontent.com/bshhoo043-ai/iran-war-daily-brief/main/logo.png" 
                             alt="시그마해운" style="height: 50px; display: block;">
                    </td>
                    <td style="text-align: right; vertical-align: middle;">
                        <div style="font-size: 19px; font-weight: 700; color: #c0392b;">IRAN WAR STATUS
