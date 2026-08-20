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

# ====================== Keywords ======================
KEYWORDS = [
    "iran", "hormuz", "strait of hormuz", "tehran", "iran war", "iran conflict",
    "tanker", "vlcc", "suezmax", "aframax", "oil", "crude", "brent", "wti",
    "trump", "geopolit", "persian gulf", "bab al-mandeb", "houthi", "saudi",
    "uae", "iraq", "kuwait", "qatar", "cosco", "cmes", "shipping", "maritime",
    "ukmto", "attack", "warning"
]

# ====================== Feeds ======================
FEEDS = [
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Maritime Executive", "https://maritime-executive.com/articles.rss"),
    ("Splash247", "https://splash247.com/feed/"),
    ("UKMTO", "https://news.google.com/rss/search?q=UKMTO+(warning+OR+attack)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Reuters", "https://news.google.com/rss/search?q=site:reuters.com+(Iran+OR+Hormuz+OR+tanker+OR+oil)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("CNBC", "https://news.google.com/rss/search?q=site:cnbc.com+(Iran+OR+Hormuz+OR+oil)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Guardian", "https://news.google.com/rss/search?q=site:theguardian.com+(Iran+OR+Hormuz)+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("Iran International", "https://news.google.com/rss/search?q=site:iranintl.com+when:1d&hl=en-US&gl=US&ceid=US:en"),
    ("General", "https://news.google.com/rss/search?q=(Iran+OR+Hormuz+OR+%22Strait+of+Hormuz%22)+(war+OR+tanker+OR+oil+OR+Trump)+when:1d&hl=en-US&gl=US&ceid=US:en"),
]

def is_relevant(title, summary=""):
    text = (title + " " + summary).lower()
    return any(kw in text for kw in KEYWORDS)

def summarize_korean(title, summary):
    try:
        prompt = f"""다음 뉴스 제목과 요약을 한국어로 4~5줄 정도로 자연스럽고 간결하게 요약해줘.
해운·유조선·원유 시장·지정학적 영향이 있으면 반드시 포함해.
불필요한 인사말 없이 내용만 작성해.

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
                
                # UKMTO는 키워드 필터를 느슨하게
                if "UKMTO" in source:
                    if "ukmto" not in title.lower() and "warning" not in title.lower() and "attack" not in title.lower():
                        continue
                else:
                    if not is_relevant(title, summary):
                        continue

                seen.add(title_hash)
                item = {
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "summary": summary,
                    "published": published
                }

                if "UKMTO" in source:
                    ukmto_items.append(item)
                else:
                    normal_items.append(item)

        except Exception as e:
            print(f"Error fetching {source}: {e}")

    ukmto_items.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    normal_items.sort(key=lambda x: x["published"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return ukmto_items[:6], normal_items[:12]

def create_html(ukmto_items, normal_items):
    now = datetime.now().strftime("%d / %B / %Y")
    
    html = f"""
    <html>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.65; color: #333; max-width: 720px; margin: 0 auto; background: #f4f6f8;">
        
        <div style="background: white; padding: 22px 28px; border-bottom: 3px solid #c0392b; margin-bottom: 22px;">
            <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                    <td style="vertical-align: middle; width: 58%;">
                        <img src="https://raw.githubusercontent.com/bshhoo043-ai/iran-war-daily-brief/main/logo.png" 
                             alt="시그마해운" style="height: 50px; display: block;">
                    </td>
                    <td style="text-align: right; vertical-align: middle;">
                        <div style="font-size: 19px; font-weight: 700; color: #c0392b;">IRAN WAR STATUS</div>
                        <div style="font-size: 13px; color: #555; margin-top: 3px;">({now})</div>
                    </td>
                </tr>
            </table>
        </div>
    """

    # UKMTO Section
    html += """
        <div style="background: #fff5f5; border-left: 5px solid #c0392b; padding: 16px 20px; margin-bottom: 28px; border-radius: 0 8px 8px 0;">
            <h2 style="margin: 0 0 12px 0; font-size: 17px; color: #c0392b;">UKMTO / 선박 공격·경보 (최근 24시간)</h2>
    """
    
    if not ukmto_items:
        html += "<p style='margin:0; color:#666; font-size:14px;'>최근 24시간 내 특별한 UKMTO Warning/Attack 보고가 없습니다.</p>"
    else:
        for i, e in enumerate(ukmto_items, 1):
            pub = e["published"].strftime("%m-%d %H:%M UTC") if e["published"] else ""
            korean = summarize_korean(e["title"], e["summary"])
            html += f"""
            <div style="margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #f0d0d0;">
                <div style="font-size: 12px; color: #888;">{e['source']} | {pub}</div>
                <div style="font-weight: 600; font-size: 15px; margin: 4px 0 6px 0;">{i}. {e['title']}</div>
                <div style="font-size: 14px; color: #444; white-space: pre-line;">{korean}</div>
                <a href="{e['link']}" style="font-size: 13px; color: #0066cc;">원문 보기 →</a>
            </div>
            """
    html += "</div>"

    # Normal News
    html += "<h2 style='font-size: 17px; color: #1a5276; margin: 0 0 16px 0;'>이란 전쟁 · 유조선 · 원유 · 지정학 주요 뉴스</h2>"

    if not normal_items:
        html += "<p>관련 뉴스가 없습니다.</p>"
    else:
        for i, e in enumerate(normal_items, 1):
            pub = e["published"].strftime("%m-%d %H:%M UTC") if e["published"] else ""
            korean = summarize_korean(e["title"], e["summary"])
            html += f"""
            <div style="background: white; padding: 16px 20px; margin-bottom: 14px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.07);">
                <div style="font-size: 12px; color: #888; margin-bottom: 5px;">{e['source']} | {pub}</div>
                <h3 style="margin: 0 0 8px 0; font-size: 15.5px; color: #222;">{i}. {e['title']}</h3>
                <div style="font-size: 14px; color: #444; line-height: 1.7; white-space: pre-line;">{korean}</div>
                <div style="margin-top: 10px;">
                    <a href="{e['link']}" style="color: #0066cc; font-size: 13px; text-decoration: none;">원문 보기 →</a>
                </div>
            </div>
            """

    html += """
        <p style="font-size: 12px; color: #888; text-align: center; margin-top: 35px;">
            시그마해운(주) | Iran / Hormuz Daily Brief
        </p>
    </body>
    </html>
    """
    return html

def send_email(html_content):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Iran/Hormuz Brief] {datetime.now().strftime('%Y-%m-%d')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    print("Email sent successfully!")

if __name__ == "__main__":
    print("Collecting news (last 24h)...")
    ukmto_items, normal_items = get_entries()
    print(f"UKMTO: {len(ukmto_items)} | News: {len(normal_items)}")
    html = create_html(ukmto_items, normal_items)
    send_email(html)
