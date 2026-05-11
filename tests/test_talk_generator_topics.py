import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mac.content_generator import talk_generator
from mac.schedule import load_schedule


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TalkTopicTests(unittest.TestCase):
    def test_select_topic_honors_avoid_topics(self):
        with patch.object(random, "choice", side_effect=lambda items: items[0]):
            topic = talk_generator.select_topic(
                "music_history",
                "deep_dive",
                avoid_topics=[
                    "The secret history of the B-side",
                    "How geography shaped sound",
                    "The lost art of the album sequence",
                ],
            )

        self.assertNotIn("B-side", topic)
        self.assertNotIn("geography", topic)
        self.assertNotIn("album sequence", topic)

    def test_select_topic_honors_slot_slug_avoidance(self):
        avoided = talk_generator.slugify_topic("The secret history of the B-side")

        with patch.object(random, "choice", side_effect=lambda items: items[0]):
            topic = talk_generator.select_topic(
                "music_history",
                "deep_dive",
                avoid_slugs={avoided},
            )

        self.assertNotEqual(topic, "The secret history of the B-side - when the throwaway becomes the classic")

    def test_slot_topic_slugs_reads_existing_segment_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            show_id = "sonic_archaeology"
            slot = "2026-05-06_0900"
            slot_dir = output_dir / show_id / slot
            slot_dir.mkdir(parents=True)
            filename = "deep_dive_the_golden_age_of_the_record_s_20260505_162804.wav"
            (slot_dir / filename).write_bytes(b"")

            with patch.object(talk_generator, "OUTPUT_DIR", output_dir):
                slugs = talk_generator.slot_topic_slugs(show_id, slot)

        self.assertEqual(slugs, {"the_golden_age_of_the_record_s"})

    def test_station_talk_topic_pools_are_complete_and_separate(self):
        klod = load_schedule(PROJECT_ROOT / "config" / "schedule.yaml")
        cdex = load_schedule(PROJECT_ROOT / "config" / "cdex_schedule.yaml")

        klod_focuses = {show.topic_focus for show in klod.shows.values()}
        cdex_focuses = {show.topic_focus for show in cdex.shows.values()}
        configured_focuses = klod_focuses | cdex_focuses

        self.assertEqual(configured_focuses - set(talk_generator.TOPIC_POOLS), set())
        self.assertTrue(klod_focuses.isdisjoint(cdex_focuses))


if __name__ == "__main__":
    unittest.main()
