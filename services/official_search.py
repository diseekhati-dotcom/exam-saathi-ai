import re, httpx
from bs4 import BeautifulSoup
from urllib.parse import unquote

ALLOWED=('gov.in','nic.in','rajasthan.gov.in','rpsc.rajasthan.gov.in','rssb.rajasthan.gov.in','rajeduboard.rajasthan.gov.in','ssc.gov.in','upsc.gov.in','ctet.nic.in','rrbcdg.gov.in','ibps.in')

def allowed(url):
    u=url.lower()
    return any(d in u for d in ALLOWED)

def unwrap(href):
    if 'uddg=' in href:
        from urllib.parse import parse_qs,urlparse
        try: return unquote(parse_qs(urlparse(href).query).get('uddg',[''])[0])
        except Exception: return href
    return href

async def search_official(query,limit=8):
    url='https://html.duckduckgo.com/html/'
    headers={'User-Agent':'Mozilla/5.0 (Exam Saathi AI)'}
    results=[]
    seen=set()
    try:
        async with httpx.AsyncClient(timeout=10,follow_redirects=True,headers=headers) as client:
            r=await client.get(url,params={'q':query})
            soup=BeautifulSoup(r.text,'html.parser')
            for a in soup.select('a.result__a[href]'):
                href=unwrap(a.get('href','')); title=a.get_text(' ',strip=True)
                if not href.startswith('http') or not allowed(href) or href in seen: continue
                parent=a.find_parent('div',class_='result')
                snippet=''
                if parent:
                    s=parent.select_one('.result__snippet')
                    snippet=s.get_text(' ',strip=True) if s else ''
                seen.add(href)
                results.append({'title':title[:90],'url':href,'snippet':snippet[:160],'pdf':href.lower().split('?')[0].endswith('.pdf')})
                if len(results)>=limit: break
    except Exception as exc:
        print('official search warning:',exc)
    return results

async def search_exam(exam,kind):
    words='syllabus scheme notification PDF' if kind=='syllabus' else 'previous question paper PYQ answer key PDF'
    queries=[f'"{exam}" {words} site:rajasthan.gov.in',f'"{exam}" {words} site:rpsc.rajasthan.gov.in',f'"{exam}" {words} site:rssb.rajasthan.gov.in',f'"{exam}" {words} site:gov.in']
    out=[]; seen=set()
    for q in queries:
        for x in await search_official(q,8):
            if x['url'] in seen: continue
            seen.add(x['url']); out.append(x)
            if len(out)>=10: return out
    return out
