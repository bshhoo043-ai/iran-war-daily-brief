import os
import feedparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
import hashlib
from openai import OpenAI   # 

# ====================== 설정 ======================
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)   # 

KEYWORDS = [
    "iran", "hormuz", "strait of hormuz", "tehran",
    "iran war", "iran conflict", "persian gulf", "bab al-mandeb",
    "strait of hormuz", "cosco", "cmes"
]

FEEDS = [
    ("OilPrice", "https://oilprice.com/rss/main"),
    ("Google News - Iran/Hormuz", "https://news.google.com/rss/search?q=(Iran+OR+Hormuz+OR+%22Strait+of+Hormuz%22)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News - Reuters", "https://news.google.com/rss/search?q=site:reuters.com+(Iran+OR+Hormuz)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Google News - Bloomberg", "https://news.google.com/rss/search?q=site:bloomberg.com+(Iran+OR+Hormuz)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Mehr News (Iran)", "https://en.mehrnews.com/rss"),
]

def is_relevant(title, summary=""):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in KEYWORDS)

def summarize_korean(title, summary):
    try:
        prompt = f"""다음 뉴스 제목과 요약을 한국어로 4~5줄 정도로 자연스럽게 요약해줘.
해운/원유 시장 관점에서 중요한 내용이 있으면 함께 언급해.
불필요한 인사말이나 설명 없이 요약 내용만 작성해.

제목: {title}
내용: {summary}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Summary error: {e}")
        return summary[:200] + "..."

def get_recent_entries(hours=30):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    seen = set()
    results = []

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

                summary = entry.get("summary", "")[:400]
                if not is_relevant(title, summary):
                    continue

                seen.add(title_hash)
                results.append({
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": summary,
                    "published": published
                })
        except Exception as e:
            print(f"Error fetching {source}: {e}")

    results.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return results[:12]  # 요약 때문에 개수를 조금 줄임

def create_html(entries):
    now = datetime.now().strftime("%d / %B / %Y")
    
    html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 720px; margin: 0 auto; background: #f8f9fa;">
        
        <!-- 헤더 -->
        <div style="background: white; padding: 20px 30px; border-bottom: 3px solid #c0392b; margin-bottom: 25px;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td style="vertical-align: middle; width: 60%;">
                        <img src="https://raw.githubusercontent.com/bshhoo043-ai/iran-war-daily-brief/main/logo.png" 
                             alt="시그마해운" 
                             style="height: 52px; display: block;">
                    </td>
                    <td style="text-align: right; vertical-align: middle;">
                        <div style="font-size: 20px; font-weight: 700; color: #c0392b;">
                            IRAN WAR STATUS
                        </div>
                        <div style="font-size: 14px; color: #555; margin-top: 4px;">
                            ({now})
                        </div>
                    </td>
                </tr>
            </table>
        </div>
    """

    if not entries:
        html += "<p>최근 관련 뉴스가 없습니다.</p>"
    else:
        for i, e in enumerate(entries, 1):
            pub = e["published"].strftime("%m-%d %H:%M UTC") if e["published"] else "N/A"
            korean_summary = summarize_korean(e["title"], e["summary"])
            
            html += f"""
            <div style="background: white; padding: 18px 22px; margin-bottom: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                <div style="font-size: 12px; color: #888; margin-bottom: 6px;">
                    {e['source']} | {pub}
                </div>
                <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #222;">
                    {i}. {e['title']}
                </h3>
                <div style="font-size: 14px; color: #444; line-height: 1.7; white-space: pre-line;">
                    {korean_summary}
                </div>
                <div style="margin-top: 12px;">
                    <a href="{e['link']}" style="color: #0066cc; font-size: 13px; text-decoration: none;">원문 보기 →</a>
                </div>
            </div>
            """

    html += """
        <br>
        <p style="font-size: 12px; color: #888; text-align: center;">
            시그마해운(주) | Iran / Hormuz Automated Daily Brief
        </p>
    </body>
    </html>
    """
    return html

def send_email(html_content):
    if not all([SENDER_EMAIL, SENDER_APP_PASSWORD, RECEIVER_EMAIL]):
        raise ValueError("Missing email secrets")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Iran/Hormuz Brief] {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

    print("✅ Email sent successfully!")

if __name__ == "__main__":
    print("Collecting news...")
    entries = get_recent_entries()
    print(f"Found {len(entries)} relevant articles")
    html = create_html(entries)
    send_email(html)
