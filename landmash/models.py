from mongoengine import *

class Review(EmbeddedDocument):
    url = StringField(required=True)
    rating = IntField(required=True)
    normalized = IntField(required=True)
    critic = StringField(required=True)

class Film(Document):
    title = StringField(required=True)
    href = StringField(required=True)
    img = StringField(required=True)
    reviews = ListField(EmbeddedDocumentField(Review))

class Market(Document):
    name = StringField(required=True)

class Showing(EmbeddedDocument):
    location_href = StringField(required=True)
    location_name = StringField(required=True)
    time_string = StringField(required=True)
    film = ReferenceField(Film, required=True)

class Listing(Document):
    date = StringField(required=True) # TODO: Make this a date
    market = ReferenceField(Market, required=True)
    showing = ListField(EmbeddedDocumentField(Showing))
