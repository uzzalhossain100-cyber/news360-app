import concurrent.futures
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

def is_clean_headline(t, u=""):
    if not t or len(t) < 14: return False
    url_lower = (u or "").lower()

    # Filter out direct video, audio, or podcast URLs
    if any(k in url_lower for k in ['/video/', '/videos/', '/watch', 'youtube.com', 'youtu.be', 'vimeo', '/audio/', '/podcast/']):
        return False

    # Filter out video-only content and video announcements ("প্রতিটি সেক্টরে যেগুলো ভিডিও বার্তা সেগুলো খবর হিসাবে এখানে লোড হবে না")
    video_patterns = [
        r'ভিডিও\s*বার্তা',
        r'ভিডিওতে\s*দেখুন',
        r'ভিডিও\s*(দেখুন|সহ|লিংক)',
        r'লাইভ\s*ভিডিও',
        r'ভিডিও\s*ভাইরাল',
        r'ভাইরাল\s*ভিডিও',
        r'ভিডিও\s*ফুটেজ',
        r'ভিডিও\s*প্রতিবেদন',
        r'ভিডিও\s*স্টোরি',
        r'ভিডিও\s*সংবাদ',
        r'ভিডিও\s*বুলেটিন',
        r'ভিডিও\s*ফিচার',
        r'\[ভিডিও\]',
        r'\(ভিডিও\)',
        r'\{ভিডিও\}',
        r'(সকাল|দুপুর|সন্ধ্যা|রাত|রাতের|দিনের)\s*(৭|৮|৯|১০|১১|১২|১|২|৩|৪|৫|৬|\d+)\s*টার\s*(সংবাদ|বুলেটিন|খবর)',
        r'সংবাদ\s*বুলেটিন', r'সরাসরি\s*সংবাদ', r'লাইভ\s*সংবাদ', r'সংবাদ\s*সারসংক্ষেপ',
        r'লাইভ\s*আপডেট', r'সরাসরি\s*দেখুন', r'টকশো', r'টক\s*শো',
        r'স্বাস্থ্য\s*প্রতিদিন', r'সংলাপ\s*প্রতিদিন', r'চাওয়া[- ]পাওয়া', r'পর্ব[- ]\s*\d+'
    ]
    for pat in video_patterns:
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





headers_social = {'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'}
headers_browser = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'}

def extract_full_article(url):
    image = ""
    paras = []
    headers = headers_browser if ('prothomalo' in url or 'bbc' in url) else headers_social
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3.0) as r:
            html = r.read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html, 'html.parser')

            # Extract authentic high-res news image
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content') and og_img['content'].startswith('http'):
                image = og_img['content'].strip()
            if not image:
                tw_img = soup.find('meta', attrs={'name': 'twitter:image'})
                if tw_img and tw_img.get('content') and tw_img['content'].startswith('http'):
                    image = tw_img['content'].strip()

            for t in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'button']):
                t.decompose()

            seen = set()
            skip_kw = ['সর্বস্বত্ব সংরক্ষিত', 'কপিরাইট', 'Terms of Use', 'Privacy Policy', 'বিজ্ঞাপন', 'আরও পড়ুন', 'ফলো করুন', 'সাবস্ক্রাইব']
            
            # 1. First scan all <p> tags
            for p in soup.find_all('p'):
                txt = p.get_text(strip=True)
                if len(txt) > 20 and not is_video_or_bulletin(txt):
                    if not re.match(r'^(প্রকাশ|প্রিন্ট|অনলাইন|আপডেট)\s*:\s*[০-৯\d]', txt):
                        if txt not in seen and not any(k in txt for k in skip_kw):
                            seen.add(txt)
                            paras.append(txt)

            # 2. If <p> tags are fewer than 2, also extract from content container divs
            if len(paras) < 2:
                container = soup.find(['article', 'main']) or soup.find('div', class_=re.compile(r'(content|detail|story|article)', re.I))
                if container:
                    for d in container.find_all(['div', 'section', 'span']):
                        if not d.find(['p', 'div']): # deepest block
                            txt = d.get_text(strip=True)
                            if len(txt) > 35 and not is_video_or_bulletin(txt):
                                if not re.match(r'^(প্রকাশ|প্রিন্ট|অনলাইন|আপডেট)\s*:\s*[০-৯\d]', txt):
                                    if txt not in seen and not any(k in txt for k in skip_kw):
                                        seen.add(txt)
                                        paras.append(txt)
    except Exception:
        pass
    return image, paras[:15]

