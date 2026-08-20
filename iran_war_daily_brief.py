import os
import feedparser
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from dateutil import parser as date_parser
import hashlib

# ====================== 설정 (Secrets에서 가져옴) ======================
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

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

                summary = entry.get("summary", "")[:300]
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
    return results[:25]

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
        html += "<p>No relevant news found in the last 24-30 hours.</p>"
    else:
        for i, e in enumerate(entries, 1):
            pub = e["published"].strftime("%m-%d %H:%M UTC") if e["published"] else "N/A"
            html += f"""
            <div style="margin-bottom: 22px;">
                <h3 style="margin-bottom: 4px; font-size: 17px;">{i}. {e['title']}</h3>
                <p style="margin: 0; color: #666; font-size: 13px;">{e['source']} | {pub}</p>
                <p style="margin: 8px 0; font-size: 14px;">{e['summary'][:280]}...</p>
                <a href="{e['link']}" style="color: #0066cc; font-size: 13px;">Read full article →</a>
            </div>
            <hr style="border: none; border-top: 1px solid #eee;">
            """

    html += """
        <br>
        <p style="font-size: 12px; color: #888;">
            Automated brief focused on Iran conflict, Strait of Hormuz, and related oil/shipping developments.
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
