# pylint: disable=E1101
import sys
import types
import json
import urllib

from functools import wraps
from urllib.parse import quote, urlencode, urljoin
from urllib.request import urlopen
from urllib.request import Request
from base64 import b64encode

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

def _chunked(xs, n):
    """Yields successive n-sized chunks from xs"""
    for i in range(0, len(xs), n):
        yield xs[i:i+n]

def kwargs_required(*xs):
    def _wrapper(method):
        @wraps(method)
        def _inner(self, *args, **kwargs):
            for x in xs:
                if x not in kwargs or not kwargs[x]:
                    raise Exception('missing required parameter: %s' % x)
            return method(self, *args, **kwargs)
        return _inner
    return _wrapper

def user_required(method):
    @wraps(method)
    def _inner(self, *args, **kwargs):
        if self.user_id is None:
            # update user_id for current user
            resp = self._api_req(ApiRequest('GET', 'me'))
            self.user_id = resp['id']
        return method(self, *args, **kwargs)
    return _inner

class MethodRequest(Request):
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
        json=None, headers=None, auth=None
    ):
        self.method = method
        self.url = url
        self.params = params or {}
        self.json = json or {}
        self.data = data or {}
        self.headers = headers or {}
        self.auth = auth

    def prepare(self):
        """Construct necessary data and return an instance of urllib's
        `Request` class.
        """
        _urllib_kwargs = {}
        _url_actual = self.url
        if self.json:
            _urllib_kwargs['data'] = json.dumps(self.json).encode()
            self.headers['Content-Type'] = 'application/json'
        elif self.data:
            _urllib_kwargs['data'] = urlencode(self.data).encode()
        if self.params:
            _url_actual = '%s?%s' % (_url_actual, urlencode(self.params))
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
            # careful, if lefthand does not contain a trailing slash it will
            # pick up the last part as a resource and replace it with righthand.
            url = urljoin(API_BASE, url)
        super(ApiRequest, self).__init__(method, url, *args, **kwargs)

class SpotifyAPI(object):
    def __init__(
        self, client_id=None, client_secret=None,
        access_token=None, refresh_token=None, redirect_uri=None
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.redirect_uri = redirect_uri
        self.user_id = None

    def _refresh_access_token(self):
        if self.refresh_token is None:
            raise Exception("missing refresh token")
        try:
            resp = urlopen(BaseRequest(
                'POST', TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token
                },
                auth=(self.client_id, self.client_secret)
            ).prepare())
            payload = json.loads(resp.read())
            self.access_token = payload['access_token']
            self.refresh_token = payload.get('refresh_token', self.refresh_token)
        except urllib.error.HTTPError as e:
            raise Exception("error refreshing user token - %d - %s" % (
                e.status, e.read()
            )) from None

    def _api_req(self, req):
        req.headers['Authorization'] = 'Bearer %s' % self.access_token
        try:
            resp = urlopen(req.prepare())
            return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.status != 401:
                raise
            # refresh token and retry once
            self._refresh_access_token()
            req.headers['Authorization'] = 'Bearer %s' % self.access_token
            try:
                resp = urlopen(req.prepare())
                return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                raise Exception("error issuing api request - %d - %s" % (
                    e.status, e.read()
                ))

    def register_code(self, code):
        """Call this after obtaining an authorization code
        to generate access/refresh tokens for user access.
        """
        if self.client_id is None or self.client_secret is None:
            raise Exception("client credentials not provided")
        if self.redirect_uri is None:
            raise Exception("missing redirect URI")
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
            self.access_token = payload['access_token']
            self.refresh_token = payload['refresh_token']
            # this method can be used to change the active user of this client
            # instance so we need to clear the user_id, allowing it to be
            # re-set when needed again.
            self.user_id = None
        except urllib.error.HTTPError as e:
            raise Exception("error generating user access token - %d - %s" % (
                e.status, e.read()
            )) from None

    def oauth2_url(self, scopes=None):
        """Crafts a URL that you can use to request user access.
        After successful authorization Spotify will redirect to the
        provided request URI with the one-time auth code. You can pass
        that to `register_code` to update this client's tokens.
        """
        if scopes is None:
            scopes = []
        if self.redirect_uri is None:
            raise Exception("missing redirect URI")
        if self.client_id is None:
            raise Exception("missing client ID")
        for s in scopes:
            if s not in VALID_SCOPES:
                raise Exception("invalid scope: %s" % s)
        return '%s?%s' % (
            OAUTH2_URL, urlencode({
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": ' '.join(scopes)
            })
        )

    def _response_paginator(self, req, limit=None):
        """Generator that iterates over the items returned by a Spotify
        paging object and seamlessly requests the next batch until exhausted.

        Optionally pass a limit parameter to set the number of returned results
        per batch although make sure it does not exceed Spotify's limitations
        or the request will fail.

        https://developer.spotify.com/documentation/web-api/reference/object-model/#paging-object
        """
        if limit is not None:
            req.params['limit'] = limit
        next_url = req.url
        while next_url:
            req.url = next_url
            results = self._api_req(req)
            for item in results['items']:
                yield item
            next_url = results.get('next')

    ################################################

    def playlist(self, playlist_id):
        req = ApiRequest('GET', 'playlists/%s' % playlist_id)
        return self._api_req(req)

    @user_required
    def playlists(self, user_id=None):
        if user_id is None:
            user_id = self.user_id
        req = ApiRequest('GET', 'users/%s/playlists' % user_id)
        for item in self._response_paginator(req):
            yield item

    def playlist_tracks(self, playlist_id):
        req = ApiRequest('GET', 'playlists/%s/tracks' % playlist_id)
        for item in self._response_paginator(req):
            yield item['track']

    @kwargs_required('name')
    @user_required
    def playlist_add(self, user_id=None, **kwargs):
        if user_id is None:
            user_id = self.user_id
        req = ApiRequest(
            'POST', 'users/%s/playlists' % user_id,
            json=kwargs
        )
        return self._api_req(req)

    def playlist_tracks_add(self, playlist_id, track_ids):
        # TODO: Rework
        success = True
        req = ApiRequest('POST', 'playlists/%s/tracks' % playlist_id)
        for chunk in _chunked(track_ids, 100):
            req.json = {'uris': chunk}
            try:
                self._api_req(req)
            except:
                success = False
        return success

    def tracks(self, track_ids):
        req = ApiRequest('GET', 'tracks')
        for chunk in _chunked(track_ids, 50):
            req.params['ids'] = ','.join(chunk)
            resp = self._api_req(req)
            for item in resp['tracks']:
                yield item

    def artists(self, artist_ids):
        req = ApiRequest('GET', 'artists')
        for chunk in _chunked(artist_ids, 50):
            req.params['ids'] = ','.join(chunk)
            resp = self._api_req(req)
            for item in resp['artists']:
                yield item

    def artist_related_artists(self, artist_id):
        req = ApiRequest('GET', 'artists/%s/related-artists' % artist_id)
        for item in self._api_req(req)['artists']:
            yield item
