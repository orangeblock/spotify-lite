# spotify-lite
A lightweight, single-file, zero-dependency Spotify wrapper, that can be dropped into any Python 2.x or 3.x project with minimal hassle.

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

## Authorization
First, you need to initialize an instance of the API wrapper with your developer credentials:
```python
import spotify

client_id = "my-client-id"
client_secret = "top-secret"
# optional but required when registering a user via authorization code
redirect_uri = "http://localhost:1337"

api = spotify.SpotifyAPI(client_id, client_secret, redirect_uri) 
```
Alternatively you can set the `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_REDIRECT_URI` environment variables and call the above constructor with no arguments:
```python
import os

# ... or directly through your runtime environment
os.environ['SPOTIFY_CLIENT_ID'] = "my-client-id"
os.environ['SPOTIFY_CLIENT_SECRET'] = "top-secret"
os.environ['SPOTIFY_REDIRECT_URI'] = "http://localhost:1337"

api = spotify.SpotifyAPI()
```

This library supports the [authorization code flow](https://developer.spotify.com/documentation/general/guides/authorization-guide/#authorization-code-flow). You will need to prompt a user to grant permissions which will generate an authorization code that you can use to associate the user with the API instance. You can call `api.oauth2_url(scopes=['user-read-private'])` on the above created object to generate a valid auth URL requesting the specified roles (passed as a list of strings). Refer to the [documentation](https://developer.spotify.com/documentation/general/guides/scopes/) for allowed authorization scopes. 

After you've sent the user to the above URL (and assuming your setup credentials are valid) you will obtain an authorization code on the specified redirect URI. You can then pass that code to the API instance:
```python
code = "code-i-received-from-authorization-flow"
user = api.set_user_from_code(code)
```
If successful, the `user` object you receive contains the currently generated access and refresh tokens. You can store `user.refresh_token` to skip the authorization code flow in the future. According to Spotify refresh tokens should be valid indefinitely unless you change your client credentials. 

If you've persisted a user's refresh token you can directly instantiate an API instance by creating a `SpotifyUser` object and passing it to the wrapper's constructor:
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
If you only have one user for your application and you've already obtained the refresh token you can set the environment variable `SPOTIFY_REFRESH_TOKEN` to eliminate any boilerplate code:
```python
import os

# ... or directly through your runtime environment
os.environ['SPOTIFY_CLIENT_ID'] = "my-client-id"
os.environ['SPOTIFY_CLIENT_SECRET'] = "top-secret"
os.environ['SPOTIFY_REFRESH_TOKEN'] = "user-token-persisted-across-sessions"

api = spotify.SpotifyAPI()
print(api.profile())
```

----

## API endpoints
This library automatically handles pagination for requests and responses. Additionally, responses will always return the parsed JSON received from Spotify. 

Each Spotify API endpoint is mapped to a method you can access via the API wrapper instance. For details on what parameters are accepted for a particular endpoint, refer to the official [Web API Reference](https://developer.spotify.com/documentation/web-api/reference/). Path parameters and IDs for batch requests are passed as positional arguments, and query parameters as keyword arguments. The names of keyword arguments follow the naming convetion outlined in the Spotify documentation:
```python
>>> api.playlist('2pFB0I2SvMbsPHZrfRfbZL', fields=['description', 'uri'])
{'description': 'Music candy. High replay value.', 'uri': 'spotify:playlist:2pFB0I2SvMbsPHZrfRfbZL'}
```
You will notice in the above we are using a Python list instead of what the documentation mentions, which is a comma-separated list of strings. In general, CSV parameters should be passed as lists and the library will automatically convert them. Additionally, ignore any parameters that have to deal with pagination, such as `limit` or `offset` as these are automatically handled internally.  

All methods that should return multiple items return a generator, which you use to iterate over all results without specifiying any pagination parameters:
```python
tracks_generator = api.playlist_tracks("1SCHh6WSTufPLgEFjGSteL")
for track in tracks_generator:
  print(track['track']['name'])
```
You don't have to unwrap the Spotify paging object or worry about hitting pagination limits, the library will automatically handle all of this and always use the highest available limit for each paginated request to limit round-trip time.

Endpoints that receive multiple ids usually need to be sent in batches. The library takes care of all that for you so you can simply pass the entire list:
```python
# huge list of 5000 tracks
track_uris = [...] 
api.playlist_tracks_add("my-playlist-id", track_uris)
```

## Mapping
Below is a list of supported endpoints and their corresponding method names. Argument positioning and naming as explained previously:
### Albums 
[Get Multiple Albums](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-multiple-albums) -> `albums`

[Get an Album](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-an-album) -> `album`

[Get an Album's Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-an-albums-tracks) -> `album_tracks`

### Artists
[Get Multiple Artists](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-multiple-artists) -> `artists`

[Get an Artist](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-an-artist) -> `artist`

[Get an Artist's Top Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-an-artists-top-tracks) -> `artist_top_tracks`

[Get an Artist's Related Artists](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-an-artists-related-artists) -> `artist_related_artists`

[Get an Artist's Albums](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-an-artists-albums) -> `artist_albums`

### Browse
[Get All New Releases](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-new-releases) -> `new_releases`

[Get All Featured Playlists](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-featured-playlists) -> `featured_playlists`

[Get All Categories](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-categories) -> `categories`

[Get a Category](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-a-category) -> `category`

[Get a Category's Playlists](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-a-categories-playlists) -> `category_playlists`

[Get Recommendations](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-recommendations) -> `recommendations`

### Episodes
[Get Multiple Episodes](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-multiple-episodes) -> `episodes`

[Get an Episode](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-an-episode) -> `episode`

### Follow
[Follow a Playlist](https://developer.spotify.com/documentation/web-api/reference#endpoint-follow-playlist) -> `follow_playlist`

[Unfollow Playlist](https://developer.spotify.com/documentation/web-api/reference#endpoint-unfollow-playlist) -> `unfollow_playlist`

[Check if Users Follow a Playlist](https://developer.spotify.com/documentation/web-api/reference#endpoint-check-if-user-follows-playlist) -> `is_playlist_followed`

[Get User's Followed Artists](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-followed) -> `artists_followed`

[Follow Artists or Users](https://developer.spotify.com/documentation/web-api/reference#endpoint-follow-artists-users) -> `follow_artists`, `follow_users`

[Unfollow Artists or Users](https://developer.spotify.com/documentation/web-api/reference#endpoint-unfollow-artists-users) -> `unfollow_artists`, `unfollow_users`

[Get Following State for Artists/Users](https://developer.spotify.com/documentation/web-api/reference#endpoint-check-current-user-follows) -> `is_following_artists`, `is_following_users`

### Library
[Get User's Saved Albums](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-users-saved-albums) -> `saved_albums`

[Save Albums for Current User](https://developer.spotify.com/documentation/web-api/reference#endpoint-save-albums-user) -> `saved_albums_add`

[Remove Albums for Current User](https://developer.spotify.com/documentation/web-api/reference#endpoint-remove-albums-user) -> `saved_albums_remove`

[Check User's Saved Albums](https://developer.spotify.com/documentation/web-api/reference#endpoint-check-users-saved-albums) -> `are_albums_saved`

[Get User's Saved Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-users-saved-tracks) -> `saved_tracks`

[Save Tracks for User](https://developer.spotify.com/documentation/web-api/reference#endpoint-save-tracks-user) -> `saved_tracks_add`

[Remove User's Saved Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-remove-tracks-user) -> `saved_tracks_remove`

[Check User's Saved Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-check-users-saved-tracks) -> `are_tracks_saved`

[Get User's Saved Shows](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-users-saved-shows) -> `saved_shows`

[Save Shows for Current User](https://developer.spotify.com/documentation/web-api/reference#endpoint-save-shows-user) -> `saved_shows_add`

[Remove User's Saved Shows](https://developer.spotify.com/documentation/web-api/reference#endpoint-remove-shows-user) -> `saved_shows_remove`

[Check User's Saved Shows](https://developer.spotify.com/documentation/web-api/reference#endpoint-check-users-saved-shows) -> `are_shows_saved`

### Personalization
[Get a User's Top Artists and Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-users-top-artists-and-tracks) -> `top_artists`, `top_tracks`

### Playlists
[Get a List of Current User's Playlists](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-a-list-of-current-users-playlists) -> `playlists`

[Get a List of a User's Playlists](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-list-users-playlists) -> `playlists` (w/ user ID as parameter)

[Create a Playlist](https://developer.spotify.com/documentation/web-api/reference#endpoint-create-playlist) -> `playlists_add`

[Get a Playlist](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-playlist) -> `playlist`

[Change a Playlist's Details](https://developer.spotify.com/documentation/web-api/reference#endpoint-change-playlist-details) -> `playlist_edit`

[Get a Playlist's Items](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-playlists-tracks) -> `playlist_tracks`

[Add Items to a Playlist](https://developer.spotify.com/documentation/web-api/reference#endpoint-add-tracks-to-playlist) -> `playlist_tracks_add`

[Reorder or Replace a Playlist's Items](https://developer.spotify.com/documentation/web-api/reference#endpoint-reorder-or-replace-playlists-tracks) -> `playlist_tracks_reorder`, `playlist_tracks_replace`

[Remove Items from a Playlist](https://developer.spotify.com/documentation/web-api/reference#endpoint-remove-tracks-playlist) -> `playlist_tracks_remove`

[Get a Playlist Cover Image](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-playlist-cover) -> `playlist_images`

[Upload a Custom Playlist Cover Image](https://developer.spotify.com/documentation/web-api/reference#endpoint-upload-custom-playlist-cover) -> `playlist_image_add` (w/ image binary as a file descriptor, e.g. through `open`)

### Search
[Search for an Item](https://developer.spotify.com/documentation/web-api/reference#endpoint-search) -> `search_albums`, `search_artists`, `search_playlists`, `search_tracks`, `search_shows`

### Shows
[Get Multiple Shows](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-multiple-shows) -> `shows`

[Get a Show](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-a-show) -> `show`

[Get a Show's Episodes](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-a-shows-episodes) -> `show_episodes`

### Tracks
[Get Several Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-several-tracks) -> `tracks`

[Get a Track](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-track) -> `track`

[Get Audio Features for Several Tracks](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-several-audio-features) -> `tracks_audio_features`

[Get Audio Features for a Track](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-audio-features) -> `track_audio_features`

[Get Audio Analysis for a Track](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-audio-analysis) -> `track_audio_analysis`

### User Profile
[Get Current User's Profile](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-current-users-profile) -> `profile`

[Get a User's Profile](https://developer.spotify.com/documentation/web-api/reference#endpoint-get-users-profile) -> `profile` (w/ user ID as param)


## Convenience methods
I've added a few additional convenience methods:

`playlist_track_objs`, `saved_album_objs`, `saved_show_objs`, `saved_track_objs`

These break the contract that you always get the exact JSON response from Spotify and return the inner objects, omitting any additional metadata in the outer object. As an example, these do the same thing:
```python
for track in api.playlist_tracks("1SCHh6WSTufPLgEFjGSteL"):
  print(track['track']['name'])
```
```python
for track in api.playlist_track_objs("1SCHh6WSTufPLgEFjGSteL"):
  print(track['name'])
```

## Direct API access (experimental)
You can use this library purely as an authentication wrapper and send direct requests to the Spotify API. Call the `get`, `post`, `put` and `delete` methods on the wrapper instance with parameters similar to what you would use in [Requests](https://2.python-requests.org/en/master/user/quickstart/#make-a-request), namely `params`, `data`, `json` and `headers`. You will then get back an instance of `http.client.HTTPResponse` (in Python 3.x), which you can handle as you like. Example:
```python
import json
import spotify

api = spotify.SpotifyAPI()
response = api.get("playlists/2pFB0I2SvMbsPHZrfRfbZL")
response_json = json.loads(response.read())
print(response_json['name'])
```
These are used under the hood by the wrapper methods, so are fairly well tested, but you will have to handle URL/parameter construction and response/pagination handling by yourself. 

----
## Testing
Full integration tests are availble in `tests`, running against a real Spotify user. You need to set up the `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET` and `SPOTIFY_REFRESH_TOKEN` environment variables as explained in [Authorization](#authorization). 

Then, from root directory:
```bash
python -m unittest
```
