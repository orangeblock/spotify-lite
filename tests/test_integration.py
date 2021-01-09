import os
import time
import types
import spotify
import unittest

###
# Integration tests that run without any mocking, directly against
# a live Spotify account. Environment variables must be set
# for a valid client application as well as a refresh token for
# a user that has granted ALL permissions to that application.
# Refer to `setUpClass` for names of env. variables.
#
# Tests are designed to leave the account unaltered however a test
# failure might leave leftover data which would require manual intervention.
# Refer to test output on how to correct it.
class ApiTest(unittest.TestCase):
    albums = [
        # Jon Hopkins - Immunity
        '1rxWlYQcH945S3jpIMYR35',
        # Cunninlynguists - Strange Journey Vol. 3
        '0bEZDwWaYrRZNfatVRsoTJ',
        # Echospace - Liumin
        '2sBtwfqFvOdUkRxs741VBW'
    ]
    artists = [
        # Jon Hopkins
        "7yxi31szvlbwvKq9dYOmFI",
        # Cunninlynguists
        "7EA0bLf8dXCIUkwC3lnaJa",
        # Deepchord presents: Echospace
        "6mw8tTkjJtQs6kT1V8G5fI"
    ]

    @classmethod
    def setUpClass(self):
        # Required environment variables, set these before running!
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        refresh_token = os.getenv('SPOTIFY_REFRESH_TOKEN')

        user = spotify.SpotifyUser(refresh_token=refresh_token)
        self.api = spotify.SpotifyAPI(client_id, client_secret, user=user)

    def _test_album(self):
        x = self.api.album(self.albums[0])
        self.assertEqual(x['id'], self.albums[0])

    def _test_albums(self):
        xs = self.api.albums(self.albums)
        self.assertIsInstance(xs, types.GeneratorType)
        ids = list(map(lambda x: x['id'], list(xs)))
        self.assertEqual(len(ids), len(self.albums))
        self.assertSetEqual(set(ids), set(self.albums))

    def _test_album_tracks(self):
        xs = self.api.album_tracks(self.albums[0])
        self.assertIsInstance(xs, types.GeneratorType)
        tracks = list(xs)
        artists = list(map(lambda x: x['artists'][0]['id'], tracks))
        self.assertNotEqual(0, len(artists))
        self.assertSetEqual(set([self.artists[0]]), set(artists))

    def _test_artist(self):
        x = self.api.artist(self.artists[0])
        self.assertEqual(x['id'], self.artists[0])

    def _test_artists(self):
        xs = self.api.artists(self.artists)
        self.assertIsInstance(xs, types.GeneratorType)
        ids = list(map(lambda x: x['id'], list(xs)))
        self.assertEqual(len(ids), len(self.artists))
        self.assertSetEqual(set(ids), set(self.artists))

    def test_artist_albums(self):
        pass

    def test_artist_top_tracks(self):
        pass

    def test_artist_related_artists(self):
        pass

    def test_category(self):
        pass

    def test_categories(self):
        pass

    def test_category_playlists(self):
        pass

    def test_featured_playlists(self):
        pass

    def test_new_releases(self):
        pass

    def test_recommendations(self):
        pass

    def test_episode(self):
        pass

    def test_episodes(self):
        pass

    def test_is_following_artists(self):
        pass

    def test_is_following_users(self):
        pass

    def test_is_playlist_followed(self):
        pass

    def test_follow_unfollow_artists(self):
        pass

    def test_follow_unfollow_users(self):
        pass

    def test_follow_unfollow_playlist(self):
        pass

    def test_artists_followed(self):
        pass
