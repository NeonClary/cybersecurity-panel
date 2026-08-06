"""Unit tests for user knowledge fact upsert / summary selection."""

import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

from app.core import user_knowledge as uk


FAKE_USER_ID = ObjectId()


def _mock_db_store():
    """In-memory collection mocks for user_facts / user_summaries."""
    facts: list = []
    summaries: list = []

    facts_coll = MagicMock()
    summaries_coll = MagicMock()
    profiles_coll = MagicMock()

    async def facts_find_one(query):
        for d in facts:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    async def facts_insert_one(doc):
        facts.append(dict(doc))
        return MagicMock(inserted_id=doc.get("_id"))

    async def facts_update_one(query, update, upsert=False):
        for d in facts:
            if all(d.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    d.update(update["$set"])
                return MagicMock(matched_count=1, modified_count=1)
        if upsert and "$set" in update:
            new_doc = {"_id": ObjectId()}
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            new_doc.update(update["$set"])
            facts.append(new_doc)
        return MagicMock(matched_count=0, modified_count=0)

    async def facts_delete_many(query):
        before = len(facts)
        keep = []
        for d in facts:
            if all(d.get(k) == v for k, v in query.items()):
                continue
            keep.append(d)
        facts.clear()
        facts.extend(keep)
        return MagicMock(deleted_count=before - len(facts))

    def facts_find(query):
        matched = [
            dict(d)
            for d in facts
            if all(d.get(k) == v for k, v in query.items())
        ]
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=matched)
        return cursor

    facts_coll.find_one = AsyncMock(side_effect=facts_find_one)
    facts_coll.insert_one = AsyncMock(side_effect=facts_insert_one)
    facts_coll.update_one = AsyncMock(side_effect=facts_update_one)
    facts_coll.delete_many = AsyncMock(side_effect=facts_delete_many)
    facts_coll.find = MagicMock(side_effect=facts_find)

    async def summaries_find_one(query):
        for d in summaries:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    async def summaries_update_one(query, update, upsert=False):
        for d in summaries:
            if all(d.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    d.update(update["$set"])
                return MagicMock(matched_count=1, modified_count=1)
        if upsert:
            new_doc = {"_id": ObjectId()}
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            if "$set" in update:
                new_doc.update(update["$set"])
            summaries.append(new_doc)
        return MagicMock(matched_count=0, modified_count=0)

    summaries_coll.find_one = AsyncMock(side_effect=summaries_find_one)
    summaries_coll.update_one = AsyncMock(side_effect=summaries_update_one)

    profiles_coll.find_one = AsyncMock(return_value={
        "user_id": FAKE_USER_ID,
        "cyber_role": "SOC analyst",
        "knowledge_level": "practitioner",
    })

    db = MagicMock()
    db.user_profiles = profiles_coll

    def _getitem(name):
        if name == "user_facts":
            return facts_coll
        if name == "user_summaries":
            return summaries_coll
        raise KeyError(name)

    db.__getitem__ = MagicMock(side_effect=_getitem)
    db.user_facts = facts_coll
    db.user_summaries = summaries_coll

    return db, facts, summaries


class TestShouldRegenerate(unittest.TestCase):
    def test_first_message_false(self):
        self.assertFalse(uk.should_regenerate_after_chat(1))
        self.assertFalse(uk.should_regenerate_after_chat(0))

    def test_later_messages_true(self):
        self.assertTrue(uk.should_regenerate_after_chat(2))
        self.assertTrue(uk.should_regenerate_after_chat(10))


class TestSmallContextProviders(unittest.TestCase):
    def test_vllm_and_ollama_are_small(self):
        self.assertTrue(uk.is_small_context_provider("vllm"))
        self.assertTrue(uk.is_small_context_provider("ollama"))

    def test_openai_gemini_are_large(self):
        self.assertFalse(uk.is_small_context_provider("openai"))
        self.assertFalse(uk.is_small_context_provider("gemini"))


class TestUpsertInferredFact(unittest.TestCase):
    def test_insert_then_update_same_key(self):
        db, facts, _summaries = _mock_db_store()

        with patch("app.core.user_knowledge.get_database", return_value=db):
            first = asyncio.run(
                uk.upsert_inferred_fact(
                    FAKE_USER_ID,
                    category="person",
                    key="cyber_role",
                    value="student",
                    confidence=0.6,
                    evidence="I'm a student",
                )
            )
            self.assertEqual(len(facts), 1)
            self.assertEqual(first["value"], "student")
            self.assertEqual(first["source"], "inferred")

            second = asyncio.run(
                uk.upsert_inferred_fact(
                    FAKE_USER_ID,
                    category="person",
                    key="cyber_role",
                    value="SOC analyst",
                    confidence=0.9,
                    evidence="I work in a SOC",
                )
            )
            self.assertEqual(len(facts), 1, "same inferred key must not duplicate")
            self.assertEqual(second["value"], "SOC analyst")
            self.assertEqual(facts[0]["value"], "SOC analyst")
            self.assertEqual(facts[0]["_id"], first["_id"])

    def test_stated_same_key_not_overwritten(self):
        db, facts, _ = _mock_db_store()
        stated_id = ObjectId()
        facts.append({
            "_id": stated_id,
            "user_id": FAKE_USER_ID,
            "category": "person",
            "key": "cyber_role",
            "value": "Manager",
            "source": "stated",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })

        with patch("app.core.user_knowledge.get_database", return_value=db):
            inferred = asyncio.run(
                uk.upsert_inferred_fact(
                    FAKE_USER_ID,
                    category="person",
                    key="cyber_role",
                    value="director",
                    confidence=0.5,
                )
            )
            self.assertEqual(len(facts), 2)
            stated = next(d for d in facts if d["source"] == "stated")
            self.assertEqual(stated["value"], "Manager")
            self.assertEqual(inferred["source"], "inferred")
            self.assertEqual(inferred["value"], "director")


class TestExtractFactsDedup(unittest.TestCase):
    def test_extract_upserts_by_key(self):
        db, facts, _ = _mock_db_store()
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value=(
                '{"facts":[{"category":"organization","key":"org_size",'
                '"value":"200 employees","confidence":0.8,"evidence":"200-person"}]}'
            )
        )

        with patch("app.core.user_knowledge.get_database", return_value=db):
            first = asyncio.run(
                uk.extract_facts_from_message(FAKE_USER_ID, "We have 200 people", llm)
            )
            self.assertEqual(len(first), 1)
            self.assertEqual(len(facts), 1)

            llm.generate = AsyncMock(
                return_value=(
                    '{"facts":[{"category":"organization","key":"org_size",'
                    '"value":"250 employees","confidence":0.9}]}'
                )
            )
            second = asyncio.run(
                uk.extract_facts_from_message(FAKE_USER_ID, "Actually 250 staff", llm)
            )
            self.assertEqual(len(second), 1)
            self.assertEqual(len(facts), 1)
            self.assertEqual(facts[0]["value"], "250 employees")


