import tempfile
import unittest
from pathlib import Path

from mac.playlist_intake import select_next_track


class PlaylistIntakeTests(unittest.TestCase):
    def test_select_next_track_skips_missing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first = tmp_path / "first.wav"
            second = tmp_path / "second.wav"
            third = tmp_path / "third.wav"
            first.write_bytes(b"")
            third.write_bytes(b"")

            tracks = [str(first), str(second), str(third)]

            self.assertEqual(select_next_track(tracks, str(first)), str(third))

    def test_select_next_track_wraps_to_existing_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first = tmp_path / "first.wav"
            second = tmp_path / "second.wav"
            third = tmp_path / "third.wav"
            first.write_bytes(b"")
            third.write_bytes(b"")

            tracks = [str(first), str(second), str(third)]

            self.assertEqual(select_next_track(tracks, str(third)), str(first))


if __name__ == "__main__":
    unittest.main()
