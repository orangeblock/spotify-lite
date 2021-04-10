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
        '1rxWlYQcH945S3jpIMYR35',
        '0bEZDwWaYrRZNfatVRsoTJ',
        '2sBtwfqFvOdUkRxs741VBW'
    ]
    album_names = [
        "Jon Hopkins - Immunity",
        "Cunninlynguists - Strange Journey Vol. 3",
        "Echospace - Liumin"
    ]
    artists = [
        "7yxi31szvlbwvKq9dYOmFI",
        "7EA0bLf8dXCIUkwC3lnaJa",
        "6mw8tTkjJtQs6kT1V8G5fI",
        "7dGJo4pcD2V6oG8kP0tJRR"
    ]
    artist_names = [
        'Jon Hopkins',
        'Cunninlynguists',
        'Deepchord presents: Echospace',
        'Eminem'
    ]
    categories = [
        'party'
    ]
    shows = [
        '4rOoJ6Egrf8K2IrywzwOMk',
        '3hOAVGZCDEO52OEGiG1ZFR'
    ]
    show_names = [
        'The Joe Rogan Experience',
        'The Nobody Zone'
    ]
    episodes = [
        # Joe Rogan #1592
        '15p3DpjZeaXCwcXyGTytMj',
        # Joe Rogan #1591
        '6j9JygkIR2MsNLGZA9Suc3',
        # Joe Rogan #1590
        '6JDZgjywtlxWXO7V5NOjOg'
    ]
    users = [
        'particledetector',
        'glennpmcdonald'
    ]
    playlists = [
        '0WDr7WCMndGfhoUwfm0ngS',
    ]
    playlist_names = [
        'The Pulse of Downtempo'
    ]
    tracks = [
        '4uLU6hMCjMI75M1A2tKUQC',
        '5626KdflSKfeDK7RJQfSrE'
    ]
    track_names = [
        'Rick Astley - Never Gonna Give You Up',
        'Nils Frahm - Says'
    ]

    @classmethod
    def setUpClass(self):
        # Required environment variables, set these before running!
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        refresh_token = os.getenv('SPOTIFY_REFRESH_TOKEN')

        user = spotify.SpotifyUser(refresh_token=refresh_token)
        self.api = spotify.SpotifyAPI(client_id, client_secret, user=user)

    def test_album(self):
        x = self.api.album(self.albums[0])
        self.assertEqual(x['id'], self.albums[0])

    def test_albums(self):
        xs = self.api.albums(self.albums)
        self.assertIsInstance(xs, types.GeneratorType)
        ids = list(map(lambda x: x['id'], list(xs)))
        self.assertEqual(len(ids), len(self.albums))
        self.assertSetEqual(set(ids), set(self.albums))

    def test_album_tracks(self):
        xs = self.api.album_tracks(self.albums[0])
        self.assertIsInstance(xs, types.GeneratorType)
        tracks = list(xs)
        artists = list(map(lambda x: x['artists'][0]['id'], tracks))
        self.assertNotEqual(0, len(artists))
        self.assertSetEqual(set([self.artists[0]]), set(artists))

    def test_artist(self):
        x = self.api.artist(self.artists[0])
        self.assertEqual(x['id'], self.artists[0])

    def test_artists(self):
        xs = self.api.artists(self.artists)
        self.assertIsInstance(xs, types.GeneratorType)
        ids = list(map(lambda x: x['id'], list(xs)))
        self.assertEqual(len(ids), len(self.artists))
        self.assertSetEqual(set(ids), set(self.artists))

    def test_artist_albums(self):
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

    def test_artist_top_tracks(self):
        xs = self.api.artist_top_tracks(self.artists[0])
        self.assertIsInstance(xs, types.GeneratorType)
        # ensure all tracks have og artist in artist list
        artist_lists = list(map(lambda x: x['artists'], list(xs)))
        self.assertGreater(len(artist_lists), 0)
        for l in artist_lists:
            self.assertIn(
                self.artists[0], list(map(lambda x: x['id'], l))
            )

    def test_artist_related_artists(self):
        xs = self.api.artist_related_artists(self.artists[0])
        self.assertIsInstance(xs, types.GeneratorType)
        obj_types = list(map(lambda x: x['type'], list(xs)))
        self.assertGreater(len(obj_types), 0)
        self.assertListEqual(['artist'], list(set(obj_types)))

    def test_category(self):
        x = self.api.category(self.categories[0])
        self.assertEqual(x['id'], self.categories[0])

    def test_categories(self):
        xs = self.api.categories()
        self.assertIsInstance(xs, types.GeneratorType)
        # no way to tell if objects are categories without fetching
        # everything and checking for the hardcoded one so instead
        # we just check we at least pull something.
        cats = [next(xs) for _ in range(10)]
        self.assertEqual(10, len(cats))

    def test_category_playlists(self):
        xs = self.api.category_playlists(self.categories[0])
        self.assertIsInstance(xs, types.GeneratorType)
        pls = [next(xs) for _ in range(2)]
        self.assertEqual(2, len(pls))
        self.assertEqual(
            ['playlist'], list(set(map(lambda x: x['type'], pls)))
        )

    def test_featured_playlists(self):
        xs = self.api.featured_playlists()
        self.assertIsInstance(xs, types.GeneratorType)
        pls = [next(xs) for _ in range(5)]
        self.assertEqual(5, len(pls))
        self.assertEqual(
            ['playlist'], list(set(map(lambda x: x['type'], pls)))
        )

    def test_new_releases(self):
        xs = self.api.new_releases()
        self.assertIsInstance(xs, types.GeneratorType)
        albs = [next(xs) for _ in range(5)]
        self.assertEqual(5, len(albs))
        self.assertEqual(
            ['album'], list(set(map(lambda x: x['type'], albs)))
        )

    def test_recommendations(self):
        pass

    def test_episode(self):
        x = self.api.episode(self.episodes[0])
        self.assertEqual(x['id'], self.episodes[0])

    def test_episodes(self):
        xs = self.api.episodes(self.episodes)
        self.assertIsInstance(xs, types.GeneratorType)
        eps = list(xs)
        self.assertEqual(len(eps), 3)
        self.assertSetEqual(
            set(map(lambda x: x['id'], eps)),
            set(self.episodes))

    def test_follow_artists_multi(self):
        """Tests following, unfollowing and querying follow status
        for artists.
        """
        # find if account follows artist initially
        f_xs = [self.artists[0], self.artists[1]]
        f_names = [self.artist_names[0], self.artist_names[1]]
        init_status = list(self.api.is_following_artists(f_xs))
        try:
            # unfollow all currently followed artists
            for i, status in enumerate(init_status):
                if status:
                    self.api.unfollow_artists([f_xs[i]])
            # follow artists
            self.api.follow_artists(f_xs)
            # check follow status
            sts = list(self.api.is_following_artists(f_xs))
            self.assertListEqual(sts, [True, True])
            # check if artists_followed endpoint returns artists
            _all_followed = list(self.api.artists_followed())
            _all_followed_ids = list(map(lambda x: x['id'], _all_followed))
            for _id in f_xs:
                self.assertIn(_id, _all_followed_ids)
            # unfollow one
            self.api.unfollow_artists([f_xs[0]])
            # check follow status
            sts = list(self.api.is_following_artists(f_xs))
            self.assertListEqual(sts, [False, True])
            # reset initial status
            for i, i_st in enumerate(init_status):
                if i_st != sts[i]:
                    if i_st == True:
                        self.api.follow_artists([f_xs[i]])
                    else:
                        self.api.unfollow_artists([f_xs[i]])
            # ensure final state is correct
            final_status = list(self.api.is_following_artists(f_xs))
            self.assertListEqual(init_status, final_status)
        except:
            raise Exception(
                "Potentially invalid account state - follow/unfollow " +
                "status for artists: %s" % (
                    ', '.join(
                        [
                            '%s (%s)' % (f_xs[i], f_names[i])
                            for i in range(len(f_xs))
                        ]
                    )
                ))

    def test_follow_users_multi(self):
        """Tests following, unfollowing and querying follow status
        for users.
        """
        # find if account follows user initially
        f_xs = [self.users[0], self.users[1]]
        init_status = list(self.api.is_following_users(f_xs))
        try:
            # unfollow all currently followed users
            for i, status in enumerate(init_status):
                if status:
                    self.api.unfollow_users([f_xs[i]])
            # follow users
            self.api.follow_users(f_xs)
            # check follow status
            sts = list(self.api.is_following_users(f_xs))
            self.assertListEqual(sts, [True, True])
            # unfollow one
            self.api.unfollow_users([f_xs[0]])
            # check follow status
            sts = list(self.api.is_following_users(f_xs))
            self.assertListEqual(sts, [False, True])
            # reset initial status
            for i, i_st in enumerate(init_status):
                if i_st != sts[i]:
                    if i_st == True:
                        self.api.follow_users([f_xs[i]])
                    else:
                        self.api.unfollow_users([f_xs[i]])
            # ensure final state is correct
            final_status = list(self.api.is_following_users(f_xs))
            self.assertListEqual(init_status, final_status)
        except:
            raise Exception(
                "Potentially invalid account state - follow/unfollow " +
                "status for users: %s" % (
                    ', '.join(
                        [
                            '%s' % f_xs[i]
                            for i in range(len(f_xs))
                        ]
                    )
                ))

    def test_follow_playlist_multi(self):
        """Tests following, unfollowing and querying follow status
        for playlists.
        """
        # find if account follows playlist initially
        profile = self.api.profile()
        init_status = list(self.api.is_playlist_followed(
            self.playlists[0], [profile['id']]
        ))[0]
        try:
            # unfollow playlist if followed
            if init_status:
                self.api.unfollow_playlist(self.playlists[0])
            # follow playlist
            self.api.follow_playlist(self.playlists[0])
            # check follow status
            st = list(self.api.is_playlist_followed(
                self.playlists[0], [profile['id']]
            ))[0]
            self.assertEqual(st, True)
            # unfollow
            self.api.unfollow_playlist(self.playlists[0])
            # check follow status
            st = list(self.api.is_playlist_followed(
                self.playlists[0], [profile['id']]
            ))[0]
            self.assertEqual(st, False)
            # reset initial status
            if init_status != st:
                if init_status == True:
                    self.api.follow_playlist(self.playlists[0])
                else:
                    self.api.unfollow_playlist(self.playlists[0])
            # ensure final state is correct
            final_status = list(self.api.is_playlist_followed(
                self.playlists[0], [profile['id']]
            ))[0]
            self.assertEqual(init_status, final_status)
        except:
            raise Exception(
                "Potentially invalid account state - follow/unfollow " +
                "status for playlist: %s (%s)" % (
                    self.playlists[0], self.playlist_names[0]
                ))

    def test_saved_albums_multi(self):
        """Test saving, removing and listing saved albums"""
        # find if albums are saved initially
        xs = [self.albums[0], self.albums[1]]
        xs_names = [self.album_names[0], self.album_names[1]]
        init_status = list(self.api.are_albums_saved(xs))
        try:
            # delete all currently saved albums
            for i, status in enumerate(init_status):
                if status:
                    self.api.saved_albums_remove([xs[i]])
            # save albums
            self.api.saved_albums_add(xs)
            # check save status
            sts = list(self.api.are_albums_saved(xs))
            self.assertListEqual(sts, [True, True])
            # check general endpoint now that at least 2 are saved
            album_gen = self.api.saved_albums()
            for i in range(2):
                album = next(album_gen)['album']
                self.assertEqual(album['type'], 'album')
            # remove one
            self.api.saved_albums_remove([xs[0]])
            # check save status
            sts = list(self.api.are_albums_saved(xs))
            self.assertListEqual(sts, [False, True])
            # reset initial status
            for i, i_st in enumerate(init_status):
                if i_st != sts[i]:
                    if i_st == True:
                        self.api.saved_albums_add([xs[i]])
                    else:
                        self.api.saved_albums_remove([xs[i]])
            final_status = list(self.api.are_albums_saved(xs))
            self.assertListEqual(init_status, final_status)
        except:
            raise Exception(
                "Potentially invalid account state - saved status " +
                "for albums: %s" % (
                    ', '.join(
                        [
                            '%s (%s)' % (xs[i], xs_names[i])
                            for i in range(len(xs))
                        ]
                    )
                )
            )

    def test_saved_shows_multi(self):
        """Test saving, removing and listing saved shows"""
        # find if shows are saved initially
        xs = [self.shows[0], self.shows[1]]
        xs_names = [self.show_names[0], self.show_names[1]]
        init_status = list(self.api.are_shows_saved(xs))
        try:
            # delete all currently saved shows
            for i, status in enumerate(init_status):
                if status:
                    self.api.saved_shows_remove([xs[i]])
            # save shows
            self.api.saved_shows_add(xs)
            # check save status
            sts = list(self.api.are_shows_saved(xs))
            self.assertListEqual(sts, [True, True])
            # check general endpoint now that at least 2 are saved
            show_gen = self.api.saved_shows()
            for i in range(2):
                show = next(show_gen)['show']
                self.assertEqual(show['type'], 'show')
            # remove one
            self.api.saved_shows_remove([xs[0]])
            # check save status
            sts = list(self.api.are_shows_saved(xs))
            self.assertListEqual(sts, [False, True])
            # reset initial status
            for i, i_st in enumerate(init_status):
                if i_st != sts[i]:
                    if i_st == True:
                        self.api.saved_shows_add([xs[i]])
                    else:
                        self.api.saved_shows_remove([xs[i]])
            final_status = list(self.api.are_shows_saved(xs))
            self.assertListEqual(init_status, final_status)
        except:
            raise Exception(
                "Potentially invalid account state - saved status " +
                "for shows: %s" % (
                    ', '.join(
                        [
                            '%s (%s)' % (xs[i], xs_names[i])
                            for i in range(len(xs))
                        ]
                    )
                )
            )

    def test_saved_tracks_multi(self):
        """Test saving, removing and listing saved tracks"""
        # find if tracks are saved initially
        xs = [self.tracks[0], self.tracks[1]]
        xs_names = [self.track_names[0], self.track_names[1]]
        init_status = list(self.api.are_tracks_saved(xs))
        try:
            # delete all currently saved tracks
            for i, status in enumerate(init_status):
                if status:
                    self.api.saved_tracks_remove([xs[i]])
            # save tracks
            self.api.saved_tracks_add(xs)
            # check save status
            sts = list(self.api.are_tracks_saved(xs))
            self.assertListEqual(sts, [True, True])
            # check general endpoint now that at least 2 are saved
            track_gen = self.api.saved_tracks()
            for i in range(2):
                track = next(track_gen)['track']
                self.assertEqual(track['type'], 'track')
            # remove one
            self.api.saved_tracks_remove([xs[0]])
            # check save status
            sts = list(self.api.are_tracks_saved(xs))
            self.assertListEqual(sts, [False, True])
            # reset initial status
            for i, i_st in enumerate(init_status):
                if i_st != sts[i]:
                    if i_st == True:
                        self.api.saved_tracks_add([xs[i]])
                    else:
                        self.api.saved_tracks_remove([xs[i]])
            final_status = list(self.api.are_tracks_saved(xs))
            self.assertListEqual(init_status, final_status)
        except:
            raise Exception(
                "Potentially invalid account state - saved status " +
                "for tracks: %s" % (
                    ', '.join(
                        [
                            '%s (%s)' % (xs[i], xs_names[i])
                            for i in range(len(xs))
                        ]
                    )
                )
            )