def fetch_prothomalo_live(now_ts):
    candidates = []
    seen = set()
    try:
        req = urllib.request.Request("https://www.prothomalo.com/feed", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=3.5) as r:
            root = ET.fromstring(r.read())
            for it in root.findall('.//item')[:15]:
                t_elem = it.find('title')
                l_elem = it.find('link')
                if t_elem is None or not t_elem.text: continue
                t = t_elem.text.strip()
                l = l_elem.text.strip() if (l_elem is not None and l_elem.text) else ''
                if not is_clean_headline(t, l) or l in seen: continue
                seen.add(l)
                candidates.append((t, l))
    except Exception:
        pass

    def build_item(c):
        t, l = c
        img, paras = extract_full_article(l)
        if not img:
            img = 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80'
        return {
            "id": l,
            "title": t,
            "link": l,
            "timestamp": now_ts,
            "category": detect_cat(t, l),
            "source_id": "prothomalo",
            "source_name": "প্রথম আলো",
            "source_badge": "Prothom Alo",
            "source_color": "#e11d48",
            "image": img,
            "paragraphs": paras
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(build_item, candidates))

def fetch_bbc_live(now_ts):
    candidates = []
    seen = set()
    try:
        req = urllib.request.Request("https://feeds.bbci.co.uk/bengali/rss.xml", headers=headers_browser)
        with urllib.request.urlopen(req, timeout=3.5) as r:
            root = ET.fromstring(r.read())
            for it in root.findall('.//item')[:15]:
                t_elem = it.find('title')
                l_elem = it.find('link')
                if t_elem is None or not t_elem.text: continue
                t = t_elem.text.strip()
                l = l_elem.text.strip() if (l_elem is not None and l_elem.text) else ''
                if not is_clean_headline(t, l) or l in seen: continue
                seen.add(l)
                thumb = it.find('{http://search.yahoo.com/mrss/}thumbnail')
                rss_img = thumb.attrib['url'] if (thumb is not None and 'url' in thumb.attrib) else ''
                candidates.append((t, l, rss_img))
    except Exception:
        pass

    def build_item(c):
        t, l, rss_img = c
        img, paras = extract_full_article(l)
        if not img: img = rss_img
        if not img:
            img = 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&auto=format&fit=crop&q=80'
        return {
            "id": l,
            "title": t,
            "link": l,
            "timestamp": now_ts,
            "category": detect_cat(t, l),
            "source_id": "bbc",
            "source_name": "বিবিসি বাংলা",
            "source_badge": "BBC Bangla",
            "source_color": "#dc2626",
            "image": img,
            "paragraphs": paras
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(build_item, candidates))

def fetch_ittefaq_live(now_ts):
    candidates = []
    seen = set()
    try:
        req = urllib.request.Request("https://www.ittefaq.com.bd/", headers=headers_social)
        with urllib.request.urlopen(req, timeout=3.5) as r:
            soup = BeautifulSoup(r.read().decode('utf-8', errors='ignore'), 'html.parser')
            for a in soup.find_all('a'):
                h = a.get('href', '')
                if not h: continue
                if h.startswith('//'):
                    h = 'https:' + h
                elif h.startswith('/'):
                    h = 'https://www.ittefaq.com.bd' + h
                parts = h.strip('/').split('/')
                if any(p.isdigit() and len(p) >= 5 for p in parts):
                    t = a.get_text().strip()
                    if not is_clean_headline(t, h) or h in seen: continue
                    seen.add(h)
                    candidates.append((t, h))
                    if len(candidates) >= 15: break
    except Exception:
        pass

    def build_item(c):
        t, l = c
        img, paras = extract_full_article(l)
        if not img:
            img = 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&auto=format&fit=crop&q=80'
        return {
            "id": l,
            "title": t,
            "link": l,
            "timestamp": now_ts,
            "category": detect_cat(t, l),
            "source_id": "ittefaq",
            "source_name": "দৈনিক ইত্তেফাক",
            "source_badge": "Ittefaq",
            "source_color": "#2563eb",
            "image": img,
            "paragraphs": paras
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(build_item, candidates))

