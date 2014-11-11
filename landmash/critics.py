import requests

from . utils import RateLimited
from . models import Review
from bs4 import BeautifulSoup


class Critic():

    def __init__(self, critic_id):
        self.critic_id = critic_id

    def get_review(self, film):
        raise NotImplementedError


class RTCritic(Critic):

    def __init__(self, rt_api_key):
        Critic.__init__(self, "rotten_tomatoes")
        self.rt_url = "http://api.rottentomatoes.com/api/public/v1.0/movies.json"
        self.rt_api_key = rt_api_key

    @RateLimited(10)
    def get_review(self, film):
        r = requests.get(
            self.rt_url,
            params={'q': film.title,
                    'apikey': self.rt_api_key}).json()
        results = r['movies']

        if len(results):
            score = results[0]['ratings']['critics_score']
            url = results[0]['links']['alternate']

            # To counteract for negative, aka nonexistent scores
            if score < 0:
                score = 49

            return Review(
                critic=self.critic_id, rating=score, url=url, normalized=score)
        else:
            return None


class IMDBCritic(Critic):

    def __init__(self):
        Critic.__init__(self, "imdb")

    def run_search(self, film, exact=True):
        r = requests.get(
            "http://www.imdb.com/find",
            params={
                'q': film.title,
                's': 'tt',
                'ttype': 'ft',
                'exact': str(exact).lower()
            })
        parsed = False
        parsed_results = None
        text = r.text
        while(not parsed):
            parsed = True
            try:
                parsed_results = BeautifulSoup(text)
            except HTMLParseError as e:
                textlist = text.splitlines()
                del textlist[e.lineno - 1]
                text = '\n'.join(textlist)
                parsed = False
        results = parsed_results.find_all(
            'td',
            attrs={
                'class': 'result_text'})
        if len(results):
            return results
        else:
            return self.run_search(film, False)

    def get_review(self, film):
        results = self.run_search(film)
        if len(results):
            url = results[0].a['href'].split('?')[0]
            url = "http://www.imdb.com" + url
            r2 = requests.get(url)
            rating = BeautifulSoup(
                r2.text).find_all(
                    'div',
                    attrs={'class': 'titlePageSprite'})
            if rating:
                rating = float(rating[0].string.strip())
                return Review(
                    critic=self.critic_id, rating=rating, url=url, normalized=rating * 10)
            return None
        return None
