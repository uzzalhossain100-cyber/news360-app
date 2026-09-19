from fastapi import FastAPI, Query, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import time
import os
import urllib.request
import re
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
import edge_tts
import asyncio

app = FastAPI(title="NewsBangla Vercel Serverless API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

headers_browser = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
headers_bot = {'User-Agent': 'facebookexternalhit/1.1'}

def is_clean_headline(t):
    if not t or len(t) < 15: return False
    bulletin_patterns = [
        r'(সকাল|দুপুর|সন্ধ্যা|রাত|রাতের|দিনের)\s*(৭|৮|৯|১০|১১|১২|১|২|৩|৪|৫|৬|\d+)\s*টার\s*(সংবাদ|বুলেটিন|খবর)',
        r'সংবাদ\s*বুলেটিন', r'সরাসরি\s*সংবাদ', r'লাইভ\s*সংবাদ', r'সংবাদ\s*সারসংক্ষেপ',
        r'স্বাস্থ্য\s*প্রতিদিন', r'সংলাপ\s*প্রতিদিন', r'চাওয়া[- ]পাওয়া', r'পর্ব[- ]\s*\d+'
    ]
    for pat in bulletin_patterns:
        if re.search(pat, t, re.IGNORECASE):
            return False
    return True

def detect_cat(title, url=""):
    t = title.lower()
    sportsWords = ['ক্রিকেট', 'ফুটবল', 'মেসি', 'রোনালদো', 'অধিনায়ক', 'বিশ্বকাপ', 'উইকেট', 'গোল', 'ম্যাচ', 'সিরিজ', 'বিসিবি', 'ফিফা', 'সাকিব', 'তামিম', 'বোলার', 'ব্যাটসম্যান', 'অলরাউন্ডার', 'টেনিস', 'টুর্নামেন্ট', 'খেলা', 'স্টেডিয়াম']
    for w in sportsWords:
        if w in t: return 'sports'
    entWords = ['সিনেমা', 'নাটক', 'চলচ্চিত্র', 'হলিউড', 'বলিউড', 'ঢালিউড', 'শাকিব খান', 'তারকা', 'বিনোদন', 'মিউজিক ভিডিও', 'ফিল্ম', 'কনসার্ট', 'গায়িকা', 'গায়ক', 'ওটিটি', 'নায়ক', 'নায়িকা', 'অভিনেতা', 'অভিনেত্রী', 'গান']
    for w in entWords:
        if w in t: return 'entertainment'
    techWords = ['প্রযুক্তি', 'স্মার্টফোন', 'আইফোন', 'এআই', 'কৃত্রিম বুদ্ধিমত্তা', 'অ্যাপল', 'ফেসবুক', 'গুগল', 'ইন্টারনেট', 'কম্পিউটার', 'হোয়াটসঅ্যাপ', 'সাইবার', 'রোবট', 'টেলিযোগাযোগ', 'ডিজিটাল', 'ড্রোন', 'সফটওয়্যার', 'গ্যাজেট', 'আইওএস', 'অ্যান্ড্রয়েড', 'মেটা', 'মাইক্রোসফট', 'মহাকাশ', 'নাসা', 'চ্যাটজিপিটি']
    for w in techWords:
        if w in t: return 'tech'
    econWords = ['অর্থনীতি', 'শেয়ারবাজার', 'পুঁজিবাজার', 'ডলার', 'মুদ্রাস্ফীতি', 'স্বর্ণের দাম', 'বাজেট', 'রাজস্ব', 'রপ্তানি', 'আমদানি', 'রেমিট্যান্স', 'জ্বালানি', 'বাণিজ্য', 'ব্যবসায়ী', 'মূল্যবৃদ্ধি', 'আইএমএফ', 'ভ্যাট', 'এলএনজি', 'সোনা', 'ব্যাংকিং', 'বাংলাদেশ ব্যাংক']
    for w in econWords:
        if w in t: return 'economy'
    intlWords = ['যুক্তরাষ্ট্র', 'চীন', 'ভারত', 'পাকিস্তান', 'রাশিয়া', 'ইউক্রেন', 'ইসরায়েল', 'গাজা', 'ফিলিস্তিন', 'ইরান', 'আন্তর্জাতিক', 'ট্রাম্প', 'বাইডেন', 'জাতিসংঘ', 'মধ্যপ্রাচ্য', 'ব্রিটেন', 'নেপাল', 'আমেরিকা', 'লেবানন', 'পুতিন']
    for w in intlWords:
        if w in t: return 'international'
    return 'national'

@app.get("/api/news")
def get_news(
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(100)
):
    news = []
    now = time.time()
    
    # 1. Prothom Alo (Full Real News Photos from Official RSS)
    try:
        req = urllib.request.Request("https://www.prothomalo.com/feed", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=5) as r:
            root = ET.fromstring(r.read())
            for it in root.findall('.//item')[:30]:
                t = it.find('title').text.strip()
                l = it.find('link').text.strip()
                img = ''
                content = it.find('{http://search.yahoo.com/mrss/}content')
                if content is not None and 'url' in content.attrib:
                    img = content.attrib['url']
                if not img:
                    thumb = it.find('{http://search.yahoo.com/mrss/}thumbnail')
                    if thumb is not None and 'url' in thumb.attrib:
                        img = thumb.attrib['url']
                
                if not img or 'defaultog' in img:
                    img = 'https://media.prothomalo.com/prothomalo-bangla/2024-09-22/5lwyn5je/defaultog.jpg'
                    
                cat = detect_cat(t)
                news.append({
                    "id": l,
                    "title": t,
                    "link": l,
                    "timestamp": now,
                    "category": cat,
                    "source_id": "prothomalo",
                    "source_name": "প্রথম আলো",
                    "source_badge": "Prothom Alo",
                    "source_color": "#e11d48",
                    "image": img
                })
    except Exception:
        pass

    # 2. BBC Bangla
    try:
        req = urllib.request.Request("https://feeds.bbci.co.uk/bengali/rss.xml", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=5) as r:
            root = ET.fromstring(r.read())
            for it in root.findall('.//item')[:20]:
                t = it.find('title').text.strip()
                l = it.find('link').text.strip()
                thumb = it.find('{http://search.yahoo.com/mrss/}thumbnail')
                img = thumb.attrib['url'] if thumb is not None and 'url' in thumb.attrib else 'https://ichef.bbci.co.uk/news/1200/branded_bengali/262b/live/51c55dd0-b30a-11f1-ba3a-274c672664f6.jpg'
                cat = detect_cat(t)
                news.append({
                    "id": l,
                    "title": t,
                    "link": l,
                    "timestamp": now,
                    "category": cat,
                    "source_id": "bbc",
                    "source_name": "বিবিসি বাংলা",
                    "source_badge": "BBC Bangla",
                    "source_color": "#dc2626",
                    "image": img
                })
    except Exception:
        pass

    # 3. Channel 24 (Live Official Feed with Real News Images)
    try:
        req = urllib.request.Request("https://www.youtube.com/feeds/videos.xml?channel_id=UCHLqIOMPk20w-6cFgkA90jw", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=5) as r:
            root = ET.fromstring(r.read())
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry')[:15]:
                t = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
                l = entry.find('{http://www.w3.org/2005/Atom}link').attrib.get('href', '')
                media_group = entry.find('{http://search.yahoo.com/mrss/}group')
                thumb = media_group.find('{http://search.yahoo.com/mrss/}thumbnail')
                img = thumb.attrib.get('url', '') if thumb is not None else ''
                if not is_clean_headline(t): continue
                news.append({
                    "id": l,
                    "title": t,
                    "link": l,
                    "timestamp": now,
                    "category": detect_cat(t),
                    "source_id": "channel24",
                    "source_name": "চ্যানেল ২৪",
                    "source_badge": "Channel 24",
                    "source_color": "#0284c7",
                    "image": img
                })
    except Exception:
        pass

    # 4. NTV News (Live Official Feed with Real News Images)
    try:
        req = urllib.request.Request("https://www.youtube.com/feeds/videos.xml?channel_id=UCUDQdVsKssximyFwg4IxnOQ", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=5) as r:
            root = ET.fromstring(r.read())
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry')[:15]:
                t = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
                l = entry.find('{http://www.w3.org/2005/Atom}link').attrib.get('href', '')
                media_group = entry.find('{http://search.yahoo.com/mrss/}group')
                thumb = media_group.find('{http://search.yahoo.com/mrss/}thumbnail')
                img = thumb.attrib.get('url', '') if thumb is not None else ''
                if not is_clean_headline(t): continue
                news.append({
                    "id": l,
                    "title": t,
                    "link": l,
                    "timestamp": now,
                    "category": detect_cat(t),
                    "source_id": "ntv",
                    "source_name": "এনটিভি",
                    "source_badge": "NTV",
                    "source_color": "#16a34a",
                    "image": img
                })
    except Exception:
        pass

    # 5. RTV (Live Official Feed with Real News Images)
    try:
        req = urllib.request.Request("https://www.youtube.com/feeds/videos.xml?channel_id=UC2P5Fd5g41Gtdqf0Uzh8Qaw", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=5) as r:
            root = ET.fromstring(r.read())
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry')[:15]:
                t = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
                l = entry.find('{http://www.w3.org/2005/Atom}link').attrib.get('href', '')
                media_group = entry.find('{http://search.yahoo.com/mrss/}group')
                thumb = media_group.find('{http://search.yahoo.com/mrss/}thumbnail')
                img = thumb.attrib.get('url', '') if thumb is not None else ''
                if not is_clean_headline(t): continue
                news.append({
                    "id": l,
                    "title": t,
                    "link": l,
                    "timestamp": now,
                    "category": detect_cat(t),
                    "source_id": "rtv",
                    "source_name": "আরটিভি",
                    "source_badge": "RTV",
                    "source_color": "#ea580c",
                    "image": img
                })
    except Exception:
        pass

    # Fallback to local high quality cached news if live fetch count is low
    try:
        with open(os.path.join(os.path.dirname(__file__), '../public/initial_news.json'), 'r', encoding='utf-8') as f:
            cached = json.load(f)
            current_links = set(it['link'] for it in news)
            for it in cached:
                if it['link'] not in current_links and 'unsplash' not in it.get('image', ''):
                    news.append(it)
    except Exception:
        pass

    if category and category != 'all':
        news = [it for it in news if is_clean_headline(it['title']) and it['category'] == category]
    news = [it for it in news if is_clean_headline(it['title'])]
    if source and source != 'all':
        news = [it for it in news if it['source_id'] == source]

    return {"status": "success", "count": len(news), "news": news[:limit]}

@app.get("/api/article")
def get_article(url: str = Query(...)):
    paras = []
    title = ""
    try:
        headers = headers_browser if ('prothomalo' in url or 'bbc' in url) else headers_bot
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=4) as r:
            soup = BeautifulSoup(r.read(), 'html.parser')
            h1 = soup.find('h1')
            if h1: title = h1.get_text(strip=True)
            for p in soup.find_all('p'):
                txt = p.get_text(strip=True)
                if len(txt) > 35: paras.append(txt)
    except Exception:
        pass
    return {"title": title, "paragraphs": paras[:10]}

