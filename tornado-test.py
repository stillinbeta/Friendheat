from datetime import datetime, timedelta
import threading
import time
import logging
from Queue import Queue

import tornado.ioloop
import tornado.web

class Limiter(object):
    def __init__(self, time_ms=2000, ioloop=None):
        self.lock = threading.Lock()
        self.limit = timedelta(milliseconds=time_ms)
        self.last_used = datetime.now()
    
        logging.debug("Didn't get lock, sleeping")
        self.callback_queue = Queue()

        if ioloop is None:
            ioloop = tornado.ioloop.IOLoop.instance()
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

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")
class LimitedHandler(tornado.web.RequestHandler):
    def initialize(self, limiter):
        self.limiter = limiter

    @tornado.web.asynchronous
    def get(self):
        self.limiter.wait(self._callback)

    def _callback(self):
        self.write("Got you back!")
        self.finish()

def application():
    limiter = Limiter()
    return tornado.web.Application([
        (r"/", MainHandler),
        (r"/limited", LimitedHandler, {'limiter': limiter})
    ])

if __name__ == "__main__":
    application().listen(8888)
    tornado.ioloop.IOLoop.instance().start()


