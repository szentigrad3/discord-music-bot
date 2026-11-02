"""Queue index validation regression tests."""
import unittest
from bot.music.player import MusicPlayer


class QueuePositionTests(unittest.TestCase):
    def setUp(self):
        self.player = object.__new__(MusicPlayer)
        self.player.tracks = ['first', 'second', 'third']

    def test_move_first_to_last(self):
        self.player.move_track(1, 3)
        self.assertEqual(self.player.tracks, ['second', 'third', 'first'])

    def test_move_last_to_first(self):
        self.player.move_track(3, 1)
        self.assertEqual(self.player.tracks, ['third', 'first', 'second'])

    def test_noop_move(self):
        self.player.move_track(2, 2)
        self.assertEqual(self.player.tracks, ['first', 'second', 'third'])

    def test_invalid_positions_do_not_mutate_queue(self):
        for source, dest in ((0, 1), (-1, 1), (1, 0), (1, 4), (4, 1)):
            with self.subTest(source=source, dest=dest):
                with self.assertRaises(IndexError):
                    self.player.move_track(source, dest)
                self.assertEqual(self.player.tracks, ['first', 'second', 'third'])

    def test_empty_queue_rejects_move(self):
        self.player.tracks = []
        with self.assertRaises(IndexError):
            self.player.move_track(1, 1)
