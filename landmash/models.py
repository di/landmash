from mongoengine import *
from flask import current_app as app


@classmethod
def get(cls, **kwargs):
    ''' Default wrapper for Document.objects.get '''
    if app.force_fetch:
        raise cls.DoesNotExist
    return cls.objects.get(**kwargs)

Document.get = get


class Review(EmbeddedDocument):
    url = StringField(required=True)
    rating = FloatField(required=True)
    normalized = IntField(required=True)
    critic = StringField(required=True)


class Film(Document):
    title = StringField(required=True, unique=True)
    href = StringField(required=True, unique=True)
    lm_id = StringField(required=True, unique=True)
    img = StringField(required=True)
    reviews = ListField(EmbeddedDocumentField(Review))


class Market(Document):
    name = StringField(required=True)

    @classmethod
    def get(cls, **kwargs):
        ''' Can't get a missing market, so override default method here.'''
        return cls.objects.get(**kwargs)


class Showing(Document):
    location_href = StringField(required=True)
    location_name = StringField(required=True)
    time_string = StringField(required=True)
    c_setting = StringField()
    film = ReferenceField(Film, required=True)
    date = StringField(required=True, unique_with="film")


class Listing(Document):
    date = StringField(required=True, unique_with="market")  # TODO: Make this a date
    market = ReferenceField(Market, required=True)
    showing = ListField(ReferenceField(Showing))
