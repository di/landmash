import requests
from bs4 import BeautifulSoup
from .models import Listing, Showing, Film
from flask import current_app as app


class LandmarkProxy:

    def __init__(self):
        self.base_url = "http://www.landmarktheatres.com"
        self.lm_url = self.base_url + "/Market/MarketShowtimes.asp"
        self.critics = []

    def sort_films(self, showing):
        if len(showing.film.reviews) > 0:
            total = sum([e.normalized for e in showing.film.reviews])
            return total / float(len(showing.film.reviews))
        return 0

    def make_listing(self, date, market):
        listing = Listing(date=date, market=market).save()
        for f in self.make_request(date, market.name):
            location_href = self.base_url + f['location_href']
            location_name = f["location_name"]
            time_string = f["time_string"]
            showing = None

            try:
                film = Film.get(title=f['title'])
            except Film.DoesNotExist:
                img = self.base_url + "/Assets/Images/Films/%s.jpg" % (
                    f['href'].split("=")[1])
                film = Film(
                    title=f['title'],
                    href=self.base_url + f['href'],
                    lm_id=f['href'].split("=")[1],
                    img=img).save()

                for critic in self.critics:
                    review = critic.get_review(film)
                    if review:
                        film.update(
                            add_to_set__reviews=critic.get_review(film))

            showing = Showing(
                location_href=location_href,
                location_name=location_name,
                time_string=time_string,
                film=film)

            # Add the c_setting, if it exists
            if "c_setting" in f:
                showing.c_setting = f["c_setting"]

            listing.update(add_to_set__showing=showing)
        listing.reload()

        # Sort the films
        listing.showing = sorted(
            listing.showing,
            key=lambda x: self.sort_films(x),
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

        locations = BeautifulSoup(r.text).find_all('ul', id='navMainST')
        ret = []
        for l in locations:
            for f in l.find_all('li', id=None):
                fm = {"title": f.a.string,
                 "href": f.a['href'],
                 "location_name": l.li.a.a.string,
                 "location_href": l.li.a.a['href'],
                 "time_string": f.find('span', class_='shwTime').string}

                c_setting = f.find('span', class_='cSetting')
                if c_setting != None:
                    fm["c_setting"] = c_setting.string
                ret.append(fm)
        return ret

    def get_listing(self, date, market):
        try:
            return Listing.get(date=date, market=market)
        except Listing.DoesNotExist:
            return self.make_listing(date=date, market=market)
