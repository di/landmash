#!/usr/bin/python

import os
from time import strftime
from flask import Flask, render_template, abort
from urlparse import urlparse
from pymongo import Connection
from landmash.models import Market, Film
from flask.ext.mongoengine import MongoEngine
from .critics import RTCritic, IMDBCritic
from .errors import StatusError
from .utils import rating_filter
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
        listing = landmark.get_listing(strftime("%x"), market)
        showing = enumerate(listing.showing)
        return render_template(
            'index.html', showing=showing, date=strftime("%A, %B %-d"), market=market)

    except StatusError:
        return "Landmark Website Down!"

@app.route("/<lm_id>/")
def film(lm_id):
    try:
        return render_template('film.html', film=Film.get(lm_id=lm_id))
    except Film.DoesNotExist:
        return abort(404)
