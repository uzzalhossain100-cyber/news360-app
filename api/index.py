from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import time
import os
import urllib.request
import re
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup

app = FastAPI(title="News360 Vercel Serverless API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

headers_browser = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
headers_bot = {'User-Agent': 'facebookexternalhit/1.1'}

def detect_cat(title, url=""):
    t = title.lower()
    u = (url or '').lower()
    if '/sports' in u or '/khela' in u: return 'sports'
    if '/entertainment' in u or '/binodon' in u: return 'entertainment'
    if '/economy' in u or '/business' in u or '/banijjo' in u: return 'economy'
    if '/technology' in u or '/tech' in u or '/projukti' in u: return 'tech'
    if '/international' in u or '/bishwo' in u or '/world' in u: return 'international'

    sportsWords = ['ক্রিকেট', 'ফুটবল', 'মেসি', 'রোনালদো', 'অধিনায়ক', 'বিশ্বকাপ', 'উইকেট', 'গোল', 'ম্যাচ', 'সিরিজ', 'বিসিবি', 'ফিফা', 'সাকিব', 'তামিম', 'বোলার', 'ব্যাটসম্যান', 'অলরাউন্ডার', 'টেনিস', 'হাফসেঞ্চুরি', 'সেঞ্চুরি', 'টুর্নামেন্ট', 'আইপিএল', 'বিপিএল', 'টাইগার', 'ম্যানচেস্টার', 'বার্সেলোনা', 'রিয়াল মাদ্রিদ', 'পিএসজি', 'লা লিগা', 'প্রিমিয়ার লিগ', 'চ্যাম্পিয়নস লিগ', 'খেলার খবর', 'খেলাধুলা', 'স্টেডিয়াম', 'বোলিং', 'ব্যাটিং']
    for w in sportsWords:
        if w in t: return 'sports'

    entWords = ['সিনেমা', 'নাটক', 'চলচ্চিত্র', 'হলিউড', 'বলিউড', 'ঢালিউড', 'শাকিব খান', 'তারকা', 'বিনোদন', 'মিউজিক ভিডিও', 'ফিল্ম', 'কনসার্ট', 'গায়িকা', 'গায়ক', 'ওটিটি', 'নায়ক', 'নায়িকা', 'অভিনেতা', 'অভিনেত্রী', 'শুটিং', 'অস্কার', 'কান চলচ্চিত্র', 'নাট্যকার', 'গান রিলিজ', 'নতুন গান', 'অ্যালবাম']
    for w in entWords:
        if w in t: return 'entertainment'

    techWords = ['প্রযুক্তি', 'স্মার্টফোন', 'আইফোন', 'এআই', 'কৃত্রিম বুদ্ধিমত্তা', 'অ্যাপল', 'ফেসবুক', 'গুগল', 'ইন্টারনেট', 'কম্পিউটার', 'হোয়াটসঅ্যাপ', 'সাইবার', 'রোবট', 'টেলিযোগাযোগ', 'ডিজিটাল', 'ড্রোন', 'সফটওয়্যার', 'গ্যাজেট', 'আইওএস', 'অ্যান্ড্রয়েড', 'মেটা', 'মাইক্রোসফট', 'মহাকাশ', 'নাসা', 'চ্যাটজিপিটি', 'ওপেনএআই', 'টেলিকম']
    for w in techWords:
        if w in t: return 'tech'

    econWords = ['অর্থনীতি', 'শেয়ারবাজার', 'পুঁজিবাজার', 'ডলার', 'মুদ্রাস্ফীতি', 'স্বর্ণের দাম', 'বাজেট', 'রাজস্ব', 'রপ্তানি', 'আমদানি', 'রেমিট্যান্স', 'জ্বালানি', 'বণিক', 'বাণিজ্য', 'ব্যবসায়ী', 'মূল্যবৃদ্ধি', 'আইএমএফ', 'মূল্যস্ফীতি', 'ভ্যাট', 'এলএনজি', 'পেট্রোবাংলা', 'সোনা', 'অর্থনৈতিক', 'বাণিজ্যিক', 'টাকার মান', 'সঞ্চয়পত্র', 'সুদের হার', 'ব্যাংকিং', 'বাংলাদেশ ব্যাংক']
    for w in econWords:
        if w in t: return 'economy'

    intlWords = ['যুক্তরাষ্ট্র', 'চীন', 'ভারত', 'পাকিস্তান', 'রাশিয়া', 'ইউক্রেন', 'ইসরায়েল', 'গাজা', 'ফিলিস্তিন', 'ইরান', 'আন্তর্জাতিক', 'ট্রাম্প', 'বাইডেন', 'জাতিসংঘ', 'মধ্যপ্রাচ্য', 'ব্রিটেন', 'নেপাল', 'আমেরিকা', 'লেবানন', 'পুতিন', 'হোয়াইট হাউস', 'ইউরোপ', 'ফ্রান্স', 'জার্মানি', 'সৌদি আরব', 'ইয়েমেন', 'হুতি', 'বেইজিং', 'মস্কো', 'তেহরান', 'কিয়েভ', 'ন্যাটো', 'সিরিয়া']
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
    # 1. Prothom Alo
    try:
        req = urllib.request.Request("https://www.prothomalo.com/feed", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=4) as r:
            root = ET.fromstring(r.read())
            now = time.time()
            for it in root.findall('.//item')[:25]:
                t = it.find('title')
                l = it.find('link')
                if t is not None and l is not None:
                    cat = detect_cat(t.text)
                    news.append({
                        "id": l.text,
                        "title": t.text.strip(),
                        "link": l.text.strip(),
                        "timestamp": now,
                        "category": cat,
                        "source_id": "prothomalo",
                        "source_name": "প্রথম আলো",
                        "source_badge": "Prothom Alo",
                        "source_color": "#e11d48",
                        "image": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=600&auto=format&fit=crop&q=80"
                    })
    except Exception:
        pass

    # 2. Ittefaq
    try:
        req = urllib.request.Request("https://www.ittefaq.com.bd/latest-news", headers=headers_bot)
        with urllib.request.urlopen(req, timeout=4) as r:
            soup = BeautifulSoup(r.read(), 'html.parser')
            now = time.time()
            for a in soup.find_all('a', href=True):
                h = a['href']
                t = a.get_text(strip=True)
                if re.search(r'/\d+/', h) and len(t) > 20:
                    full = h if h.startswith('http') else ('https:' + h if h.startswith('//') else 'https://www.ittefaq.com.bd' + h)
                    cat = detect_cat(t)
                    news.append({
                        "id": full,
                        "title": t,
                        "link": full,
                        "timestamp": now,
                        "category": cat,
                        "source_id": "ittefaq",
                        "source_name": "দৈনিক ইত্তেফাক",
                        "source_badge": "Ittefaq",
                        "source_color": "#2563eb",
                        "image": "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?w=600&auto=format&fit=crop&q=80"
                    })
    except Exception:
        pass

        # 3. Channel 24 via RSS
    try:
        req = urllib.request.Request("https://news.google.com/rss/search?q=site:channel24bd.tv&hl=bn&gl=BD&ceid=BD:bn", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=3) as r:
            soup = BeautifulSoup(r.read(), 'xml')
            for it in soup.find_all('item')[:15]:
                raw_t = it.find('title').text
                t = re.sub(r'\s*-\s*(Channel 24|News).*$', '', raw_t, flags=re.I).strip()
                l = it.find('link').text
                if len(t) > 20 and not t.startswith('Channel 24'):
                    news.append({
                        "id": l,
                        "title": t,
                        "link": l,
                        "timestamp": time.time(),
                        "category": detect_cat(t, l),
                        "source_id": "channel24",
                        "source_name": "চ্যানেল ২৪",
                        "source_badge": "Channel 24",
                        "source_color": "#0284c7",
                        "image": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=600&auto=format&fit=crop&q=80"
                    })
    except Exception:
        pass

    # 4. NTV via RSS
    try:
        req = urllib.request.Request("https://news.google.com/rss/search?q=site:ntvbd.com&hl=bn&gl=BD&ceid=BD:bn", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=3) as r:
            soup = BeautifulSoup(r.read(), 'xml')
            for it in soup.find_all('item')[:15]:
                raw_t = it.find('title').text
                t = re.sub(r'\s*-\s*(NTV|NTV Online).*$', '', raw_t, flags=re.I).strip()
                l = it.find('link').text
                if len(t) > 20 and not t.startswith('NTV'):
                    news.append({
                        "id": l,
                        "title": t,
                        "link": l,
                        "timestamp": time.time(),
                        "category": detect_cat(t, l),
                        "source_id": "ntv",
                        "source_name": "এনটিভি",
                        "source_badge": "NTV",
                        "source_color": "#16a34a",
                        "image": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=600&auto=format&fit=crop&q=80"
                    })
    except Exception:
        pass

    # 5. RTV via RSS
    try:
        req = urllib.request.Request("https://news.google.com/rss/search?q=site:rtvonline.com&hl=bn&gl=BD&ceid=BD:bn", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=3) as r:
            soup = BeautifulSoup(r.read(), 'xml')
            for it in soup.find_all('item')[:15]:
                raw_t = it.find('title').text
                t = re.sub(r'\s*-\s*(RTV|Rtvonline).*$', '', raw_t, flags=re.I).strip()
                l = it.find('link').text
                if len(t) > 20 and not t.startswith('RTV'):
                    news.append({
                        "id": l,
                        "title": t,
                        "link": l,
                        "timestamp": time.time(),
                        "category": detect_cat(t, l),
                        "source_id": "rtv",
                        "source_name": "আরটিভি",
                        "source_badge": "RTV",
                        "source_color": "#ea580c",
                        "image": "https://images.unsplash.com/photo-1586339949916-3e9457bef6d3?w=600&auto=format&fit=crop&q=80"
                    })
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