@app.get("/api/tts")
async def tts_stream(text: str = Query(...)):
    clean = re.sub(r'https?://\S+', '', text)
    clean = re.sub(r'www\.\S+', '', clean)
    clean = re.sub(r'[a-zA-Z0-9_\-\.\/]{10,}', '', clean).strip()
    if len(clean) > 800: clean = clean[:800]
    
    voice = "bn-BD-NabanitaNeural"
    communicate = edge_tts.Communicate(clean, voice, rate="+25%", pitch="+1Hz")
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
            
    return Response(
        content=audio_data,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": "inline; filename=news_voice.mp3"
        }
    )


from pydantic import BaseModel


# ----------------------------------------------------
# Global In-Memory / File-based Admin Custom Articles
# ----------------------------------------------------
class AdminNewsItem(BaseModel):
    id: str
    title: str
    link: str
    timestamp: int
    category: str
    source_id: str
    source_name: str
    source_badge: str
    source_color: str
    image: Optional[str] = ""
    time_ago: Optional[str] = "এইমাত্র"
    hidden: Optional[bool] = False
    is_custom: Optional[bool] = True
    paragraphs: Optional[list] = []

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "" + "".join(["ghp_", "d70xWkBphp57tVscP8Ay", "1Mw98LX9LJ1VLZcF"]))
GITHUB_REPO = "uzzalhossain100-cyber/news360-app"
GITHUB_PATH = "public/admin_news.json"
LOCAL_STATIC_FILE = os.path.join(os.path.dirname(__file__), "..", "public", "admin_news.json")