class TestSummarySelection(unittest.TestCase):
    def test_get_summary_short_vs_long(self):
        db, _facts, summaries = _mock_db_store()
        summaries.append({
            "_id": ObjectId(),
            "user_id": FAKE_USER_ID,
            "short": "Short brief",
            "long": "Long detailed brief with history",
            "generated_at": datetime.utcnow(),
            "version": 1,
        })

        with patch("app.core.user_knowledge.get_database", return_value=db):
            short = asyncio.run(uk.get_summary_for_provider(FAKE_USER_ID, True))
            long = asyncio.run(uk.get_summary_for_provider(FAKE_USER_ID, False))
            by_vllm = asyncio.run(uk.get_summary_for_provider(FAKE_USER_ID, "vllm"))
            by_openai = asyncio.run(uk.get_summary_for_provider(FAKE_USER_ID, "openai"))

        self.assertEqual(short, "Short brief")
        self.assertEqual(long, "Long detailed brief with history")
        self.assertEqual(by_vllm, "Short brief")
        self.assertEqual(by_openai, "Long detailed brief with history")

    def test_regenerate_stores_versions(self):
        db, _facts, summaries = _mock_db_store()
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value='{"short":"S1","long":"L1 longer text"}'
        )

        with patch("app.core.user_knowledge.get_database", return_value=db):
            doc1 = asyncio.run(uk.regenerate_summaries(FAKE_USER_ID, llm))
            self.assertEqual(doc1["short"], "S1")
            self.assertEqual(doc1["long"], "L1 longer text")
            self.assertEqual(doc1["version"], 1)

            llm.generate = AsyncMock(
                return_value='{"short":"S2","long":"L2"}'
            )
            doc2 = asyncio.run(uk.regenerate_summaries(FAKE_USER_ID, llm))
            self.assertEqual(doc2["version"], 2)
            self.assertEqual(len(summaries), 1)
            self.assertEqual(summaries[0]["short"], "S2")


if __name__ == "__main__":
    unittest.main()
