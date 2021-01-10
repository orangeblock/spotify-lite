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
        "6mw8tTkjJtQs6kT1V8G5fI",
        # Eminem
        "7dGJo4pcD2V6oG8kP0tJRR"
    ]
    categories = [
        'party'
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

    def _test_artist_albums(self):
        # should contain all release types
        xs = self.api.artist_albums(self.artists[1])
        self.assertIsInstance(xs, types.GeneratorType)
        releases = list(xs)
        _all_types = set(['album', 'single', 'compilation'])
        _all_groups = set(['album', 'single', 'appears_on'])
        release_types = list(map(lambda x: x['album_type'], releases))
        release_groups = list(map(lambda x: x['album_group'], releases))
        self.assertSetEqual(_all_types, set(release_types))
        self.assertSetEqual(_all_groups, set(release_groups))
        # should only contain singles
        xs = self.api.artist_albums(
            self.artists[1], include_groups=['single']
        )
        releases = list(xs)
        release_types = list(map(lambda x: x['album_type'], releases))
        release_groups = list(map(lambda x: x['album_group'], releases))
        self.assertEqual(['single'], list(set(release_types)))
        self.assertEqual(['single'], list(set(release_groups)))
        # should contain singles and albums
        xs = self.api.artist_albums(
            self.artists[1], include_groups=['single', 'album']
        )
        releases = list(xs)
        release_types = list(map(lambda x: x['album_type'], releases))
        release_groups = list(map(lambda x: x['album_group'], releases))
        self.assertSetEqual(set(['single', 'album']), set(release_types))
        self.assertSetEqual(set(['single', 'album']), set(release_groups))

    def _test_artist_top_tracks(self):
        xs = self.api.artist_top_tracks(self.artists[0])
        self.assertIsInstance(xs, types.GeneratorType)
        # ensure all tracks have og artist in artist list
        artist_lists = list(map(lambda x: x['artists'], list(xs)))
        self.assertGreater(len(artist_lists), 0)
        for l in artist_lists:
            self.assertIn(
                self.artists[0], list(map(lambda x: x['id'], l))
            )

    def _test_artist_related_artists(self):
        xs = self.api.artist_related_artists(self.artists[0])
        self.assertIsInstance(xs, types.GeneratorType)
        obj_types = list(map(lambda x: x['type'], list(xs)))
        self.assertGreater(len(obj_types), 0)
        self.assertListEqual(['artist'], list(set(obj_types)))

    def _test_category(self):
        x = self.api.category(self.categories[0])
        self.assertEqual(x['id'], self.categories[0])

    def _test_categories(self):
        xs = self.api.categories()
        self.assertIsInstance(xs, types.GeneratorType)
        # no way to tell if objects are categories without fetching
        # everything and checking for the hardcoded one so instead
        # we just check we at least pull something.
        cats = [next(xs) for _ in range(10)]
        self.assertEqual(10, len(cats))

    def _test_category_playlists(self):
        xs = self.api.category_playlists(self.categories[0])
        self.assertIsInstance(xs, types.GeneratorType)
        pls = [next(xs) for _ in range(2)]
        self.assertEqual(2, len(pls))
        self.assertEqual(
            ['playlist'], list(set(map(lambda x: x['type'], pls)))
        )

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
