import sys
import types
import requests

from requests import Request
from functools import wraps
from urllib.parse import quote, urlencode, urljoin

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
    """Yields successcive n-sized chunks from xs"""
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
            resp = self._api_req(Request('GET', 'me'))
            self.user_id = resp.json()['id']
        return method(self, *args, **kwargs)
    return _inner

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
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
            auth=(self.client_id, self.client_secret)
        )
        if not resp.ok:
            raise Exception("error refreshing user access token - %d - %s" % (
                resp.status_code, resp.text
            ))
        payload = resp.json()
        self.access_token = payload['access_token']
        self.refresh_token = payload.get('refresh_token', self.refresh_token)

    def _api_req(self, req, stream=False, timeout=30):
        session = requests.Session()
        # `req.url` could contain only the resource part so we append the base
        if API_BASE not in req.url:
            req.url = urljoin(API_BASE, req.url)
        req.headers['Authorization'] = 'Bearer %s' % self.access_token
        resp = session.send(req.prepare(), stream=stream, timeout=timeout)
        if(resp.status_code == 401):
            # refresh token and retry once
            self._refresh_access_token()
            req.headers['Authorization'] = 'Bearer %s' % self.access_token
            resp = session.send(req.prepare(), stream=stream, timeout=timeout)
            if not resp.ok:
                raise Exception("error")
        return resp

    def register_code(self, code):
        """Call this after obtaining an authorization code
        to generate access/refresh tokens for user access.
        """
        if self.client_id is None or self.client_secret is None:
            raise Exception("client credentials not provided")
        if self.redirect_uri is None:
            raise Exception("missing redirect URI")
        resp = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri
            },
            auth=(self.client_id, self.client_secret)
        )
        if not resp.ok:
            raise Exception("error generating user access token - %d - %s" % (
                resp.status_code, resp.text
            ))
        self.access_token = resp.json()['access_token']
        self.refresh_token = resp.json()['refresh_token']
        # this method can be used to change the active user of this client
        # instance so we need to clear the user_id, allowing it to be
        # re-set when needed again.
        self.user_id = None

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
            req.params["limit"] = limit
        next_url = req.url
        while next_url:
            req.url = next_url
            payload = self._api_req(req).json()
            for item in payload['items']:
                yield item
            next_url = payload.get('next')

    ################################################

    def playlist(self, playlist_id):
        req = Request('GET', 'playlists/%s' % playlist_id)
        return self._api_req(req).json()

    @user_required
    def playlists(self, user_id=None):
        if user_id is None:
            user_id = self.user_id
        req = Request('GET', 'users/%s/playlists' % user_id)
        for item in self._response_paginator(req):
            yield item

    def playlist_tracks(self, playlist_id):
        req = Request('GET', 'playlists/%s/tracks' % playlist_id)
        for item in self._response_paginator(req):
            yield item['track']

    @kwargs_required('name')
    @user_required
    def playlist_add(self, user_id=None, **kwargs):
        if user_id is None:
            user_id = self.user_id
        req = Request(
            'POST', 'users/%s/playlists' % user_id,
            json=kwargs
        )
        return self._api_req(req).json()

    def playlist_tracks_add(self, playlist_id, track_ids):
        success = True
        req = Request('POST', 'playlists/%s/tracks' % playlist_id)
        for chunk in _chunked(track_ids, 100):
            req.json = {'uris': chunk}
            resp = self._api_req(req)
            if not resp.ok:
                success = False
        return success

    def tracks(self, track_ids):
        req = Request('GET', 'tracks')
        for chunk in _chunked(track_ids, 50):
            req.params['ids'] = ','.join(chunk)
            resp = self._api_req(req)
            for item in resp.json()['tracks']:
                yield item

    def artists(self, artist_ids):
        req = Request('GET', 'artists')
        for chunk in _chunked(artist_ids, 50):
            req.params['ids'] = ','.join(chunk)
            resp = self._api_req(req)
            for item in resp.json()['artists']:
                yield item

    def artist_related_artists(self, artist_id):
        req = Request('GET', 'artists/%s/related-artists' % artist_id)
        for item in self._api_req(req).json()['artists']:
            yield item
