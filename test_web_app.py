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

    def test_official_recycling_centres_cover_overpass_outage(self):
        with patch("web_app.get_bins", return_value=None):
            response = self.client.post("/nearby-bins", json={
                "latitude": 53.3498,
                "longitude": -6.2603,
                "bin_type": "recycling",
            })

        response_data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data["dataSource"], "Dublin City Council")
        self.assertGreaterEqual(len(response_data["nearestBins"]), 1)
        self.assertEqual(
            response_data["nearestBins"][0]["bin"]["tags"]["amenity"],
            "recycling",
        )

    def test_local_bottle_banks_cover_overpass_outage(self):
        with patch("web_app.get_bins", return_value=None):
            response = self.client.post("/nearby-bins", json={
                "latitude": 53.3210,
                "longitude": -6.2666,
                "bin_type": "recycling",
            })

        response_data = response.get_json()
        nearest = response_data["nearestBins"][0]

        self.assertEqual(response.status_code, 200)
        self.assertLess(nearest["distance"], 100)
        self.assertEqual(
            nearest["bin"]["tags"]["name"],
            "Tesco Car Park Rathmines",
        )
        self.assertEqual(
            nearest["bin"]["tags"]["source"],
            "Dublin City Council / Glassco",
        )

    def test_live_osm_duplicate_does_not_repeat_official_bottle_bank(self):
        live_osm_bin = {
            "id": 564430856,
            "lat": 53.3210247,
            "lon": -6.2665921,
            "tags": {"amenity": "recycling"},
        }

        official_bins = web_app.get_dcc_recycling_bins_nearby(
            53.3210,
            -6.2666,
        )
        merged = web_app.merge_recycling_bins(
            [live_osm_bin],
            official_bins,
        )

        nearby = [
            bin_item for bin_item in merged
            if web_app.distance_metres(
                53.3210,
                -6.2666,
                bin_item["lat"],
                bin_item["lon"],
            ) < 100
        ]

        self.assertEqual(len(nearby), 1)


if __name__ == "__main__":
    unittest.main()
