import sqlite3
import tempfile
import unittest
from pathlib import Path

from mac.play_history import PlayHistory


class PlayHistoryTests(unittest.TestCase):
    def test_get_recent_filepaths_returns_recent_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = PlayHistory(Path(tmp) / "history.db")
            recent_path = "/tmp/recent.flac"
            old_path = "/tmp/old.flac"

            history.record_play(recent_path)
            with sqlite3.connect(history.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO plays (filepath, played_at)
                    VALUES (?, datetime('now', '-8 hours'))
                    """,
                    (old_path,),
                )

            self.assertIn(recent_path, history.get_recent_filepaths(hours=4))
            self.assertNotIn(old_path, history.get_recent_filepaths(hours=4))


if __name__ == "__main__":
    unittest.main()
