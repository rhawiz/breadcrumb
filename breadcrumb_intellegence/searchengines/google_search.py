from time import sleep

import requests
from bs4 import BeautifulSoup

from breadcrumb_intellegence.utils import is_ascii

GOOGLE_WEB_SEARCH_URL = "https://www.google.com/search?q={}&start={}&num={}"

"""
    Google Image Search URL usage
    Example URL: https://www.google.co.uk/search?q=SEARCH_QUERY&safe=off&nfpr=1&tbs=cdr:1,cd_min:01/03/2016,cd_max:10/03/2016,itp:face&tbm=isch
    ----Relevant Parameters----
    q: Search Query
    tbs: Filters
        cdr:1 : Add time range filter
            cd_min: Min Date
            cd_max: Max Date
        itp: Search Type
            face: Face Photos
            photo: Photograps
            clipart: Drawings
            linedrawing: Line drawings
            animated: GIFS

"""
GOOGLE_IMAGE_SEARCH_URL = "https://www.google.co.uk/search?tbm=isch&q=SEARCH_QUERY&safe=off&nfpr=1&tbs=cdr:1,cd_min:{MIN_DATE},cd_max:10/03/2016,itp:{}"


class GoogleWebSearch:
    def __init__(self, query, wait=1, start=0, num=100, sentiment_analyser=None):
        self.query = query
        self.wait = wait
        self.start = start
        self.num = num
        self.sentiment_analyser = sentiment_analyser

    def search(self, pages=1):
        results = []
        for i in range(0, pages):
            sleep(self.wait)
            query = self.query
            start = self.start + (i * self.num)
            num = self.num
            url = GOOGLE_WEB_SEARCH_URL.format(query, start, num)
            html_response = requests.get(url).text
            content = self._scrape_page(html_response)
            if not len(content):
                break
            results += content
        return results

    def _scrape_page(self, html):

        soup = BeautifulSoup(html, "html.parser")
        raw_content = soup.find_all('div', attrs={'class': 'g'})
        results = []
        for content in raw_content:

            link_tag = content.find('a')
            link_url = link_tag.get('href')[7:]
            link_text = link_tag.get_text()
            short_text = content.find('span', attrs={'class': 'st'})

            if short_text is None:
                continue

            short_text = short_text.get_text().encode('ascii', errors='ignore')

            try:
                print link_text, link_url, short_text[0:10]
            except Exception:
                pass
            content_analysis = None

            content = {
                'url': link_url,
                'url_text': link_text,
                'text': short_text
            }

            if self.sentiment_analyser:
                try:
                    content_analysis = self.sentiment_analyser(short_text)
                    content['analysis'] = content_analysis
                except Exception:
                    pass

            results.append(content)

        return results
