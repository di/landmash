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
from landmash.models import *
from flask.ext.mongoengine import MongoEngine


def initialize_db(flask_app):
    MONGO_URL = os.environ.get('MONGOHQ_URL')
    flask_app.config["MONGODB_SETTINGS"] = {
        "DB": urlparse(MONGO_URL).path[1:],
        "host": MONGO_URL}
    return MongoEngine(flask_app)

app = Flask(__name__)
db = initialize_db(app)


@app.route("/")
def root():
    try:
        date = strftime("%A, %B %-d")
        market = Market.objects.get(name='Philadelphia')
        listing = LandmarkProxy().get_listing("08/01/14", market)
        films = enumerate(listing.showing)
        return render_template('index.html', films=films, date=date, market=market)

    except StatusError:
        return "Landmark Website Down!"


def sort_films(showing):
    if len(showing.film.reviews) > 0:
        total = sum([e.normalized for e in showing.film.reviews])
        return total/float(len(showing.film.reviews))
    return 0


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


class LandmarkProxy:

    def __init__(self):
        self.lm_url = "http://www.landmarktheatres.com/Market/MarketShowtimes.asp"

    def make_listing(self, date, market):
        listing = Listing(date=date, market=market).save()
        for f in self.make_request(date, market.name):
            location_href = "http://www.landmarktheatres.com" + f['location_href']
            location_name = f[ "location_name"]
            time_string = f["time_string"]
            showing = None

            try:
                film = Film.objects.get(title=f['title'])
                showing = Showing(location_href=location_href, location_name=location_name, time_string=time_string, film=film)
                listing.update(add_to_set__showing=showing)
            except Film.DoesNotExist:
                app.logger.debug("DNE: %s" % (f['title']))
                img = "http://www.landmarktheatres.com/Assets/Images/Films/%s.jpg" % (f['href'].split("=")[1])
                try:
                    film = Film(title=f['title'], href="http://www.landmarktheatres.com" + f['href'], img=img).save()

                    for critic in [RTProxy(), IMDBProxy()]:
                        review = critic.get_review(film)
                        film.update(add_to_set__reviews=critic.get_review(film))

                    showing = Showing(location_href=location_href, location_name=location_name, time_string=time_string, film=film)
                    listing.update(add_to_set__showing=showing)
                except:
                    pass
            except:
                pass
        listing.reload()

        # Sort the films
        listing.showing = sorted(
            listing.showing,
            key=lambda x: sort_films(
                x),
            reverse=True)

        listing.save()
        return listing

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

    def get_listing(self, date, market):
        try:
            return Listing.objects.get(date=date, market=market)
        except Listing.DoesNotExist:
            app.logger.debug("DNE: Listing for %s on %s" % (market.name, date))
            return self.make_listing(date=date, market=market)


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
            score = results[0]['ratings']['critics_score']
            url = results[0]['links']['alternate']

            # To counteract for negative, aka nonexistent scores
            if score < 0:
                score = 49

            return Review(critic=self.critic_id, rating=score, url=url, normalized=score)
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
        try:
            results = self.run_search(film)
            if len(results):
                url = results[0].a['href'].split('?')[0]
                url = "http://www.imdb.com" + url
                r2 = requests.get(url)
                rating = BeautifulSoup(
                    r2.text).find_all(
                        'div',
                        attrs={'class': 'titlePageSprite'})[0]
                if len(rating):
                    rating = float(rating[0].text.strip())
                    return Review(critic=self.critic_id, rating=rating, url=url, normalized=rating*10)
                return None
        except:
            pass
        return None