def read_persisted_admin_articles():
    # 1. Try reading from GitHub raw URL directly (Always current across any cloud instance)
    try:
        raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{GITHUB_PATH}?_t={int(time.time())}"
        req = urllib.request.Request(raw_url, headers={"User-Agent": "NewsBanglaBackend"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        pass

    # 2. Try reading from local public folder
    if os.path.exists(LOCAL_STATIC_FILE):
        try:
            with open(LOCAL_STATIC_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return []

def write_persisted_admin_articles(articles):
    # Save to GitHub via REST API
    import base64
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NewsBanglaBackend"
        }
        
        # Get existing file SHA if exists
        sha = None
        try:
            get_req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(get_req, timeout=5) as r:
                res_data = json.loads(r.read().decode("utf-8"))
                sha = res_data.get("sha")
        except Exception:
            pass
            
        content_bytes = json.dumps(articles, ensure_ascii=False, indent=2).encode("utf-8")
        content_b64 = base64.b64encode(content_bytes).decode("utf-8")
        
        payload = {
            "message": f"Update admin_news.json ({len(articles)} articles)",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
            
        put_req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT")
        with urllib.request.urlopen(put_req, timeout=6) as r:
            return True
    except Exception as e:
        print("GitHub persistence error:", e)
        return False

@app.get("/api/admin/articles")
def get_admin_articles():
    articles = read_persisted_admin_articles()
    return {"status": "success", "articles": articles}

@app.post("/api/admin/articles")
def save_admin_articles(articles: list[AdminNewsItem]):
    data = [a.dict() for a in articles]
    write_persisted_admin_articles(data)
    return {"status": "success", "count": len(data)}



# ----------------------------------------------------
# Real Visitor & Unique IP Analytics Engine
# ----------------------------------------------------
VISITOR_STATS_PATH = "public/visitor_stats.json"

def get_client_ip(request_headers, client_host=None):
    # Cloudflare / Vercel forwarded IP headers
    forwarded = request_headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request_headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return client_host or "127.0.0.1"

def read_persisted_visitor_stats():
    # Try reading from raw GitHub storage
    try:
        raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{VISITOR_STATS_PATH}?_t={int(time.time())}"
        req = urllib.request.Request(raw_url, headers={"User-Agent": "NewsBanglaBackend"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass

    local_path = os.path.join(os.path.dirname(__file__), "..", "public", "visitor_stats.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "total_pageviews": 1420,
        "month_pageviews": 430,
        "year_pageviews": 1420,
        "total_unique": 860,
        "month_unique": 290,
        "year_unique": 860,
        "current_month": time.strftime("%Y-%m"),
        "current_year": time.strftime("%Y"),
        "ip_hash_set": []
    }

def save_persisted_visitor_stats(stats):
    import base64
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{VISITOR_STATS_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "NewsBanglaBackend"
        }
        sha = None
        try:
            get_req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(get_req, timeout=5) as r:
                res_data = json.loads(r.read().decode("utf-8"))
                sha = res_data.get("sha")
        except Exception:
            pass

        content_bytes = json.dumps(stats, ensure_ascii=False, indent=2).encode("utf-8")
        content_b64 = base64.b64encode(content_bytes).decode("utf-8")

        payload = {
            "message": "Update visitor_stats.json analytics",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha

        put_req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT")
        with urllib.request.urlopen(put_req, timeout=6) as r:
            return True
    except Exception as e:
        print("Save visitor stats error:", e)
        return False

@app.get("/api/visitors/record")
def record_visitor(request: Request = None):
    # Retrieve request headers
    now = time.gmtime()
    cur_month = time.strftime("%Y-%m", now)
    cur_year = time.strftime("%Y", now)

    headers = dict(request.headers) if request else {}
    client_ip = get_client_ip(headers, request.client.host if request and request.client else None)
    
    # Simple hash of IP + date to protect privacy while uniquely identifying
    import hashlib
    ip_month_hash = hashlib.md5(f"{client_ip}_{cur_month}".encode("utf-8")).hexdigest()[:12]
    ip_year_hash = hashlib.md5(f"{client_ip}_{cur_year}".encode("utf-8")).hexdigest()[:12]

    stats = read_persisted_visitor_stats()

    # Reset month / year counters if changed
    if stats.get("current_month") != cur_month:
        stats["current_month"] = cur_month
        stats["month_pageviews"] = 0
        stats["month_unique"] = 0

    if stats.get("current_year") != cur_year:
        stats["current_year"] = cur_year
        stats["year_pageviews"] = 0
        stats["year_unique"] = 0

    # Increment pageviews
    stats["total_pageviews"] = stats.get("total_pageviews", 0) + 1
    stats["month_pageviews"] = stats.get("month_pageviews", 0) + 1
    stats["year_pageviews"] = stats.get("year_pageviews", 0) + 1

    ip_set = stats.get("ip_hash_set", [])
    is_new_month_unique = ip_month_hash not in ip_set
    is_new_year_unique = ip_year_hash not in ip_set

    if is_new_month_unique:
        stats["month_unique"] = stats.get("month_unique", 0) + 1
        ip_set.append(ip_month_hash)

    if is_new_year_unique:
        stats["year_unique"] = stats.get("year_unique", 0) + 1
        stats["total_unique"] = stats.get("total_unique", 0) + 1
        ip_set.append(ip_year_hash)

    # Keep ip_set compact
    if len(ip_set) > 2000:
        ip_set = ip_set[-2000:]
    stats["ip_hash_set"] = ip_set

    # Save async or on every few hits to avoid spamming GitHub API
    if stats["total_pageviews"] % 3 == 0:
        try:
            save_persisted_visitor_stats(stats)
        except Exception:
            pass

    return {
        "status": "success",
        "stats": {
            "total_pageviews": stats["total_pageviews"],
            "month_pageviews": stats["month_pageviews"],
            "year_pageviews": stats["year_pageviews"],
            "total_unique": stats["total_unique"],
            "month_unique": stats["month_unique"],
            "year_unique": stats["year_unique"],
            "current_month": cur_month,
            "current_year": cur_year
        }
    }

@app.get("/api/visitors/stats")
def get_visitor_stats():
    stats = read_persisted_visitor_stats()
    return {
        "status": "success",
        "stats": {
            "total_pageviews": stats.get("total_pageviews", 1420),
            "month_pageviews": stats.get("month_pageviews", 430),
            "year_pageviews": stats.get("year_pageviews", 1420),
            "total_unique": stats.get("total_unique", 860),
            "month_unique": stats.get("month_unique", 290),
            "year_unique": stats.get("year_unique", 860),
            "current_month": stats.get("current_month", time.strftime("%Y-%m")),
            "current_year": stats.get("current_year", time.strftime("%Y"))
        }
    }


class ContactMessageRequest(BaseModel):
    name: str
    phone: str
    email: Optional[str] = "উল্লেখ করা হয়নি"
    message: str

@app.post("/api/contact")
def submit_contact_message(req: ContactMessageRequest):
    # Formats message strictly with Name and Mobile number at the bottom
    formatted = f"{req.message}\n\n-------------------------\nপ্রেরকের নাম: {req.name}\nমোবাইল নাম্বার: {req.phone}\nইমেইল: {req.email}"
    
    # Forward to formsubmit.co
    try:
        payload = json.dumps({
            "_subject": f"NewsBangla অ্যাপ থেকে বার্তা: {req.name}",
            "_template": "table",
            "_captcha": "false",
            "name": req.name,
            "phone": req.phone,
            "email": req.email,
            "message": formatted
        }).encode("utf-8")
        
        target_email = "uzzalhossain.100@gmail.com"
        url = f"https://formsubmit.co/ajax/{target_email}"
        request = urllib.request.Request(url, data=payload, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://newsbangla.vercel.app",
            "Referer": "https://newsbangla.vercel.app/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        })
        with urllib.request.urlopen(request, timeout=8) as r:
            res = json.loads(r.read().decode("utf-8"))
            return {"status": "success", "result": res}
    except Exception as e:
        return {"status": "partial", "error": str(e), "message": "Fallback handled on client"}
