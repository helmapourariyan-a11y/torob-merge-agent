import unittest

from agent import review


class ReviewTests(unittest.TestCase):
    def test_cable_length_mismatch(self):
        result = review({"kind": "merge", "category": "cable",
                         "left": {"length": "۱ متر"}, "right": {"length": "۲ متر"}})
        self.assertEqual(result["decision"], "reject")

    def test_cable_length_requires_review_before_inspecting_images(self):
        result = review({"kind": "merge", "category": "cable",
                         "left": {"length": "۱ متر"}, "right": {}})
        self.assertEqual(result["decision"], "review")

    def test_matching_verified_phone_case(self):
        product = dict(title="قاب گوشی", brand="X", model="C1", structure="ژله‌ای",
                       quantity="1", condition="نو", phone_model="A1",
                       camera_cover="open", magsafe="no")
        result = review(dict(kind="merge", category="phone_case", left=product, right=product,
                             images_checked=True, cluster_checked=True, single_model_confirmed=True))
        self.assertEqual(result["decision"], "approve")

    def test_split_groups_and_duplicate_ids(self):
        request = dict(kind="split", cluster_checked=True,
                       verified_split_groups=[["p1", "p2"], ["p3"]])
        self.assertEqual(review(request)["decision"], "split")
        request["verified_split_groups"].append(["p1"])
        self.assertEqual(review(request)["decision"], "review")

    def test_delete_needs_human_review(self):
        self.assertEqual(review({"kind": "delete"})["decision"], "review")
