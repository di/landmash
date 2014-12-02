#!/usr/bin/python

import os
from flask import Flask, render_template, abort
from urlparse import urlparse
from pymongo import Connection
from landmash.models import Market, Film, Showing
from flask.ext.mongoengine import MongoEngine
from .critics import RTCritic, IMDBCritic
from .errors import StatusError
from .utils import rating_filter, db_date, human_date
from .landmark import LandmarkProxy


def initialize_db(flask_app):
    MONGO_URL = os.environ.get('MONGOHQ_URL')
    flask_app.config["MONGODB_SETTINGS"] = {
        "DB": urlparse(MONGO_URL).path[1:],
        "host": MONGO_URL}
    return MongoEngine(flask_app)

app = Flask(__name__)
db = initialize_db(app)
app.force_fetch = os.environ.get("FORCE_FETCH", False)
app.jinja_env.filters["rating"] = rating_filter


@app.route("/")
def root():
    try:
        market = Market.get(name='Philadelphia')
        landmark = LandmarkProxy()
        landmark.critics = [
            RTCritic(os.environ.get('RT_API_KEY')),
            IMDBCritic()]
        listing = landmark.get_listing(db_date(), market)
        showing = enumerate(listing.showing)
        return render_template(
            'index.html', showing=showing, date=human_date(), market=market)

    except StatusError:
        return "Landmark Website Down!"

@app.route("/<lm_id>/")
def film(lm_id):
    try:
        film = Film.get(lm_id=lm_id)
        market = Market.get(name='Philadelphia')
        showings = Showing.objects(film=film, date=db_date(), market=market)
        return render_template('film.html', film=film, market=market, showings=showings, date=human_date())
    except Film.DoesNotExist:
        return abort(404)
