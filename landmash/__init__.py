#!/usr/bin/python

from datetime import datetime
from HTMLParser import HTMLParseError
import requests
import time
import os
from bs4 import BeautifulSoup
from flask import Flask, request, render_template

app = Flask(__name__)


@app.route("/")
def root():
    try:
        d = datetime.today()
        date = "%d/%d/%d" % (d.month, d.day, d.year)
        films = LandmarkProxy().get_current_films(date)

        critics = [RTProxy(), IMDBProxy()]

        for i in xrange(len(films) - 1, -1, -1):
            film = films[i]
            for critic in critics:
                review = critic.get_review(film)
                if review is None:
                    films.remove(film)
                    break
                else:
                    film.reviews.append(review)

        best = sorted(films, key=lambda x: sort_films(x), reverse=True)
        return render_template('index.html', films=enumerate(best), date=date)

    except StatusError:
        return "Landmark Website Down!"


def sort_films(x):
    return sum([e['normalized'] for e in x.reviews])/float(len(x.reviews))


def RateLimited(maxPerSecond):
    minInterval = 1.0 / float(maxPerSecond)

    def decorate(func):
        lastTimeCalled = [0.0]

        def rateLimitedFunction(*args, **kargs):
            elapsed = time.clock() - lastTimeCalled[0]
            leftToWait = minInterval - elapsed
            if leftToWait > 0:
                time.sleep(leftToWait)
            ret = func(*args, **kargs)
            lastTimeCalled[0] = time.clock()
            return ret
        return rateLimitedFunction
    return decorate


class StatusError(Exception):

    def __init__(self, status_code):
        self.status_code = status_code

    def __str__(self):
        return repr(self.status_code)


class Film:

    def __init__(self, title, landmark_link):
        self.reviews = []
        self.title = title
        self.href = "http://www.landmarktheatres.com" + landmark_link
        self.img = "http://www.landmarktheatres.com/Assets/Images/Films/%s.jpg" % (
            landmark_link.split("=")[1])

    def __str__(self):
        return self.title

    def __repr__(self):
        return self.__str__()


class LandmarkProxy:

    def __init__(self):
        self.lm_url = "http://www.landmarktheatres.com/Market/MarketShowtimes.asp"

    def get_current_films(self, date, market='Philadelphia'):
        r = requests.post(
            self.lm_url,
            params={
                'market': market},
            data={
                'ddtshow': date})
        if r.status_code != 200:
            raise StatusError(r.status_code)
        links = BeautifulSoup(r.text).find_all('a', href=True)
        return [Film(x.string, x['href']) for x in links if x['href'].startswith('/Films')]


class Critic:

    def __init__(self):
        self.films = dict()

    def get_review(self, film):
        raise NotImplementedError


class RTProxy(Critic):

    def __init__(self):
        Critic.__init__(self)
        self.rt_url = "http://api.rottentomatoes.com/api/public/v1.0/movies.json"
        self.rt_api_key = os.environ.get('RT_API_KEY')

    @RateLimited(10)
    def get_review(self, film):
        if film.title not in self.films.keys():
            r = requests.get(
                self.rt_url,
                params={'q': film.title,
                        'apikey': self.rt_api_key}).json()
            results = r['movies']
            if len(results):
                self.films[film.title] = {
                    'rating': results[0]['ratings']['critics_score'],
                    'url': results[0]['links']['alternate'],
                    'normalized': results[0]['ratings']['critics_score']
                }
            else:
                self.films[film.title] = None
        return self.films[film.title]


class IMDBProxy(Critic):

    def __init__(self):
        Critic.__init__(self)

    def get_review(self, film):
        if film.title not in self.films.keys():
            f = dict()
            r = requests.get(
                "http://www.imdb.com/find",
                params={
                    'q': film.title,
                    's': 'tt',
                    'ttype': 'ft',
                    'exact': 'true'
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
                url = results[0].a['href'].split('?')[0]
                url = "http://www.imdb.com" + url
                r2 = requests.get(url)
                rating = BeautifulSoup(
                    r2.text).find_all(
                        'div',
                        attrs={'class': 'titlePageSprite'})[0].text.strip()
                self.films[film.title] = {
                    'rating': float(rating),
                    'url': url,
                    'normalized': float(rating)*10
                }
            else:
                self.films[film.title] = None
        return self.films[film.title]
