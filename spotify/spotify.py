import os
import sys
import json
import datetime
from functools import wraps
from base64 import b64encode
try:
    # Python 3
    from urllib.parse import quote, urlencode, urljoin, parse_qs
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    basestring = str
except ImportError:
    # Python 2
    from urlparse import urljoin, parse_qs
    from urllib import urlencode, quote
    from urllib2 import urlopen, Request, HTTPError

VALID_SCOPES = [
    'ugc-image-upload', 'user-read-recently-played', 'user-top-read',
    'user-read-playback-position', 'user-read-playback-state',
    'user-modify-playback-state', 'user-read-currently-playing',
    'app-remote-control', 'streaming', 'playlist-modify-public',
    'playlist-modify-private', 'playlist-read-private',
    'playlist-read-collaborative', 'user-follow-modify', 'user-follow-read',
    'user-library-modify', 'user-library-read', 'user-read-email',
    'user-read-private'
]
OAUTH2_URL = 'https://accounts.spotify.com/authorize/'
TOKEN_URL = 'https://accounts.spotify.com/api/token/'
API_BASE = 'https://api.spotify.com/v1/'

def chunked(xs, n):
    """Yields successive n-sized chunks from xs"""
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def kwargs_required(*xs):
    def _wrapper(method):
        @wraps(method)
        def _inner(self, *args, **kwargs):
            for x in xs:
                if x not in kwargs or kwargs[x] is None:
                    raise SpotifyException(
                        'missing required parameter: %s' % x
                    )
            return method(self, *args, **kwargs)
        return _inner
    return _wrapper

def csv_kwargs(*xs):
    def _wrapper(method):
        @wraps(method)
        def _inner(self, *args, **kwargs):
            for x in xs:
                if x in kwargs and isinstance(kwargs[x], list):
                    kwargs[x] = ','.join(kwargs[x])
            return method(self, *args, **kwargs)
        return _inner
    return _wrapper

def _expect_status(expected, resp):
    if resp.code != expected:
        raise SpotifyException(
            "invalid status code - %d (expected: %s) - %s" % (
                resp.code, expected, resp.read()
            )
        )

class SpotifyException(Exception):
    def __init__(self, *args, **kwargs):
        super(SpotifyException, self).__init__(*args, **kwargs)
        self.__suppress_context__ = True

class MethodRequest(Request, object):
    def __init__(self, method, *args, **kwargs):
        self._method = method
        super(MethodRequest, self).__init__(*args, **kwargs)

    def get_method(self):
        return self._method

class BaseRequest(object):
    """Basically a ghetto version of `requests.Request`.

    Adds some syntactic sugar to make constructing urllib requests easier.
    Call `prepare()` to actually construct the request object to be used
    in calls to `urlopen()`.
    """
    def __init__(
        self, method, url, params=None, data=None,
        json=None, headers=None, auth=None, _file=None
    ):
        self.method = method
        self.url = url
        self.params = params or {}
        self.json = json or {}
        self.data = data or {}
        self.headers = headers or {}
        self.auth = auth
        self.file_contents = None
        if _file is not None:
            self.file_contents = _file.read()

    def prepare(self):
        """Construct necessary data and return an instance of urllib's
        `Request` class.
        """
        _urllib_kwargs = {}
        _url_actual = self.url
        if self.file_contents:
            _urllib_kwargs['data'] = b64encode(self.file_contents)
            self.headers['Content-Type'] = 'image/jpeg'
        elif self.json:
            _urllib_kwargs['data'] = json.dumps(self.json).encode()
            self.headers['Content-Type'] = 'application/json'
        elif self.data:
            _urllib_kwargs['data'] = urlencode(self.data).encode()
        if self.params:
            _params_actual = self.params
            parts = _url_actual.split("?")
            if len(parts) > 2 or len(parts) < 1:
                raise SpotifyException("malformed URL")
            if len(parts) == 2:
                # append passed params to existing url query string
                current_params = parse_qs(parts[-1])
                # assume we don't have repeat parameters
                _params_actual.update({
                    k: v[0] for k,v in current_params.items()
                })
            _url_actual = '%s?%s' % (parts[0], urlencode(_params_actual))
        if self.auth:
            self.headers['Authorization'] = "Basic %s" % b64encode(
                ("%s:%s" % (self.auth[0], self.auth[1])).encode()
            ).decode()
        _urllib_kwargs['headers'] = self.headers
        return MethodRequest(self.method, _url_actual, **_urllib_kwargs)

