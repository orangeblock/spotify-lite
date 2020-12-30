import sys
import enum
import types
import json
import urllib
try:
    from inspect import getfullargspec
except ImportError:
    from inspect import getargspec as getfullargspec

from functools import wraps
from urllib.parse import quote, urlencode, urljoin, parse_qs
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

class ParamType(enum.Enum):
    QUERY = 1
    JSON = 2

def chunked(xs, n):
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
            resp = self._api_req_json(ApiRequest('GET', 'me'))
            self.user_id = resp['id']
        return method(self, *args, **kwargs)
    return _inner

def ensure_ids(*tups):
    """Helper to seamlessly convert between ids and uris ensuring
    the parameter is in the required format.

    Input parameters are one or more tuples of the format (ptype, pname),
    where ptype is the type of id and pname is the name of the parameter
    in the function signature. If type is "id" param will be converted to
    a Spotify ID, otherwise to an appropriate URI, e.g. "track" converts
    to "spotify:track:...", "artist" to "spotify:artist:..." and so on.

    Example:
    @ensure_ids(("id", "user_id"), ("artist", "artist_id"))
    def(self, user_id, artist_id, **kwargs):
        # artist_id is in the form of spotify:artist:<artist_id>
        ...
    """
    def _wrapper(method):
        spec = getfullargspec(method)
        @wraps(method)
        def _inner(self, *args, **kwargs):
            # we add self to the arguments so we don't have to juggle indexes
            # while avoiding the implicit one
            args = [self] + list(args)
            for (ptype, pname) in tups:
                pidx = spec.args.index(pname)
                try:
                    val = args[pidx]
                except IndexError:
                    val = kwargs[pname]
                if ptype == 'id':
                    transformer = lambda x: x.split(':')[-1]
                else:
                    transformer = lambda x: 'spotify:%s:%s' % (
                        ptype, x.split(':')[-1]
                    )
                if isinstance(val, list):
                    val = list(map(transformer, val))
                else:
                    val = transformer(val)
                try:
                    args[pidx] = val
                except IndexError:
                    kwargs[pname] = val
            return method(*args, **kwargs)
        return _inner
    return _wrapper

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
            _params_actual = self.params
            parts = _url_actual.split("?")
            if len(parts) > 2 or len(parts) < 1:
                raise Exception("malformed URL")
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
            return urlopen(req.prepare())
        except urllib.error.HTTPError as e:
            if e.status != 401:
                raise
            # refresh token and retry once
            self._refresh_access_token()
            req.headers['Authorization'] = 'Bearer %s' % self.access_token
            try:
                return urlopen(req.prepare())
            except urllib.error.HTTPError as e:
                raise Exception("error issuing api request - %d - %s" % (
                    e.status, json.loads(e.read())
                )) from None

    def _api_req_json(self, req):
        resp = self._api_req(req)
        return json.loads(resp.read())

    # These methods are to be used by clients that want a more direct
    # access to the web API. They simply apply the authentication headers
    # and handle the request construction and retry logic. Response is
    # whatever is returned by urlopen. All additional logic like pagination
    # and parameter formatting will have to be handled manually.
    def req(self, method, url, params=None, data=None, json=None, headers=None):
        return self._api_req(
            ApiRequest(
                method, url, params=params, data=data, json=json,
                headers=headers
            ).prepare()
        )
    def get(self, url, **kwargs):
        return self.req('GET', url, **kwargs)
    def post(self, url, **kwargs):
        return self.req('POST', url, **kwargs)
    def put(self, url, **kwargs):
        return self.req('PUT', url, **kwargs)
    def delete(self, url, **kwargs):
        return self.req('DELETE', url, **kwargs)

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
        provided redirect URI with the one-time auth code. You can pass
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

    def _resp_paginator(self, req, oname=None, limit=None):
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
            results = self._api_req_json(req)
            if oname is not None:
                results = results[oname]
            for item in results['items']:
                yield item
            next_url = results.get('next')

    def _req_paginator(
        self, req, xs, iname, oname=None, limit=50, ptype=ParamType.QUERY
    ):
        """"""
        for chunk in chunked(xs, limit):
            if ptype == ParamType.QUERY:
                req.params[iname] = ','.join(chunk)
            elif ptype == ParamType.JSON:
                req.json[iname] = chunk
            if oname is None:
                yield self._api_req(req)
            else:
                resp = self._api_req_json(req)
                for item in resp[oname]:
                    yield item

    ############################################################################

    #### Albums
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

    #### Artists
    def artist(self, artist_id):
        return self._api_req_json(ApiRequest('GET', 'artists/%s' % artist_id))

    def artists(self, artist_ids):
        req = ApiRequest('GET', 'artists')
        return self._req_paginator(req, artist_ids, 'ids', 'artists', limit=50)

    def artist_albums(self, artist_id, **kwargs):
        _incl_grp = 'include_groups'
        if _incl_grp in kwargs:
            kwargs[_incl_grp] = ','.join(kwargs[_incl_grp])
        req = ApiRequest('GET', 'artists/%s/albums' % artist_id, params=kwargs)
        return self._resp_paginator(req)

    def artist_top_tracks(self, artist_id, **kwargs):
        _cntr = 'country'
        kwargs[_cntr] = kwargs.get(_cntr, 'from_token')
        req = ApiRequest('GET', 'artists/%s/top-tracks' % artist_id, params=kwargs)
        return self._api_req_json(req)['tracks']

    def artist_related_artists(self, artist_id):
        req = ApiRequest('GET', 'artists/%s/related-artists' % artist_id)
        for item in self._api_req_json(req)['artists']:
            yield item

    #### Browse
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
        # TODO: timestamp
        req = ApiRequest('GET', 'browse/featured-playlists', params=kwargs)
        return self._resp_paginator(req, oname='playlists')

    def new_releases(self, **kwargs):
        req = ApiRequest('GET', 'browse/new-releases', params=kwargs)
        return self._resp_paginator(req, oname='albums')

    def recommendations(self):
        pass

    #### Episodes
    #### Follow
    #### Library
    #### Personalization
    #### Player
    #### Playlists
    #### Search
    #### Shows
    #### Tracks
    #### Users Profile

    def playlist(self, playlist_id):
        req = ApiRequest('GET', 'playlists/%s' % playlist_id)
        return self._api_req_json(req)

    @user_required
    def playlists(self, user_id=None):
        if user_id is None:
            user_id = self.user_id
        req = ApiRequest('GET', 'users/%s/playlists' % user_id)
        for item in self._resp_paginator(req):
            yield item

    def playlist_tracks(self, playlist_id):
        req = ApiRequest('GET', 'playlists/%s/tracks' % playlist_id)
        for item in self._resp_paginator(req):
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
        return self._api_req_json(req)

    def playlist_edit(self, playlist_id, **kwargs):
        req = ApiRequest(
            'PUT', 'playlists/%s' % playlist_id,
            json=kwargs
        )
        resp = self._api_req(req)
        return resp.status == 200

    @ensure_ids(('id', 'playlist_id'), ('track', 'track_uris'))
    def playlist_tracks_add(self, playlist_id, track_uris, **kwargs):
        req = ApiRequest(
            'POST', 'playlists/%s/tracks' % playlist_id, json=kwargs
        )
        responses = self._req_paginator(
            req, track_uris, 'uris', limit=100, ptype=ParamType.JSON
        )
        status_expected = 201
        for resp in responses:
            if resp.status != status_expected:
                raise Exception("invalid status code - %d (expected %d) - %s" % (
                    resp.status, status_expected, resp.read()
                ))
        return True

    def tracks(self, track_ids, **kwargs):
        req = ApiRequest('GET', 'tracks', params=kwargs)
        return self._req_paginator(req, track_ids, 'ids', 'tracks', limit=50)
