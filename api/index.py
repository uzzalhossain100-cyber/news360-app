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

CATEGORY_KEYWORDS = {
    'sports': ['খেলা', 'ক্রিকেট', 'ফুটবল', 'মেসি', 'রোনালদো', 'অধিনায়ক', 'বিশ্বকাপ', 'উইকেট', 'গোল', 'ম্যাচ', 'সিরিজ', 'বিসিবি', 'ফিফা', 'সাকিব', 'তামিম'],
    'tech': ['প্রযুক্তি', 'স্মার্টফোন', 'আইফোন', 'এআই', 'অ্যাপল', 'ফেসবুক', 'গুগল', 'ইন্টারনেট', 'কম্পিউটার', 'হোয়াটসঅ্যাপ', 'সাইবার', 'রোবট', 'টেলিযোগাযোগ'],
    'entertainment': ['সিনেমা', 'নাটক', 'অভিনেতা', 'অভিনেত্রী', 'গান', 'চলচ্চিত্র', 'হলিউড', 'বলিউড', 'ঢালিউড', 'শাকিব', 'তারকা', 'মিউজিক', 'বিনোদন'],
    'economy': ['অর্থনীতি', 'টাকা', 'ব্যাংক', 'শেয়ারবাজার', 'পুঁজিবাজার', 'ডলার', 'রুপির', 'মুদ্রাস্ফীতি', 'স্বর্ণের', 'বাজেট', 'রাজস্ব', 'কর', 'রপ্তানি', 'আমদানি'],
    'international': ['যুক্তরাষ্ট্র', 'চীন', 'ভারত', 'পাকিস্তান', 'রাশিয়া', 'ইউক্রেন', 'ইসরায়েল', 'গাজা', 'ফিলিস্তিন', 'ইরান', 'আন্তর্জাতিক', 'ট্রাম্প', 'বাইডেন'],
    'national': ['জাতীয়', 'বাংলাদেশ', 'সরকার', 'উপদেষ্টা', 'ঢাকা', 'চট্টগ্রাম', 'আদালত', 'মামলা', 'পুলিশ', 'আইন', 'নির্বাচন', 'মন্ত্রণালয়', 'রাজনীতি', 'বিএনপি', 'জামায়াত']
}

def detect_cat(title):
    t = title.lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in t: return cat
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

    if category and category != 'all':
        news = [it for it in news if it['category'] == category]
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