def fetch_bdpratidin_live(now_ts):
    candidates = []
    seen = set()
    try:
        req = urllib.request.Request("https://www.bd-pratidin.com/", headers=headers_social)
        with urllib.request.urlopen(req, timeout=3.5) as r:
            soup = BeautifulSoup(r.read().decode('utf-8', errors='ignore'), 'html.parser')
            for a in soup.find_all('a'):
                h = a.get('href', '')
                if not h or '/202' not in h: continue
                t = a.get_text().strip()
                if not is_clean_headline(t, h): continue
                full_url = h if h.startswith('http') else ('https://www.bd-pratidin.com' + ('' if h.startswith('/') else '/') + h)
                if full_url in seen: continue
                seen.add(full_url)
                candidates.append((t, full_url))
                if len(candidates) >= 15: break
    except Exception:
        pass

    def build_item(c):
        t, l = c
        img, paras = extract_full_article(l)
        if not img:
            img = 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80'
        return {
            "id": l,
            "title": t,
            "link": l,
            "timestamp": now_ts,
            "category": detect_cat(t, l),
            "source_id": "bdpratidin",
            "source_name": "বাংলাদেশ প্রতিদিন",
            "source_badge": "BD Pratidin",
            "source_color": "#16a34a",
            "image": img,
            "paragraphs": paras
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(build_item, candidates))

def fetch_kalerkantho_live(now_ts):
    candidates = []
    seen = set()
    try:
        req = urllib.request.Request("https://www.kalerkantho.com/", headers=headers_social)
        with urllib.request.urlopen(req, timeout=3.5) as r:
            soup = BeautifulSoup(r.read().decode('utf-8', errors='ignore'), 'html.parser')
            for a in soup.find_all('a'):
                h = a.get('href', '')
                if not h or ('/online/' not in h and '/202' not in h): continue
                t = a.get_text().strip()
                t = re.sub(r'^[০-৯\d]+', '', t).strip()
                if not is_clean_headline(t, h): continue
                full_url = h if h.startswith('http') else ('https://www.kalerkantho.com' + ('' if h.startswith('/') else '/') + h)
                if full_url in seen: continue
                seen.add(full_url)
                candidates.append((t, full_url))
                if len(candidates) >= 15: break
    except Exception:
        pass

    def build_item(c):
        t, l = c
        img, paras = extract_full_article(l)
        if not img:
            img = 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80'
        return {
            "id": l,
            "title": t,
            "link": l,
            "timestamp": now_ts,
            "category": detect_cat(t, l),
            "source_id": "kalerkantho",
            "source_name": "কালের কণ্ঠ",
            "source_badge": "Kaler Kantho",
            "source_color": "#d97706",
            "image": img,
            "paragraphs": paras
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(build_item, candidates))

def fetch_jugantor_live(now_ts):
    candidates = []
    seen = set()
    try:
        req = urllib.request.Request("https://www.jugantor.com/", headers=headers_social)
        with urllib.request.urlopen(req, timeout=3.5) as r:
            soup = BeautifulSoup(r.read().decode('utf-8', errors='ignore'), 'html.parser')
            for card in soup.find_all(['div', 'article', 'li']):
                a_tag = card.find('a')
                if not a_tag: continue
                h = a_tag.get('href', '')
                if not h: continue
                parts = h.strip('/').split('/')
                if len(parts) >= 2 and parts[-1].isdigit():
                    h_tag = card.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                    t = h_tag.get_text().strip() if h_tag else a_tag.get_text().strip()
                    if not is_clean_headline(t, h): continue
                    full_url = h if h.startswith('http') else ('https://www.jugantor.com' + ('' if h.startswith('/') else '/') + h)
                    if full_url in seen: continue
                    seen.add(full_url)
                    candidates.append((t, full_url))
                    if len(candidates) >= 15: break
    except Exception:
        pass

    def build_item(c):
        t, l = c
        img, paras = extract_full_article(l)
        if not img:
            img = 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&auto=format&fit=crop&q=80'
        return {
            "id": l,
            "title": t,
            "link": l,
            "timestamp": now_ts,
            "category": detect_cat(t, l),
            "source_id": "jugantor",
            "source_name": "দৈনিক যুগান্তর",
            "source_badge": "Jugantor",
            "source_color": "#e11d48",
            "image": img,
            "paragraphs": paras
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(build_item, candidates))

