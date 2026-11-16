import unittest
from unittest.mock import patch

import web_app


class RecyclingSearchTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config["TESTING"] = True
        self.client = web_app.app.test_client()

    def test_recycling_query_uses_wider_nwr_search(self):
        query = web_app.build_bins_query("recycling", 53.34, -6.26)

        self.assertIn('nwr["amenity"="recycling"]', query)
        self.assertIn("around:10000", query)
        self.assertIn("out center", query)

    def test_way_centres_are_normalised_for_distance_calculation(self):
        bins = web_app.normalise_osm_bins([
            {
                "type": "way",
                "id": 123,
                "center": {"lat": 53.35, "lon": -6.27},
                "tags": {"amenity": "recycling"},
            }
        ])

        self.assertEqual(bins[0]["lat"], 53.35)
        self.assertEqual(bins[0]["lon"], -6.27)

    def test_recycling_point_is_not_deduplicated_against_public_bin(self):
        recycling_bin = {
            "lat": 53.350001,
            "lon": -6.270001,
            "tags": {"amenity": "recycling"},
        }
        public_bin = {
            "lat": 53.35,
            "lon": -6.27,
            "tags": {"amenity": "waste_basket"},
        }

        merged = web_app.merge_public_bins([recycling_bin], [public_bin])

        self.assertEqual(merged, [public_bin, recycling_bin])

    def test_recycling_search_does_not_use_public_bin_cache(self):
        recycling_bin = {
            "type": "node",
            "id": 456,
            "lat": 53.345,
            "lon": -6.265,
            "tags": {"amenity": "recycling"},
        }

        with patch("web_app.get_bins") as get_bins:
            get_bins.return_value = {
                "source": "live",
                "elements": [recycling_bin],
            }

            response = self.client.post("/find-bin", data={
                "latitude": "53.34",
                "longitude": "-6.26",
                "bin_type": "recycling",
            })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_bins.call_args.kwargs["allow_cache"])
        self.assertIn(
            'nwr["amenity"="recycling"]',
            get_bins.call_args.args[1],
        )

    def test_locate_again_preserves_recycling_filter(self):
        recycling_bin = {
            "type": "node",
            "id": 789,
            "lat": 53.345,
            "lon": -6.265,
            "tags": {"amenity": "recycling"},
        }

        with patch("web_app.get_bins") as get_bins:
            get_bins.return_value = {
                "source": "live",
                "elements": [recycling_bin],
            }

            response = self.client.post("/nearby-bins", json={
                "latitude": 53.34,
                "longitude": -6.26,
                "bin_type": "recycling",
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["binType"], "recycling")
        self.assertEqual(
            response.get_json()["nearestBins"][0]["bin"]["tags"]["amenity"],
            "recycling",
        )
        self.assertFalse(get_bins.call_args.kwargs["allow_cache"])


if __name__ == "__main__":
    unittest.main()
