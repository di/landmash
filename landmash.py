#!/usr/bin/python

import requests
import time
import ConfigParser
from bs4 import BeautifulSoup


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


def get_current_films(date, market='Philadelphia'):
    r = requests.post(
        lm_url,
        params={
            'market': market},
        data={
            'ddtshow': date})
    links = BeautifulSoup(r.text).find_all('a', href=True)
    return [x.string for x in links if x['href'].startswith('/Films')]


@RateLimited(10)
def get_rt_rating(title):
    r = requests.get(rt_url, params={'q': title, 'apikey': rt_api_key}).json()
    sort = sorted(r['movies'], key=lambda x: int(
        x['year'] if x['year'] else 0), reverse=True)
    return sort[0]['ratings']['critics_score']


def get_imdb_rating(title):
    r = requests.get(imdb_url, params={'q': title, 'limit': 10}).json()
    sort = sorted(r, key=lambda x: int(
        x['year'] if x['year'] else 0), reverse=True)
    try:
        return sort[0]['rating']
    except KeyError:
        return None


def load_config(filename):
    config = ConfigParser.RawConfigParser()
    try:
        with open(filename):
            pass
    except IOError:
        print('File `%s` not found.' % (filename))
        sys.exit(0)
    config.read(filename)
    return config

lm_url = "http://www.landmarktheatres.com/Market/MarketShowtimes.asp"
rt_url = "http://api.rottentomatoes.com/api/public/v1.0/movies.json"
imdb_url = "http://imdbapi.org"
config = load_config('landmash.cfg')
rt_api_key = config.get('rotten_tomatoes', 'api_key')
films = get_current_films('5/18/2013')
print zip(films, [get_rt_rating(f) for f in films], [get_imdb_rating(f) for f in films])
