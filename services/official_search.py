import re, httpx
from bs4 import BeautifulSoup
from urllib.parse import unquote, parse_qs, urlparse, urljoin

ALLOWED_DOMAINS=(
    'gov.in','nic.in','rajasthan.gov.in','rpsc.rajasthan.gov.in',
    'rssb.rajasthan.gov.in','rajeduboard.rajasthan.gov.in',
    'recruitment.rajasthan.gov.in','ssc.gov.in','upsc.gov.in',
    'ctet.nic.in','rrbcdg.gov.in','ibps.in'
)
UA='Mozilla/5.0 (Android 14; ExamSaathiAI/1.1)'

def allowed(url:str)->bool:
    try:
        host=urlparse(url).netloc.lower().split(':')[0]
        return any(host==d or host.endswith('.'+d) for d in ALLOWED_DOMAINS)
    except Exception: return False

def is_pdf(url:str)->bool:
    try:
        path=urlparse(url).path.lower()
        return path.endswith('.pdf') or '.pdf/' in path
    except Exception: return False

def unwrap(href:str)->str:
    try:
        if 'uddg=' in href:
            return unquote(parse_qs(urlparse(href).query).get('uddg',[''])[0])
    except Exception: pass
    return href

def clean_title(text):
    return re.sub(r'\s+',' ',text or '').strip()[:140]

async def search_web(query, limit=10):
    out=[]; seen=set()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={'User-Agent':UA}) as client:
            r=await client.get('https://html.duckduckgo.com/html/',params={'q':query})
            r.raise_for_status()
            soup=BeautifulSoup(r.text,'html.parser')
            for a in soup.select('a.result__a[href]'):
                href=unwrap(a.get('href','')).strip()
                if not href.startswith('http') or not allowed(href): continue
                key=href.split('#')[0]
                if key in seen: continue
                seen.add(key)
                parent=a.find_parent('div',class_='result')
                sn=parent.select_one('.result__snippet') if parent else None
                out.append({'title':clean_title(a.get_text(' ',strip=True)),'url':href,
                            'snippet':clean_title(sn.get_text(' ',strip=True) if sn else ''),'pdf':is_pdf(href)})
                if len(out)>=limit: break
    except Exception as exc:
        print('official search warning:',exc)
    return out

async def extract_pdfs_from_pages(pages, exam, kind, limit=10):
    """Open official result pages and extract their real PDF hrefs.
    This fixes the old behaviour where the bot returned the official homepage/archive page.
    """
    found=[]; seen=set()
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={'User-Agent':UA}) as client:
        for page in pages[:8]:
            if is_pdf(page['url']):
                if page['url'] not in seen:
                    seen.add(page['url']); found.append(page)
                continue
            try:
                r=await client.get(page['url'])
                if r.status_code>=400 or 'text/html' not in r.headers.get('content-type','').lower(): continue
                soup=BeautifulSoup(r.text,'html.parser')
                for a in soup.select('a[href]'):
                    href=urljoin(str(r.url),a.get('href','')).strip()
                    if not allowed(href) or not is_pdf(href): continue
                    if href in seen: continue
                    title=clean_title(a.get_text(' ',strip=True)) or clean_title(page['title'])
                    context=(title+' '+page['title']).lower()
                    # For PYQ, prefer question paper/answer-key links; for syllabus prefer syllabus/notification.
                    score=0
                    words=('question paper','previous','pyq','old paper','answer key','प्रश्न पत्र','paper') if kind=='pyq' else ('syllabus','पाठ्यक्रम','scheme','notification','advertisement')
                    for w in words:
                        if w in context: score+=10
                    seen.add(href)
                    found.append({'title':title,'url':href,'snippet':page.get('snippet',''),'pdf':True,'score':score})
                    if len(found)>=limit*2: break
            except Exception as exc:
                print('pdf extraction warning:',exc)
    found.sort(key=lambda x:x.get('score',0),reverse=True)
    return found[:limit]

async def search_exam(exam, kind):
    if kind=='syllabus':
        queries=[
            f'"{exam}" syllabus filetype:pdf site:rpsc.rajasthan.gov.in',
            f'"{exam}" syllabus filetype:pdf site:rssb.rajasthan.gov.in',
            f'"{exam}" syllabus filetype:pdf site:rajeduboard.rajasthan.gov.in',
            f'"{exam}" पाठ्यक्रम filetype:pdf site:gov.in',
            f'"{exam}" scheme syllabus filetype:pdf site:gov.in',
        ]
    else:
        queries=[
            f'"{exam}" question paper filetype:pdf site:rpsc.rajasthan.gov.in',
            f'"{exam}" previous paper filetype:pdf site:rssb.rajasthan.gov.in',
            f'"{exam}" question paper filetype:pdf site:rajeduboard.rajasthan.gov.in',
            f'"{exam}" PYQ filetype:pdf site:gov.in',
            f'"{exam}" answer key filetype:pdf site:gov.in',
        ]
    raw=[]; seen=set()
    for q in queries:
        for x in await search_web(q,10):
            if x['url'] not in seen:
                seen.add(x['url']); raw.append(x)
    direct=[x for x in raw if x['pdf']]
    if direct:
        return direct[:10]
    # Search result may point to an official archive/page. Extract its actual PDF links.
    extracted=await extract_pdfs_from_pages(raw,exam,kind,10)
    return extracted
