import os.path
from datetime import datetime, timedelta
import threading
from Queue import Queue
from urllib import quote, urlopen
import json

from tornado.ioloop import IOLoop
import tornado.web
import sqlite3dbm

GOOGLE_API_URL = 'http://maps.googleapis.com/maps/api/geocode/json?sensor=true&address={city}'

class Limiter(object):
    def __init__(self, time_ms=250, ioloop=None):
        self.lock = threading.Lock()
        self.limit = timedelta(milliseconds=time_ms)
        self.last_used = datetime.now()
    
        self.callback_queue = Queue()

        if ioloop is None:
            ioloop = IOLoop.instance()
        self.ioloop = ioloop

    def wait(self, callback):
        acquired = self.lock.acquire(False)
        if not acquired:
            self.callback_queue.put(lambda: self.wait(callback))
            return
        difference = datetime.now() - self.last_used 
        self.ioloop.add_timeout(max(self.limit - difference, timedelta(0)),
                                self.make_unlock(callback))
    def make_unlock(self, callback):
        def unlock():
            self.last_used = datetime.now()
            self.lock.release()
            self.ioloop.add_callback(callback)
            if not self.callback_queue.empty():
                self.ioloop.add_callback(self.callback_queue.get())
        return unlock

class GeocodeHandler(tornado.web.RequestHandler):
    def initialize(self, limiter, db):
        self.limiter = limiter
        self.db = db

    @tornado.web.asynchronous
    def get(self, city):
        try:
            self.write(self.db[city])
            self.finish()
        except KeyError:
            self.city = city
            self.limiter.wait(self._fetch_new)

    def _fetch_new(self):
        try:
            city = quote(self.city)
            response = urlopen(GOOGLE_API_URL.format(city=city)).read()
            decoded = json.loads(response)
        except IOError as e:
            raise tornado.web.HTTPError(504, 
                "Couldn't access Google API: " + str(e))
        except ValueError as e:
            raise tornado.web.HTTPError(502,
                "Couldn't decode API response: " + str(e))
        if not 'status' in decoded or decoded['status'] != 'OK':
            raise tornado.web.HTTPError(502, "Couldn't geocode request")

        location = decoded['results'][0]['geometry']['location']
        lat = location['lat']
        lng = location['lng']
        
        location_dict = {'lat': lat, 'long': lng}

        self.write(location_dict)
        self.finish()

        self.db[self.city] = location_dict
        self.db.sync()

def application():
    path = os.path.dirname(os.path.abspath(__file__))
    geocode_args = {'limiter': Limiter(),
                    'db': sqlite3dbm.sshelve.open(path + '/db.sqlite3')}
    static_args = {'path': path + "/static/",
                   'default_filename': 'index.html'}
       
    return tornado.web.Application([
        (r"/geocode/(.*)", GeocodeHandler, geocode_args),
        (r"/(.*)", tornado.web.StaticFileHandler, static_args),
    ])

if __name__ == "__main__":
    application().listen(10099)
    IOLoop.instance().start()
