import os.path
from urllib import quote, urlopen
import json


import bottle
from bottle_sqlite import SQLitePlugin

dirname = os.path.dirname(os.path.abspath(__file__))

bottle.install(SQLitePlugin(dbfile=dirname + '/db.sqlite3'))


GOOGLE_API_URL = 'http://maps.googleapis.com/maps/api/geocode/json?sensor=true&address={city}'


@bottle.route('/geocode/<city>')
def geocode(city, db):
    row = db.execute('SELECT lat, long FROM geocode WHERE city = ?',
                     (city,)).fetchone()
    if row:
        return dict(row)

    try:
        response = urlopen(GOOGLE_API_URL.format(city=quote(city))).read()
        decoded = json.loads(response)
    except IOError as e:
        bottle.abort(504, "Couldn't access Google API: " + str(e))
    except ValueError as e:
        bottle.abort(502, "Couldn't decode API response: " + str(e))

    if not 'status' in decoded or decoded['status'] != 'OK':
        bottle.abort(502, "Coludn't geocode request")

    location = decoded['results'][0]['geometry']['location']
    lat = location['lat']
    lng = location['lng']

    row = db.execute('INSERT INTO geocode (city, lat, long) VALUES (?, ?, ?)',
                     (city, lat, lng,))
    return {'lat': lat, 'long': lng}

@bottle.route('/')
def index():
    return bottle.static_file('index.html', root=dirname)

@bottle.route('/channel')
def index():
    return bottle.static_file('channel.html', root=dirname)

if __name__ == "__main__":
    bottle.run(server="gunicorn", bind="unix:/tmp/gunicorn-friendheat.sock")
