# spotify-lite
A lightweight, single-file, zero-dependency Spotify wrapper that can be dropped into any Python 2.x or 3.x project with minimal hassle.

## Quick Start
Copy `spotify.py` anywhere into your project. 

Get an instance of the API wrapper:
```python
import spotify

client_id = "my-client-id"
client_secret = "top-secret"
# optional but required when registering a user via authorization code flow
redirect_uri = "http://localhost:1337"

api = spotify.SpotifyAPI(client_id, client_secret, redirect_uri)
```

Get user permission and complete authorization:
```python
url = api.oauth2_url(scopes=['user-read-private'])
# redirect user to above url, get auth code and then...
user = api.set_user_from_code('really-long-code-string')
```
See [Authorization](#authorization) section for more options and detailed explanation.

Get a playlist:
```python
pl = api.playlist('1SCHh6WSTufPLgEFjGSteL')
print(pl['name'])
```
The response for single resource endpoints is the JSON response from Spotify, as a Python dictionary.

Get associated user's playlists:
```python
pls = api.playlists()
for pl in pls:
  print(pl['name'])
```
The response for endpoints returning multiple resources is always a **generator**, yielding the inner Spotify resource(s). Pagination is automatically handled. 

Post a boatload of tracks to a playlist:
```python
track_uris = ["spotify:track:4uLU6hMCjMI75M1A2tKUQC"] * 5000
api.playlist_tracks_add('some-playlist-id', track_uris)
```
You don't need to batch your requests - the above will execute multiple batch requests internally to add all tracks to the playlist.

See [API Endpoints](#api-endpoints) for a more in-depth look at the request/response mapping.

----
# **<span style="color:red;">IGNORE BELOW THIS POINT - INCOMPLETE</span>**

## Authorization
Create an instance of the API wrapper using your developer client credentials:
```python
import spotify

client_id = "my-client-id"
client_secret = "top-secret"
# optional but required when registering a user via authorization code
redirect_uri = "http://localhost:1337"

api = spotify.SpotifyAPI(client_id, client_secret, redirect_uri) 
```
Alternatively you can set the `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_REDIRECT_URI` environment variables and call the above constructor with no arguments.

Currently this library supports the [authorization code flow](https://developer.spotify.com/documentation/general/guides/authorization-guide/#authorization-code-flow). You will need to prompt a user to grant permissions which will generate an authorization code that you can use to associate the user with the API instance. You can call `api.oauth2_url(scopes=['user-read-private'])` on the above created object to generate a valid auth URL requesting the specified roles (passed as a list of strings). Refer to [Spotify documentation](https://developer.spotify.com/documentation/general/guides/scopes/) for allowed authorization scopes. 

After you've sent the user to the above URL (and assuming your setup credentials are valid) you will obtain an authorization code on the specified redirect URI. You can then pass that code to the API instance:
```python
code = "code-i-received-from-authorization-flow"
user = api.set_user_from_code(code)
```
If successful, the `user` object you receive contains the currently generated access and refresh tokens. You can store `user.refresh_token` to skip the authorization code flow in the future. According to Spotify refresh tokens should be valid indefinitely unless you change your client credentials. Below is the API wrapper instantiation for a user that has a known refresh token:
```python
# assume environment variables for client credentials are set
user = spotify.SpotifyUser(refresh_token='user-token-persisted-across-sessions')
api = spotify.SpotifyAPI(user=user)
```
`SpotifyUser`s can be dynamically assigned to a `SpotifyAPI` instance:
```python
new_user = spotify.SpotifyUser(refresh_token='another-saved-token')
api.set_user(new_user)
# API methods now work against new_user
```
## API endpoints
This library is built with the idea of hiding all pagination and handling parameter parsing so that you can use pythonic invocations.

Get a playlist:
```python
pl = api.playlist("1SCHh6WSTufPLgEFjGSteL")
print(pl['name'])
```
Responses will always return the inner JSON resource obtained from Spotify, parsed into a Python dictionary for easy access. All methods that should return multiple items return a generator, which you use to iterate over all results without specifiying any pagination parameters:
```python
tracks_generator = api.playlist_tracks("1SCHh6WSTufPLgEFjGSteL")
for track in tracks_generator:
  print(track['name'])
```
You don't have to unwrap the Spotify paging object or worry about hitting pagination limits, the library will automatically handle all of this and always use the highest available limit for each paginated request to limit round-trip time.

Endpoints that receive multiple ids usually need to be sent in batches. The library takes care of all that for you so you can simply pass the entire list:
```python
# huge list of 5000 tracks
track_uris = [...] 
api.playlist_tracks_add("my-playlist-id", track_uris)
```