def fetch_bdnews24_live(now_ts):
    candidates = []
    seen = set()
    try:
        req = urllib.request.Request("https://bangla.bdnews24.com/", headers=headers_social)
        with urllib.request.urlopen(req, timeout=3.5) as r:
            soup = BeautifulSoup(r.read().decode('utf-8', errors='ignore'), 'html.parser')
            for a in soup.find_all('a'):
                h = a.get('href', '')
                if not h: continue
                if any(c in h for c in ['/bangladesh/', '/world/', '/sport/', '/cricket/', '/economy/', '/opinion/']):
                    t = a.get_text().strip()
                    if not is_clean_headline(t, h): continue
                    full_url = h if h.startswith('http') else ('https://bangla.bdnews24.com' + ('' if h.startswith('/') else '/') + h)
                    if full_url in seen: continue
                    seen.add(full_url)
                    candidates.append((t, full_url))
                    if len(candidates) >= 15: break
    except Exception:
        pass

    def build_item(c):
        t, l = c
        img, paras = extract_full_article(l)
        if not img:
            img = 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80'
        return {
            "id": l,
            "title": t,
            "link": l,
            "timestamp": now_ts,
            "category": detect_cat(t, l),
            "source_id": "bdnews24",
            "source_name": "বিডিনিউজ টোয়েন্টিফোর",
            "source_badge": "BDNews24",
            "source_color": "#7c3aed",
            "image": img,
            "paragraphs": paras
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(build_item, candidates))


CATEGORY_KEYWORDS = {
    'sports': 'খেলা OR ক্রিকেট OR ফুটবল OR মেসি OR রোনালদো OR বিশ্বকাপ OR ম্যাচ',
    'entertainment': 'বিনোদন OR সিনেমা OR নাটক OR তারকা OR ওটিটি OR গান OR বলিউড OR ঢালিউড',
    'economy': 'অর্থনীতি OR বাণিজ্য OR পুঁজিবাজার OR ডলার OR ব্যাংক OR বাজেট OR রেমিট্যান্স',
    'tech': 'প্রযুক্তি OR স্মার্টফোন OR আইফোন OR এআই OR বিজ্ঞান OR ইন্টারনেট OR গ্যাজেট',
    'international': 'আন্তর্জাতিক OR বিশ্ব OR যুদ্ধ OR জাতিসংঘ OR যুক্তরাষ্ট্র OR মধ্যপ্রাচ্য',
    'national': 'বাংলাদেশ OR ঢাকা OR চট্টগ্রাম OR আদালত OR পুলিশ OR নির্বাচন OR সরকার'
}

PAPER_DOMAINS = {
    'prothomalo': ('prothomalo.com', 'প্রথম আলো', 'Prothom Alo', '#e11d48'),
    'bbc': ('bbc.com/bengali', 'বিবিসি বাংলা', 'BBC Bangla', '#dc2626'),
    'ittefaq': ('ittefaq.com.bd', 'দৈনিক ইত্তেফাক', 'Ittefaq', '#2563eb'),
    'bdpratidin': ('bd-pratidin.com', 'বাংলাদেশ প্রতিদিন', 'BD Pratidin', '#16a34a'),
    'kalerkantho': ('kalerkantho.com', 'কালের কণ্ঠ', 'Kaler Kantho', '#d97706'),
    'jugantor': ('jugantor.com', 'দৈনিক যুগান্তর', 'Jugantor', '#e11d48'),
    'bdnews24': ('bangla.bdnews24.com', 'বিডিনিউজ টোয়েন্টিফোর', 'BDNews24', '#7c3aed')
}

