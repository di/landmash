#!/usr/bin/python

from HTMLParser import HTMLParseError
import requests
import time
import os
import json
from bs4 import BeautifulSoup
from flask import Flask, request, render_template
from urlparse import urlparse
from pymongo import Connection
from time import strftime

MONGO_URL = os.environ.get('MONGOHQ_URL')

if MONGO_URL:
    connection = Connection(MONGO_URL)
    db = connection[urlparse(MONGO_URL).path[1:]]
else:
    sys.exit("MongoDB URL not found, exiting")


app = Flask(__name__)


@app.route("/")
def root():
    try:
        landmark_films = LandmarkProxy().get_current_films(strftime("%x"))
        critics = [RTProxy(), IMDBProxy()]
        films = [Film(x, critics) for x in landmark_films]
        best = sorted(films, key=lambda x: sort_films(x), reverse=True)
        return render_template('index.html', films=enumerate(best), date=strftime("%A, %B %-d"))

    except StatusError:
        return "Landmark Website Down!"


def sort_films(x):
    return sum([e.normalized for e in x.reviews])/float(len(x.reviews))


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

    def __init__(self, data, critics):
        self.title = data['title']
        self.href = "http://www.landmarktheatres.com" + data['href']
        self.img = "http://www.landmarktheatres.com/Assets/Images/Films/%s.jpg" % (
            data['href'].split("=")[1])
        self.location_name = data['location_name']
        self.location_href = data['location_href']
        self.time_string = data['time_string']
        self.reviews = []

        cache = db.films.find_one({"title": self.title})
        if cache is None:
            app.logger.debug("Adding " + self.title + " to DB.")

            for critic in critics:
                review = critic.get_review(self)
                self.reviews.append(review)

            db.films.insert(self.to_dict())
        else:
            self.reviews = [Review(
                            x['critic_id'],
                            x['rating'],
                            x['url'],
                            x['normalized']) for x in cache['reviews']]

    def to_dict(self):
        ret = self.__dict__
        ret['reviews'] = [x.__dict__ for x in self.reviews]
        return ret


class LandmarkProxy:

    def __init__(self):
        self.lm_url = "http://www.landmarktheatres.com/Market/MarketShowtimes.asp"

    def get_current_films(self, date, market='Philadelphia'):
        listing = db.listings.find_one({"date": date, "market": market})

        if listing is None:
            films = self.make_request(date, market)
            db.listings.insert({
                "date": date,
                "market": market,
                "films": films
            })
            return films
        else:
            return listing['films']

    def make_request(self, date, market):
        ret = dict()
        ret["date"] = date
        ret["markets"] = [market]
        r = requests.post(
            self.lm_url,
            params={
                'market': market},
            data={
                'ddtshow': date})
        if r.status_code != 200:
            raise StatusError(r.status_code)

        locations = BeautifulSoup(
            r.text).find_all('ul',
                             id='navMainST')
        return [{"title": f.a.string,
                 "href": f.a['href'],
                 "location_name": l.li.a.a.string,
                 "location_href": l.li.a.a['href'],
                 "time_string": f.span.string}
                for l in locations for f in l.find_all('li', id=None)]


class Review():

    def __init__(self, critic_id, rating, url, normalized):
        self.critic_id = critic_id
        self.rating = rating
        self.url = url
        self.normalized = normalized


class Critic():

    def __init__(self, critic_id):
        self.critic_id = critic_id

    def get_review(self, film):
        raise NotImplementedError


class RTProxy(Critic):

    def __init__(self):
        Critic.__init__(self, "rotten_tomatoes")
        self.rt_url = "http://api.rottentomatoes.com/api/public/v1.0/movies.json"
        self.rt_api_key = os.environ.get('RT_API_KEY')

    @RateLimited(10)
    def get_review(self, film):
        r = requests.get(
            self.rt_url,
            params={'q': film.title,
                    'apikey': self.rt_api_key}).json()
        results = r['movies']

        if len(results):
            return Review(self.critic_id, results[0]['ratings']['critics_score'], results[0]['links']['alternate'], results[0]['ratings']['critics_score'])
        else:
            return None


class IMDBProxy(Critic):

    def __init__(self):
        Critic.__init__(self, "imbd")

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
                    attrs={'class': 'titlePageSprite'})[0].text.strip()
            return Review(self.critic_id, float(rating), url, float(rating)*10)

        else:
            return None
