#!/usr/bin/python

from datetime import datetime
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

        rt = RTProxy()
        imdb = IMDBProxy()

        for i in xrange(len(films) - 1, -1, -1):
            f = films[i]
            rt_film = rt.get_film(f)
            imdb_film = imdb.get_film(f)

            if rt_film is not None and imdb_film is not None:
                f.rt = rt.get_rating(rt_film)
                f.rt_url = rt.get_url(rt_film)

                f.imdb = imdb.get_rating(imdb_film)
                f.imdb_url = imdb.get_url(imdb_film)
            else:
                films.remove(f)

        best = sorted(films, key=lambda x: sort_films(x), reverse=True)
        return render_template('index.html', films=enumerate(best), date=date)

    except StatusError:
        return "Landmark Website Down!"


def sort_films(x):
    if x.imdb > 0:
        return (x.rt + x.imdb*10)/2
    else:
        return (x.rt + x.rt-20)/2


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
        self.title = title
        self.href = "http://www.landmarktheatres.com" + landmark_link
        self.img = "http://www.landmarktheatres.com/Assets/Images/Films/%s.jpg" % (
            landmark_link.split("=")[1])

    def __str__(self):
        return self.title

    def __repr__(self):
        return self.__str__()


class LandmarkProxy:

    def __init__(
            self, lm_url="http://www.landmarktheatres.com/Market/MarketShowtimes.asp"):
        self.lm_url = lm_url

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


class RTProxy:

    def __init__(
            self, rt_url="http://api.rottentomatoes.com/api/public/v1.0/movies.json"):
        self.rt_url = rt_url
        self.rt_api_key = os.environ.get('RT_API_KEY')
        self.films = dict()

    @RateLimited(10)
    def get_film(self, film):
        if film.title not in self.films.keys():
            r = requests.get(
                self.rt_url,
                params={'q': film.title,
                        'apikey': self.rt_api_key}).json()
            sort = sorted(r['movies'], key=lambda x: int(
                x['year'] if x['year'] else 0), reverse=True)
            try:
                self.films[film.title] = sort[0]
            except IndexError:
                return None
        return self.films[film.title]

    def get_rating(self, film):
        return film['ratings']['critics_score']

    def get_url(self, film):
        return film['links']['alternate']


class IMDBProxy:

    def __init__(self):
        self.films = dict()

    def get_film(self, film):
        if film.title not in self.films.keys():
            f = dict()
            r = requests.get(
                "http://www.imdb.com/find",
                params={
                    'q': film.title,
                    's': 'tt',
                    'exact': 'true'
                })
            url = "http://www.imdb.com" + BeautifulSoup(
                r.text).find_all(
                    'td',
                    attrs={
                        'class': 'result_text'})[
                            0].a[
                    'href'].split(
                        '?')[
                            0]
            f['imdbRating'] = float(
                BeautifulSoup(requests.get(url).text).find_all('div',
                                                               attrs={'class': 'titlePageSprite'})[0].text.strip())
            f['imdbURL'] = url
            self.films[film.title] = f
        return self.films[film.title]

    def get_rating(self, film):
        return film['imdbRating']

    def get_url(self, film):
        return film['imdbURL']