class ApiRequest(BaseRequest):
    def __init__(self, method, url, *args, **kwargs):
        # url could contain only the resource part so we append the base
        if API_BASE not in url:
            # note, if lefthand does not contain a trailing slash it will pick
            # up the last part as a resource and replace it with righthand!!
            url = urljoin(API_BASE, url)
        super(ApiRequest, self).__init__(method, url, *args, **kwargs)

class SpotifyUser(object):
    def __init__(self, access_token=None, refresh_token=None):
        self.access_token = access_token
        self.refresh_token = refresh_token

class SpotifyAPI(object):
    def __init__(
        self, client_id=None, client_secret=None, redirect_uri=None,
        user=None
    ):
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = client_secret \
            or os.getenv("SPOTIFY_CLIENT_SECRET")
        self.redirect_uri = redirect_uri \
            or os.getenv("SPOTIFY_REDIRECT_URI")
        self.auth_user = None
        if user is not None:
            self.set_user(user)
        elif os.getenv("SPOTIFY_REFRESH_TOKEN"):
            self.set_user(
                SpotifyUser(refresh_token=os.getenv("SPOTIFY_REFRESH_TOKEN"))
            )

    def _refresh_access_token(self):
        if self.auth_user is None:
            raise SpotifyException('no user registered')
        if self.auth_user.refresh_token is None:
            raise SpotifyException('missing refresh token')
        try:
            resp = urlopen(BaseRequest(
                'POST', TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.auth_user.refresh_token
                },
                auth=(self.client_id, self.client_secret)
            ).prepare())
            payload = json.loads(resp.read())
            self.auth_user.access_token = payload['access_token']
            self.auth_user.refresh_token = payload.get(
                'refresh_token', self.auth_user.refresh_token
            )
        except HTTPError as e:
            raise SpotifyException("error refreshing user token - %d - %s" % (
                e.code, e.read()
            ))

    def _api_req(self, req):
        if self.auth_user is None:
            raise SpotifyException('no user registered')
        req.headers['Authorization'] = 'Bearer %s' % (
            self.auth_user.access_token
        )
        try:
            return urlopen(req.prepare())
        except HTTPError as e:
            if e.code != 401:
                raise
            # refresh token and retry once
            self._refresh_access_token()
            req.headers['Authorization'] = 'Bearer %s' % (
                self.auth_user.access_token
            )
            try:
                return urlopen(req.prepare())
            except HTTPError as e:
                raise SpotifyException(
                    "error issuing api request - %d - %s" % (
                        e.code, json.loads(e.read())
                    )
                )

    def _api_req_json(self, req):
        resp = self._api_req(req)
        return json.loads(resp.read())

    # These methods are to be used by clients that want a more direct
    # access to the web API. They simply apply the authentication headers
    # and handle the request construction and retry logic. Response is
    # whatever is returned by urlopen. All additional logic like pagination
    # and parameter formatting will have to be handled manually.
    def req(
        self, method, url, params=None, data=None, json=None, headers=None
    ):
        return self._api_req(
            ApiRequest(
                method, url, params=params, data=data, json=json,
                headers=headers
            )
        )
    def get(self, url, **kwargs):
        return self.req('GET', url, **kwargs)
    def post(self, url, **kwargs):
        return self.req('POST', url, **kwargs)
    def put(self, url, **kwargs):
        return self.req('PUT', url, **kwargs)
    def delete(self, url, **kwargs):
        return self.req('DELETE', url, **kwargs)

    def set_user(self, user):
        if not isinstance(user, SpotifyUser):
            raise SpotifyException('invalid user instance')
        self.auth_user = user

    def set_user_from_code(self, code):
        """Call this after obtaining an authorization code
        to generate access/refresh tokens for user access.
        """
        if self.client_id is None or self.client_secret is None:
            raise SpotifyException("client credentials not provided")
        if self.redirect_uri is None:
            raise SpotifyException("missing redirect URI")
        try:
            resp = urlopen(BaseRequest(
                'POST', TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri
                },
                auth=(self.client_id, self.client_secret)
            ).prepare())
            payload = json.loads(resp.read())
            self.auth_user = SpotifyUser(
                payload['access_token'],
                payload['refresh_token']
            )
            return self.auth_user
        except HTTPError as e:
            raise SpotifyException(
                "error generating user access token - %d - %s" % (
                    e.code, e.read()
                )
            )

    def oauth2_url(self, scopes=None):
        """Crafts a URL that you can use to request user access.
        After successful authorization Spotify will redirect to the
        provided redirect URI with the one-time auth code. You can pass
        that to `set_user_from_code` to update this client's tokens.
        """
        if scopes is None:
            scopes = []
        if self.redirect_uri is None:
            raise SpotifyException("missing redirect URI")
        if self.client_id is None:
            raise SpotifyException("missing client ID")
        for s in scopes:
            if s not in VALID_SCOPES:
                raise SpotifyException("invalid scope: %s" % s)
        return '%s?%s' % (
            OAUTH2_URL, urlencode({
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": ' '.join(scopes)
            })
        )

    def _resp_paginator(self, req, oname=None, limit=None):
        """Generator that iterates over the items returned by a Spotify
        paging object and seamlessly requests the next batch until exhausted.

        Optionally pass a limit parameter to set the number of returned results
        per batch, making sure it does not exceed Spotify's limitations or the
        request will fail.
        """
        if limit is not None:
            req.params['limit'] = limit
        next_url = req.url
        while next_url:
            req.url = next_url
            try:
                results = self._api_req_json(req)
                if oname is not None:
                    results = results[oname]
                for item in results['items']:
                    yield item
            except HTTPError:
                return
            next_url = results.get('next')

    def _req_paginator(self, req, xs, iname, oname=None, limit=50):
        """Sends input parameters in chunks. Only works for query parameters.

        `req`: The request object on which to apply parameter chunking.
        `xs`: The input list.
        `iname`: The query param name to use.
        `oname`: Optinally the output param name under which the response
            list is located. If omitted the return type is the raw response.
        `limit`: The number of items per chunk.
        """
        for chunk in chunked(xs, limit):
            req.params[iname] = ','.join(chunk)
            if oname is None:
                yield self._api_req(req)
            else:
                resp = self._api_req_json(req)
                for item in resp[oname]:
                    yield item

    ###########################################################################

    ################################## Albums #################################
    def album(self, album_id, **kwargs):
        return self._api_req_json(
            ApiRequest('GET', 'albums/%s' % album_id, params=kwargs)
        )

    def albums(self, album_ids, **kwargs):
        req = ApiRequest('GET', 'albums', params=kwargs)
        return self._req_paginator(req, album_ids, 'ids', 'albums', limit=20)

    def album_tracks(self, album_id, **kwargs):
        req = ApiRequest('GET', 'albums/%s/tracks' % album_id, params=kwargs)
        return self._resp_paginator(req)

    ################################# Artists #################################
    def artist(self, artist_id):
        return self._api_req_json(ApiRequest('GET', 'artists/%s' % artist_id))

    def artists(self, artist_ids):
        req = ApiRequest('GET', 'artists')
        return self._req_paginator(req, artist_ids, 'ids', 'artists', limit=50)

    @csv_kwargs('include_groups')
    def artist_albums(self, artist_id, **kwargs):
        req = ApiRequest('GET', 'artists/%s/albums' % artist_id, params=kwargs)
        return self._resp_paginator(req)

    def artist_top_tracks(self, artist_id, **kwargs):
        _cntr = 'country'
        kwargs[_cntr] = kwargs.get(_cntr, 'from_token')
        req = ApiRequest(
            'GET', 'artists/%s/top-tracks' % artist_id, params=kwargs
        )
        for track in self._api_req_json(req)['tracks']:
            yield track

    def artist_related_artists(self, artist_id):
        req = ApiRequest('GET', 'artists/%s/related-artists' % artist_id)
        for item in self._api_req_json(req)['artists']:
            yield item

    ################################# Browse ##################################
    def category(self, category_id, **kwargs):
        return self._api_req_json(ApiRequest(
            'GET', 'browse/categories/%s' % category_id, params=kwargs
        ))

    def categories(self, **kwargs):
        req = ApiRequest('GET', 'browse/categories', params=kwargs)
        return self._resp_paginator(req, oname='categories')

    def category_playlists(self, category_id, **kwargs):
        req = ApiRequest(
            'GET', 'browse/categories/%s/playlists' % category_id,
            params=kwargs
        )
        return self._resp_paginator(req, oname='playlists')

    def featured_playlists(self, **kwargs):
        ts = 'timestamp'
        if ts in kwargs and isinstance(kwargs['ts'], datetime.datetime):
            kwargs['ts'] = kwargs['ts'].replace(microsecond=0).isoformat()
        req = ApiRequest('GET', 'browse/featured-playlists', params=kwargs)
        return self._resp_paginator(req, oname='playlists')

    def new_releases(self, **kwargs):
        req = ApiRequest('GET', 'browse/new-releases', params=kwargs)
        return self._resp_paginator(req, oname='albums')

    @csv_kwargs('seed_artists', 'seed_genres', 'seed_tracks')
    def recommendations(self, **kwargs):
        _seeds = ['seed_artists', 'seed_genres', 'seed_tracks']
        if not any([x in kwargs for x in _seeds]):
            raise SpotifyException('seed value(s) missing')
        req = ApiRequest('GET', 'recommendations', params=kwargs)
        return self._api_req_json(req)

    ############################## Episodes ###################################
    def episode(self, episode_id, **kwargs):
        req = ApiRequest('GET', 'episodes/%s' % episode_id, params=kwargs)
        return self._api_req_json(req)

    def episodes(self, episode_ids, **kwargs):
        req = ApiRequest('GET', 'episodes', params=kwargs)
        return self._req_paginator(
            req, episode_ids, 'ids', 'episodes', limit=50
        )

    ################################ Follow ###################################
    def _is_following_type(self, _type, type_ids):
        req = ApiRequest(
            'GET', 'me/following/contains', params={'type': _type}
        )
        for resp in self._req_paginator(req, type_ids, "ids", limit=50):
            results = json.loads(resp.read())
            for res in results:
                yield res

    def is_following_artists(self, artist_ids):
        return self._is_following_type('artist', artist_ids)

    def is_following_users(self, user_ids):
        return self._is_following_type('user', user_ids)

    def is_playlist_followed(self, playlist_id, user_ids):
        req = ApiRequest(
            'GET', 'playlists/%s/followers/contains' % playlist_id
        )
        for resp in self._req_paginator(req, user_ids, 'ids', limit=5):
            for res in json.loads(resp.read()):
                yield res

    def _follow_unfollow_type(self, method, _type, type_ids):
        req = ApiRequest(method, 'me/following', params={'type': _type})
        for resp in self._req_paginator(req, type_ids, "ids", limit=50):
            _expect_status(204, resp)
        return True

    def follow_artists(self, artist_ids):
        return self._follow_unfollow_type('PUT', 'artist', artist_ids)

    def follow_users(self, user_ids):
        return self._follow_unfollow_type('PUT', 'user', user_ids)

    def unfollow_artists(self, artist_ids):
        return self._follow_unfollow_type('DELETE', 'artist', artist_ids)

    def unfollow_users(self, user_ids):
        return self._follow_unfollow_type('DELETE', 'user', user_ids)

    def follow_playlist(self, playlist_id, **kwargs):
        req = ApiRequest(
            'PUT', 'playlists/%s/followers' % playlist_id,
            json=kwargs
        )
        _expect_status(200, self._api_req(req))
        return True

    def unfollow_playlist(self, playlist_id):
        req = ApiRequest('DELETE', 'playlists/%s/followers' % playlist_id)
        _expect_status(200, self._api_req(req))
        return True

    def artists_followed(self):
        req = ApiRequest('GET', 'me/following', params={'type': 'artist'})
        return self._resp_paginator(req, 'artists', limit=50)

    ############################# Library #####################################
    def _is_type_saved(self, _type, type_ids):
        req = ApiRequest('GET', 'me/%s/contains' % _type)
        for resp in self._req_paginator(req, type_ids, "ids", limit=50):
            results = json.loads(resp.read())
            for res in results:
                yield res

    def are_albums_saved(self, album_ids):
        return self._is_type_saved('albums', album_ids)

    def are_shows_saved(self, show_ids):
        return self._is_type_saved('shows', show_ids)

    def are_tracks_saved(self, track_ids):
        return self._is_type_saved('tracks', track_ids)

    def saved_albums(self, **kwargs):
        req = ApiRequest('GET', 'me/albums', params=kwargs)
        return self._resp_paginator(req)

    def saved_album_objs(self, **kwargs):
        for item in self.saved_albums(**kwargs):
            yield item['album']

    def saved_shows(self):
        req = ApiRequest('GET', 'me/shows')
        return self._resp_paginator(req)

    def saved_show_objs(self):
        for item in self.saved_shows():
            yield item['show']

    def saved_tracks(self, **kwargs):
        req = ApiRequest('GET', 'me/tracks', params=kwargs)
        return self._resp_paginator(req)

    def saved_track_objs(self, **kwargs):
        for item in self.saved_tracks(**kwargs):
            yield item['track']

    def saved_albums_remove(self, album_ids):
        req = ApiRequest('DELETE', 'me/albums')
        for resp in self._req_paginator(req, album_ids, 'ids', limit=50):
            _expect_status(200, resp)
        return True

    def saved_shows_remove(self, show_ids):
        req = ApiRequest('DELETE', 'me/shows')
        for resp in self._req_paginator(req, show_ids, 'ids', limit=50):
            _expect_status(200, resp)
        return True

    def saved_tracks_remove(self, track_ids, **kwargs):
        req = ApiRequest('DELETE', 'me/tracks', params=kwargs)
        for resp in self._req_paginator(req, track_ids, 'ids', limit=50):
            _expect_status(200, resp)
        return True

    def saved_albums_add(self, album_ids):
        req = ApiRequest('PUT', 'me/albums')
        for resp in self._req_paginator(req, album_ids, 'ids', limit=50):
            _expect_status(200, resp)
        return True

    def saved_shows_add(self, show_ids):
        req = ApiRequest('PUT', 'me/shows')
        for resp in self._req_paginator(req, show_ids, 'ids', limit=50):
            _expect_status(200, resp)
        return True

    def saved_tracks_add(self, track_ids):
        req = ApiRequest('PUT', 'me/tracks')
        for resp in self._req_paginator(req, track_ids, 'ids', limit=50):
            _expect_status(200, resp)
        return True

    ############################ Personalization ##############################
    def _top_type(self, _type, **kwargs):
        req = ApiRequest('GET', 'me/top/%s' % _type)
        return self._resp_paginator(req)

    def top_tracks(self, **kwargs):
        return self._top_type('tracks', **kwargs)

    def top_artists(self, **kwargs):
        return self._top_type('artists', **kwargs)

    ############################# Playlists ###################################
    def playlist_tracks_add(self, playlist_id, track_uris, **kwargs):
        req = ApiRequest(
            'POST', 'playlists/%s/tracks' % playlist_id, json=kwargs
        )
        for chunk in chunked(track_uris, 100):
            req.json['uris'] = chunk
            final_resp = self._api_req(req)
            _expect_status(201, final_resp)
        return json.loads(final_resp.read())

    def playlist_edit(self, playlist_id, **kwargs):
        req = ApiRequest(
            'PUT', 'playlists/%s' % playlist_id, json=kwargs
        )
        resp = self._api_req(req)
        return resp.code == 200

    @kwargs_required('name')
    def playlists_add(self, user_id=None, **kwargs):
        if user_id is None:
            _url = 'me/playlists'
        else:
            _url = 'users/%s/playlists' % user_id
        return self._api_req_json(ApiRequest('POST', _url, json=kwargs))

    def playlists(self, user_id=None):
        if user_id is None:
            req = ApiRequest('GET', 'me/playlists')
        else:
            req = ApiRequest('GET', 'users/%s/playlists' % user_id)
        return self._resp_paginator(req, limit=50)

    def playlist_images(self, playlist_id):
        req = ApiRequest('GET', 'playlists/%s/images' % playlist_id)
        for item in self._api_req_json(req):
            yield item

    @csv_kwargs('fields')
    def playlist(self, playlist_id, **kwargs):
        req = ApiRequest('GET', 'playlists/%s' % playlist_id, params=kwargs)
        return self._api_req_json(req)

    @csv_kwargs('fields')
    def playlist_tracks(self, playlist_id, **kwargs):
        req = ApiRequest(
            'GET', 'playlists/%s/tracks' % playlist_id, params=kwargs
        )
        return self._resp_paginator(req, limit=100)

    def playlist_track_objs(self, playlist_id, **kwargs):
        for item in self.playlist_tracks(playlist_id, **kwargs):
            yield item['track']

    def playlist_tracks_remove(self, playlist_id, track_params, **kwargs):
        req = ApiRequest(
            'DELETE', 'playlists/%s/tracks' % playlist_id, json=kwargs
        )
        if len(track_params) > 100 and \
            any(map(
                lambda x: not isinstance(x, str),
                track_params[100:]
            )):
                raise SpotifyException(
                    "cannot positionally delete after 100 items."
                )
        last_resp = {}
        for chunk in chunked(track_params, 100):
            payload = []
            for item in chunk:
                if isinstance(item, basestring):
                    payload.append({"uri": item})
                else:
                    payload.append({
                        "uri": item[0],
                        "positions": list(item[1])
                    })
            req.json['tracks'] = payload
            last_resp = self._api_req_json(req)
        return last_resp

    @kwargs_required('range_start', 'insert_before')
    def playlist_tracks_reorder(self, playlist_id, **kwargs):
        req = ApiRequest(
            'PUT', 'playlists/%s/tracks' % playlist_id, json=kwargs
        )
        return self._api_req_json(req)

    def playlist_tracks_replace(self, playlist_id, track_uris):
        req = ApiRequest('PUT', 'playlists/%s/tracks' % playlist_id)
        for resp in self._req_paginator(req, track_uris, 'uris', limit=100):
            _expect_status(201, resp)
        return True

    def playlist_image_add(self, playlist_id, image_file):
        req = ApiRequest(
            'PUT', 'playlists/%s/images' % playlist_id, _file=image_file
        )
        _expect_status(202, self._api_req(req))
        return True

    ############################# Search ######################################
    def _search_type(self, _type, q, **kwargs):
        kwargs['type'] = _type
        kwargs['query'] = q
        req = ApiRequest('GET', 'search', params=kwargs)
        return self._resp_paginator(req, '%ss' % _type, limit=50)

    def search_albums(self, q, **kwargs):
        return self._search_type('album', q, **kwargs)
    def search_artists(self, q, **kwargs):
        return self._search_type('artist', q, **kwargs)
    def search_playlists(self, q, **kwargs):
        return self._search_type('playlist', q, **kwargs)
    def search_tracks(self, q, **kwargs):
        return self._search_type('track', q, **kwargs)
    def search_shows(self, q, **kwargs):
        return self._search_type('show', q, **kwargs)

    ############################# Shows #######################################
    def show(self, show_id, **kwargs):
        req = ApiRequest('GET', 'shows/%s' % show_id, params=kwargs)
        return self._api_req_json(req)

    def shows(self, show_ids, **kwargs):
        req = ApiRequest('GET', 'shows', params=kwargs)
        return self._req_paginator(req, show_ids, 'ids', 'shows', limit=50)

    def show_episodes(self, show_id, **kwargs):
        req = ApiRequest('GET', 'shows/%s/episodes' % show_id, params=kwargs)
        return self._resp_paginator(req, limit=50)

    ############################## Tracks #####################################
    def track_audio_analysis(self, track_id):
        req = ApiRequest('GET', 'audio-analysis/%s' % track_id)
        return self._api_req_json(req)

    def track_audio_features(self, track_id):
        req = ApiRequest('GET', 'audio-features/%s' % track_id)
        return self._api_req_json(req)

    def tracks_audio_features(self, track_ids):
        req = ApiRequest('GET', 'audio-features')
        return self._req_paginator(
            req, track_ids, 'ids', 'audio_features', limit=100
        )

    def tracks(self, track_ids, **kwargs):
        req = ApiRequest('GET', 'tracks', params=kwargs)
        return self._req_paginator(req, track_ids, 'ids', 'tracks', limit=50)

    def track(self, track_id, **kwargs):
        req = ApiRequest('GET', 'tracks/%s' % track_id, params=kwargs)
        return self._api_req_json(req)

    ############################ User Profile #################################
    def profile(self, user_id=None):
        if user_id is None:
            req = ApiRequest('GET', 'me')
        else:
            req = ApiRequest('GET', 'users/%s' % user_id)
        return self._api_req_json(req)

    ############################ Player #######################################
    @csv_kwargs('additional_types')
    def player(self, **kwargs):
        req = ApiRequest('GET', 'me/player', params=kwargs)
        return self._api_req_json(req)

    def player_transfer(self, device_id, **kwargs):
        kwargs['device_ids'] = [device_id]
        self._api_req(ApiRequest('PUT', 'me/player', json=kwargs))

    def player_devices(self):
        req = ApiRequest('GET', 'me/player/devices')
        for item in self._api_req_json(req)['devices']:
            yield item

    @csv_kwargs('additional_types')
    def player_current_track(self, **kwargs):
        req = ApiRequest('GET', 'me/player/currently-playing', params=kwargs)
        return self._api_req_json(req)

    def player_play(self, **kwargs):
        _fld = 'device_id'
        params = {}
        if _fld in kwargs:
            params[_fld] = kwargs[_fld]
        self._api_req(ApiRequest('PUT', 'me/player/play', params=params, json=kwargs))

    def player_pause(self, **kwargs):
        self._api_req(ApiRequest('PUT', 'me/player/pause', params=kwargs))

    def player_next(self, **kwargs):
        self._api_req(ApiRequest('POST', 'me/player/next', params=kwargs))

    def player_previous(self, **kwargs):
        self._api_req(ApiRequest('POST', 'me/player/previous', params=kwargs))

    @kwargs_required('position_ms')
    def player_seek(self, **kwargs):
        self._api_req(ApiRequest('PUT', 'me/player/seek', params=kwargs))

    @kwargs_required('state')
    def player_repeat(self, **kwargs):
        self._api_req(ApiRequest('PUT', 'me/player/repeat', params=kwargs))

    @kwargs_required('volume_percent')
    def player_volume(self, **kwargs):
        self._api_req(ApiRequest('PUT', 'me/player/volume', params=kwargs))

    @kwargs_required('state')
    def player_shuffle(self, **kwargs):
        self._api_req(ApiRequest('PUT', 'me/player/shuffle', params=kwargs))

    def player_recent_tracks(self, **kwargs):
        req = ApiRequest('GET', 'me/player/recently-played')
        return self._resp_paginator(req, limit=50)

    def player_recent_track_objs(self, **kwargs):
        for item in self.player_recent_tracks(**kwargs):
            yield item['track']

    def player_queue_add(self, uri, **kwargs):
        _prefix = 'spotify:track:'
        if not uri.startswith(_prefix):
            uri = '%s%s' % (_prefix, uri)
        kwargs['uri'] = uri
        req = ApiRequest('POST', 'me/player/queue', params=kwargs)
        self._api_req(req)
