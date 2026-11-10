"""Unit tests for the SQLite Mongo-shim filter operators."""

import unittest
from datetime import datetime, timedelta

from bson import ObjectId

from app.core.db import _matches


class TestFilterOperators(unittest.TestCase):
    def setUp(self):
        self.uid = ObjectId()
        self.doc = {"_id": ObjectId(), "user_id": self.uid, "is_active": True,
                    "created_at": datetime(2026, 11, 9, 12, 0)}

    def test_exists_false_matches_missing_field(self):
        self.assertTrue(_matches(self.doc, {"user_id": self.uid, "deleted_at": {"$exists": False}}))
        self.assertFalse(_matches({**self.doc, "deleted_at": datetime.utcnow()},
                                  {"deleted_at": {"$exists": False}}))

    def test_exists_true(self):
        self.assertTrue(_matches(self.doc, {"is_active": {"$exists": True}}))
        self.assertFalse(_matches(self.doc, {"deleted_at": {"$exists": True}}))

    def test_ne_and_nin(self):
        self.assertTrue(_matches(self.doc, {"is_active": {"$ne": False}}))
        self.assertTrue(_matches({"x": 1}, {"is_active": {"$ne": False}}))
        self.assertFalse(_matches({"is_active": False}, {"is_active": {"$ne": False}}))
        self.assertTrue(_matches(self.doc, {"is_active": {"$nin": [False]}}))

    def test_in_still_works(self):
        self.assertTrue(_matches(self.doc, {"user_id": {"$in": [self.uid]}}))
        self.assertFalse(_matches(self.doc, {"user_id": {"$in": [ObjectId()]}}))

    def test_comparisons_and_or(self):
        since = self.doc["created_at"] - timedelta(hours=1)
        self.assertTrue(_matches(self.doc, {"created_at": {"$gt": since}}))
        self.assertFalse(_matches(self.doc, {"created_at": {"$lt": since}}))
        self.assertTrue(_matches(self.doc, {"$or": [{"updated_at": {"$gt": since}},
                                                    {"created_at": {"$gte": since}}]}))
        self.assertFalse(_matches(self.doc, {"created_at": {"$gt": "not-a-date"}}))

    def test_plain_dict_value_is_equality(self):
        self.assertTrue(_matches({"meta": {"a": 1}}, {"meta": {"a": 1}}))

    def test_unknown_operator_raises(self):
        with self.assertRaises(ValueError):
            _matches(self.doc, {"title": {"$regex": "x"}})


if __name__ == "__main__":
    unittest.main()