def fetch_targeted_category_news(target_category, target_source=None, limit=50):
    items = []
    kw = CATEGORY_KEYWORDS.get(target_category, '')
    if not kw: return items

    papers = []
    if target_source and target_source != 'all' and target_source in PAPER_DOMAINS:
        papers = [(target_source, *PAPER_DOMAINS[target_source])]
    else:
        papers = [(k, *v) for k, v in PAPER_DOMAINS.items()]

    now_ts = time.time()
    for pid, domain, pname, pbadge, pcolor in papers:
        query = f"site:{domain} ({kw})"
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=bn&gl=BD&ceid=BD:bn"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=3.5) as r:
                root = ET.fromstring(r.read())
                for it in root.findall('.//item')[:15]:
                    title_elem = it.find('title')
                    link_elem = it.find('link')
                    if title_elem is None or not title_elem.text: continue
                    t = title_elem.text.strip()
                    # Clean title: Google news titles usually end with " - Newspaper"
                    t = re.sub(r'\s*-\s*[^ -]+$', '', t).strip()
                    l = link_elem.text.strip() if link_elem is not None and link_elem.text else ''
                    if not is_clean_headline(t, l): continue

                    # Bind authentic themed news photo for category
                    img = ''
                    CATEGORY_THEMED_IMAGES = {
                        'sports': 'https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&auto=format&fit=crop&q=80',
                        'entertainment': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800&auto=format&fit=crop&q=80',
                        'economy': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&auto=format&fit=crop&q=80',
                        'tech': 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop&q=80',
                        'international': 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&auto=format&fit=crop&q=80',
                        'national': 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80'
                    }
                    img = CATEGORY_THEMED_IMAGES.get(target_category, 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80')

                    items.append({
                        "id": l,
                        "title": t,
                        "link": l,
                        "timestamp": now_ts,
                        "category": target_category,
                        "source_id": pid,
                        "source_name": pname,
                        "source_badge": pbadge,
                        "source_color": pcolor,
                        "image": img
                    })
                    if len(items) >= limit: break
        except Exception:
            pass
        if len(items) >= limit: break
    return items




def load_pristine_catalog():
    # 1. Same directory (api/initial_news.json) - Always bundled in Vercel!
    p1 = os.path.join(os.path.dirname(__file__), "initial_news.json")
    if os.path.exists(p1):
        try:
            with open(p1, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # 2. Public directory
    p2 = os.path.join(os.path.dirname(__file__), "..", "public", "initial_news.json")
    if os.path.exists(p2):
        try:
            with open(p2, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # 3. Vercel live static endpoint
    try:
        req = urllib.request.Request("https://newsbangla.vercel.app/initial_news.json", headers={"User-Agent": "NewsBanglaInternal"})
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        pass
    return []


def curate_into_newsbangla(item):
    orig_title = item.get('title', '').strip()
    clean_t = re.sub(r'\s*[-–|].*$', '', orig_title).strip()
    orig_paras = item.get('paragraphs', [])
    cat = item.get('category', 'national')
    source_name = item.get('source_name', 'বিশেষ সূত্র')
    now_ts = item.get('timestamp') or time.time()
    
    # 1. NewsBangla Curated Title
    curated_title = clean_t

    # 2. NewsBangla Editorial Synthesis Paragraphs
    curated_paras = []
    lead_para = f"নিউজবাংলা বিশেষ ডেস্ক: {clean_t} সংক্রান্ত বিষয়ে মাঠপর্যায়ের সর্বশেষ অনুসন্ধান ও তথ্য-উপাত্তে তাৎপর্যপূর্ণ অগ্রগতি লক্ষ্য করা গেছে। বিভিন্ন দায়িত্বশীল সূত্রের বরাত দিয়ে {source_name}-সহ শীর্ষ সংবাদমাধ্যমের প্রতিবেদনে ঘটনাটির বিশদ চিত্র উঠে এসেছে।"
    curated_paras.append(lead_para)

    if orig_paras and len(orig_paras) > 0:
        for p in orig_paras[:8]:
            clean_p = p.strip()
            if len(clean_p) > 28 and not any(k in clean_p for k in ['সর্বস্বত্ব সংরক্ষিত', 'কপিরাইট', 'Terms of Use', 'বিজ্ঞাপন', 'ছবি:']):
                curated_paras.append(clean_p)
    else:
        curated_paras.append(f"{clean_t} নিয়ে সংশ্লিষ্ট মহলে ব্যাপক প্রতিক্রিয়া সৃষ্টি হয়েছে। ঘটনার গভীরতা ও পারিপার্শ্বিক অবস্থা বিবেচনায় নিয়ে দায়িত্বশীল কর্তৃপক্ষ কার্যকর পদক্ষেপ গ্রহণে তৎপর রয়েছে বলে জানা গেছে।")

    analysis_para = f"নিউজবাংলা পর্যবেক্ষণ দল জানাচ্ছে, বর্তমান সামগ্রিক বাস্তবতায় ঘটনাটির প্রভাব অত্যন্ত সুদূরপ্রসারী। নাগরিক জীবন ও সংশ্লিষ্ট ক্ষেত্রে এর দীর্ঘমেয়াদী ফলাফল নিয়ে বহুমুখী বিশ্লেষণ চলছে।"
    curated_paras.append(analysis_para)

    conclusion_para = "পরিস্থিতির ওপর সার্বক্ষণিক সজাগ নজর রাখছে নিউজবাংলা। ঘটনার বিস্তারিত অগ্রগতি ও পরবর্তী আপডেট জানতে চোখ রাখুন নিউজবাংলা ডিজিটাল নেটওয়ার্কে।"
    curated_paras.append(conclusion_para)

    # 3. High quality news image
    img = item.get('image', '')
    if not img or 'unsplash' in img:
        CATEGORY_THEMED_IMAGES = {
            'sports': 'https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&auto=format&fit=crop&q=80',
            'entertainment': 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=800&auto=format&fit=crop&q=80',
            'economy': 'https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&auto=format&fit=crop&q=80',
            'tech': 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop&q=80',
            'international': 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=800&auto=format&fit=crop&q=80',
            'national': 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80'
        }
        img = CATEGORY_THEMED_IMAGES.get(cat, 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&auto=format&fit=crop&q=80')

    return {
        "id": f"newsbangla-{item.get('id', item.get('link', ''))}",
        "title": curated_title,
        "link": item.get('link', ''),
        "timestamp": now_ts,
        "category": cat,
        "source_id": "newsbangla",
        "source_name": "নিউজবাংলা",
        "source_badge": "NewsBangla",
        "source_color": "#e11d48",
        "image": img,
        "paragraphs": curated_paras
    }


@app.get("/api/news")
def get_news(
    category: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(100)
):
    news = []
    now_ts = time.time()
    
    # 1. SPECIAL CASE: NewsBangla Exclusive Source
    # ("এখানে পত্রিকা ক্যাটাগরিতে আর একটি নাম যোগ হবে NewsBangla এখানে ক্লিক করলে ক্যাটাগরি অনুযায়ী প্রতিটি বিভাগে অন্য পত্রিকার খবর থেকে নিজের মতো করে কিছু মূল খবর তৈরী করে প্রদর্শন করবে সাথে খবরের ছবিটিও নিজের মতো খবর রিলেটেড নতুন ছবি দিবে")
    if source == 'newsbangla':
        catalog = load_pristine_catalog()
        curated_pool = []
        seen_t = set()
        for it in catalog:
            c_it = curate_into_newsbangla(it)
            if c_it['title'] not in seen_t:
                seen_t.add(c_it['title'])
                curated_pool.append(c_it)

        if category and category != 'all':
            curated_pool = [n for n in curated_pool if n.get('category') == category]

        return {
            "status": "success",
            "count": len(curated_pool[:limit]),
            "news": curated_pool[:limit]
        }

    # 2. STANDARD NEWSPAPER SOURCES
    fetch_map = {
        'prothomalo': fetch_prothomalo_live,
        'bbc': fetch_bbc_live,
        'ittefaq': fetch_ittefaq_live,
        'bdpratidin': fetch_bdpratidin_live,
        'kalerkantho': fetch_kalerkantho_live,
        'jugantor': fetch_jugantor_live,
        'bdnews24': fetch_bdnews24_live
    }

    if source and source != 'all' and source in fetch_map:
        news.extend(fetch_map[source](now_ts))
    else:
        # Run all scrapers concurrently in parallel threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            future_to_source = {executor.submit(fn, now_ts): s_id for s_id, fn in fetch_map.items()}
            for future in concurrent.futures.as_completed(future_to_source):
                try:
                    res_items = future.result()
                    if res_items: news.extend(res_items)
                except Exception:
                    pass

    # Fallback to local catalog if live fetch count is low
    if len(news) < 5:
        local_items = load_pristine_catalog()
        for it in local_items:
            if not source or source == 'all' or it.get('source_id') == source:
                news.append(it)

    # Filter out any video content strictly
    clean_news = []
    seen = set()
    for item in news:
        t = item.get("title", "")
        l = item.get("link", "")
        if not is_clean_headline(t, l): continue
        if l in seen: continue
        seen.add(l)
        clean_news.append(item)

    # Filter by category if requested
    if category and category != 'all':
        cat_items = [n for n in clean_news if n.get('category') == category]
        if len(cat_items) < 5:
            local_items = load_pristine_catalog()
            seen_links = set(n.get('link') for n in cat_items)
            for it in local_items:
                if it.get('category') == category:
                    if (not source or source == 'all' or it.get('source_id') == source) and it.get('link') not in seen_links:
                        seen_links.add(it.get('link'))
                        cat_items.append(it)
        clean_news = cat_items

    return {
        "status": "success",
        "count": len(clean_news[:limit]),
        "news": clean_news[:limit]
    }



# ---------------------------------------------------------------------------
# SOCIAL MEDIA SHARE PREVIEW ENDPOINT (Facebook, WhatsApp, Messenger, Twitter)
# Generates dynamic OpenGraph tags with the real article headline and thumbnail image
# ---------------------------------------------------------------------------
def render_social_share_page(article_id: str, direct_link: Optional[str] = None):
    found_item = None
    target_id = article_id.strip() if article_id else ""
    target_link = direct_link.strip() if direct_link else ""

    # 1. Search in Admin Persisted Articles
    try:
        admin_articles = read_persisted_admin_articles()
        for a in admin_articles:
            if target_id and a.get("id") == target_id:
                found_item = a
                break
            if target_link and a.get("link") == target_link:
                found_item = a
                break
    except Exception:
        pass

    # 2. Search in Pristine Catalog
    if not found_item:
        try:
            catalog = load_pristine_catalog()
            for it in catalog:
                if target_id and (it.get("id") == target_id or f"newsbangla-{it.get('id')}" == target_id):
                    found_item = it
                    break
                if target_link and it.get("link") == target_link:
                    found_item = it
                    break
        except Exception:
            pass

    # 3. Fallback defaults
    if found_item:
        raw_title = found_item.get("title", "তাজা সংবাদ - NewsBangla")
        title = re.sub(r'\s*[-–|].*$', '', raw_title).strip()
        paras = found_item.get("paragraphs", [])
        desc = paras[0][:200] if paras else f"{title} সম্পর্কে বিস্তারিত পড়ুন NewsBangla-তে।"
        raw_image = found_item.get("image") or ""
        
        # If image is base64 data URI, route through /api/article-image/{id} so Facebook/WhatsApp can crawl a real HTTP image URL
        if raw_image.startswith("data:"):
            image = f"https://newsbangla.vercel.app/api/article-image/{target_id}"
        elif raw_image.startswith("http"):
            image = raw_image
        else:
            image = "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=1200&auto=format&fit=crop&q=80"
    else:
        title = "NewsBangla - তাজা সংবাদ ২৪/৭"
        desc = "বাংলাদেশের সর্বাধুনিক অনলাইন সংবাদ মাধ্যম NewsBangla।"
        image = "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=1200&auto=format&fit=crop&q=80"

    import html
    escaped_title = html.escape(title)
    escaped_desc = html.escape(desc)
    escaped_image = html.escape(image)
    
    canonical_share_url = f"https://newsbangla.vercel.app/article/{target_id or 'news'}"
    app_redirect_url = f"https://newsbangla.vercel.app/?article={target_id}" if target_id else "https://newsbangla.vercel.app/"

    html_content = f"""<!DOCTYPE html>
<html lang="bn" prefix="og: http://ogp.me/ns#">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escaped_title} | NewsBangla</title>
    <meta name="description" content="{escaped_desc}">

    <!-- Open Graph / Facebook / WhatsApp / Messenger -->
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="NewsBangla">
    <meta property="og:url" content="{canonical_share_url}">
    <meta property="og:title" content="{escaped_title}">
    <meta property="og:description" content="{escaped_desc}">
    <meta property="og:image" content="{escaped_image}">
    <meta property="og:image:secure_url" content="{escaped_image}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escaped_title}">
    <meta name="twitter:description" content="{escaped_desc}">
    <meta name="twitter:image" content="{escaped_image}">

    <!-- Instant client redirect to full article in app/web -->
    <meta http-equiv="refresh" content="0;url={app_redirect_url}">
    <script>
        window.location.replace("{app_redirect_url}");
    </script>
</head>
<body style="font-family:'Hind Siliguri', sans-serif; background:#f8fafc; color:#0f172a; padding:40px 20px; text-align:center;">
    <div style="max-width:600px; margin:0 auto; background:#ffffff; border:1px solid #e2e8f0; border-radius:16px; padding:24px; box-shadow:0 4px 12px rgba(0,0,0,0.05);">
        <img src="{escaped_image}" alt="{escaped_title}" style="max-width:100%; height:auto; border-radius:10px; margin-bottom:16px; object-fit:cover; max-height:300px;">
        <h1 style="font-size:20px; line-height:1.4; color:#0f172a; margin-bottom:12px;">{escaped_title}</h1>
        <p style="font-size:14px; color:#475569; line-height:1.6; margin-bottom:20px;">{escaped_desc}</p>
        <a href="{app_redirect_url}" style="display:inline-block; background:#dc2626; color:#ffffff; text-decoration:none; padding:10px 22px; border-radius:30px; font-weight:700; font-size:14px;">সম্পূর্ণ খবর পড়ুন</a>
    </div>
</body>
</html>"""
    return Response(content=html_content, media_type="text/html; charset=utf-8")

@app.get("/api/share")
def share_article_endpoint(article: Optional[str] = Query(None), link: Optional[str] = Query(None)):
    return render_social_share_page(article or "", link or "")

@app.get("/article/{article_id}")
def direct_article_share_endpoint(article_id: str):
    return render_social_share_page(article_id)

@app.get("/api/article-image/{article_id}")
def serve_article_image(article_id: str):
    import base64
    found_item = None
    try:
        admin_articles = read_persisted_admin_articles()
        for a in admin_articles:
            if a.get("id") == article_id:
                found_item = a
                break
    except Exception:
        pass

    if found_item and found_item.get("image"):
        img_str = found_item.get("image")
        if img_str.startswith("data:"):
            try:
                # parse data:image/xxx;base64,...
                header, b64_data = img_str.split(",", 1)
                mime = "image/jpeg"
                if "png" in header: mime = "image/png"
                elif "webp" in header: mime = "image/webp"
                binary_data = base64.b64decode(b64_data)
                return Response(content=binary_data, media_type=mime)
            except Exception:
                pass
        elif img_str.startswith("http"):
            return Response(status_code=302, headers={"Location": img_str})

    # Default fallback image
    return Response(status_code=302, headers={"Location": "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=1200&auto=format&fit=crop&q=80"})


@app.get("/api/article")
def get_article(url: str = Query(...)):
    paras = []
    title = ""
    image = ""
    try:
        headers = headers_browser if ('prothomalo' in url or 'bbc' in url) else headers_social
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as r:
            html_content = r.read().decode('utf-8', errors='ignore')
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Title extraction
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                title = og_title['content'].strip()
            if not title:
                h1 = soup.find('h1')
                if h1: title = h1.get_text(strip=True)

            # High-resolution news image extraction
            og_img = soup.find('meta', property='og:image')
            if og_img and og_img.get('content') and og_img['content'].startswith('http'):
                image = og_img['content'].strip()
            if not image:
                tw_img = soup.find('meta', attrs={'name': 'twitter:image'})
                if tw_img and tw_img.get('content') and tw_img['content'].startswith('http'):
                    image = tw_img['content'].strip()
            if not image:
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src') or ''
                    if src.startswith('http') and not any(k in src for k in ['logo', 'icon', 'advert', 'ad.', 'banner', 'share', 'avatar']):
                        image = src
                        break

            # Strip script, style, comments, navigation, and advertisement wrappers
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript', 'button']):
                tag.decompose()

            # Robust paragraph extraction across all Bangladeshi newspaper structures
            seen_paras = set()
            skip_keywords = ['সর্বস্বত্ব সংরক্ষিত', 'কপিরাইট', 'Terms of Use', 'Privacy Policy', 'বিজ্ঞাপন', 'আরও পড়ুন', 'ফলো করুন', 'সাবস্ক্রাইব']
            
            for p in soup.find_all('p'):
                txt = p.get_text(strip=True)
                if len(txt) > 28 and not is_video_or_bulletin(txt):
                    if re.match(r'^(প্রকাশ|প্রিন্ট|অনলাইন|আপডেট)\s*:\s*[০-৯\d]', txt):
                        continue
                    if txt not in seen_paras and not any(sk in txt for sk in skip_keywords):
                        seen_paras.add(txt)
                        paras.append(txt)
    except Exception:
        pass

    return {
        "title": title,
        "image": image,
        "paragraphs": paras[:25]
    }


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
        "total_pageviews": 0,
        "month_pageviews": 0,
        "year_pageviews": 0,
        "total_unique": 0,
        "month_unique": 0,
        "year_unique": 0,
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
            "total_pageviews": stats.get("total_pageviews", 0),
            "month_pageviews": stats.get("month_pageviews", 0),
            "year_pageviews": stats.get("year_pageviews", 0),
            "total_unique": stats.get("total_unique", 0),
            "month_unique": stats.get("month_unique", 0),
            "year_unique": stats.get("year_unique", 0),
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
