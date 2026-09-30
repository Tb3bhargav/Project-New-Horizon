"""
Tests for Phase 3 Answer Pipeline components:
1. Local Question Detector (question classification rules)
2. RAM Session Context Cache (5 Q&A capacity limit, FIFO eviction, reset)
3. FIFO Question Queue (ordering & queue management)
4. Streaming Answer Engine (mocked Groq GPT-OSS 120B streaming & 429 key failover)
"""

import time
from unittest.mock import patch, MagicMock

from app.question_detector import QuestionDetector
from app.context_cache import ContextCache
from app.question_queue import QuestionQueue
from app.answer_engine import GroqAnswerEngine, AllAnswerKeysExhaustedError


# ---------------------------------------------------------------------------
# Test 1 - Question Detector
# ---------------------------------------------------------------------------

def test_question_detector():
    print("=" * 60)
    print("TEST 1: Local Rule-Based Question Detector")
    print("=" * 60)

    qd = QuestionDetector()

    questions = [
        "What is the capital of France?",
        "what is the time",
        "How far is the moon",
        "Is Paris a city",
        "Can you explain quantum computing",
        "Tell me a story",
        "Describe photosynthesis",
        "Where are my keys?"
    ]

    statements = [
        "Today is a sunny day.",
        "I love coding in Python.",
        "The quick brown fox jumps over the lazy dog",
        "Hello world"
    ]

    for q in questions:
        assert qd.is_question(q), f"Failed to identify as question: '{q}'"
        print(f"  [QUESTION] '{q}' -> True")

    for s in statements:
        assert not qd.is_question(s), f"Incorrectly identified as question: '{s}'"
        print(f"  [STATEMENT] '{s}' -> False")

    print("\n[VERIFICATION PASSED] Question detector rules work correctly.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 2 - Context Cache (5 Q&A FIFO Eviction)
# ---------------------------------------------------------------------------

def test_context_cache():
    print()
    print("=" * 60)
    print("TEST 2: RAM Context Cache (5-Pair Capacity & FIFO)")
    print("=" * 60)

    cache = ContextCache(capacity=5)
    assert len(cache) == 0

    # Add 6 Q&A pairs
    for i in range(1, 7):
        cache.add(f"Question {i}", f"Answer {i}")

    # Capacity limit check
    assert len(cache) == 5, f"Expected capacity 5, got {len(cache)}"
    print(f"  Capacity maintained at {len(cache)} pairs.")

    # FIFO check: Question 1 should be evicted, Question 2..6 present
    messages = cache.get_context_messages()

    first_user_msg = messages[0]["content"]
    assert first_user_msg == "Question 2", f"Expected oldest remaining 'Question 2', got '{first_user_msg}'"
    print(f"  Oldest entry evicted (Question 1 removed, Question 2 is first).")

    last_user_msg = messages[-2]["content"]
    assert last_user_msg == "Question 6", f"Expected newest 'Question 6', got '{last_user_msg}'"
    print(f"  Newest entry present (Question 6).")

    # Clear check
    cache.clear()
    assert len(cache) == 0, "Cache should be empty after clear"
    print("  Clear() resets cache to 0 entries.")

    print("\n[VERIFICATION PASSED] Context cache capacity & FIFO eviction verified.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 3 - Question Queue
# ---------------------------------------------------------------------------

def test_question_queue():
    print()
    print("=" * 60)
    print("TEST 3: FIFO Question Queue")
    print("=" * 60)

    q = QuestionQueue()
    assert q.is_empty()

    q.enqueue("First question?")
    q.enqueue("Second question?")
    assert q.size() == 2

    item1 = q.dequeue()
    assert item1 == "First question?"
    print(f"  Dequeued 1st: '{item1}'")

    item2 = q.dequeue()
    assert item2 == "Second question?"
    print(f"  Dequeued 2nd: '{item2}'")

    assert q.is_empty()
    assert q.dequeue() is None
    print("  Queue is empty after dequeuing all items.")

    print("\n[VERIFICATION PASSED] FIFO Question Queue operates in order.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 4 - Answer Engine Streaming (Mocked)
# ---------------------------------------------------------------------------

def test_answer_engine_streaming():
    print()
    print("=" * 60)
    print("TEST 4: Answer Engine Streaming (Mocked Groq GPT-OSS 120B)")
    print("=" * 60)

    engine = GroqAnswerEngine(keys=["test_answer_key_1"])

    mock_chunks = ["Paris ", "is ", "the ", "capital ", "of ", "France."]

    def mock_groq_constructor(api_key=None):
        mock = MagicMock()
        
        # Mock chunk object structure
        def chunk_gen():
            for text in mock_chunks:
                c = MagicMock()
                c.choices = [MagicMock()]
                c.choices[0].delta.content = text
                yield c

        mock.chat.completions.create.return_value = chunk_gen()
        return mock

    with patch("app.answer_engine.Groq", side_effect=mock_groq_constructor):
        tokens = list(engine.stream_answer("What is the capital of France?", mode="Short"))

    full_text = "".join(tokens)
    assert full_text == "Paris is the capital of France.", f"Unexpected output: '{full_text}'"
    print(f"  Streamed answer: '{full_text}'")

    print("\n[VERIFICATION PASSED] Answer engine streams tokens correctly.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Test 5 - Answer Engine Rate-Limit Failover
# ---------------------------------------------------------------------------

def test_answer_engine_failover():
    print()
    print("=" * 60)
    print("TEST 5: Answer Engine Rate-Limit Failover")
    print("=" * 60)

    engine = GroqAnswerEngine(keys=["key_1", "key_2"])

    def mock_groq_constructor(api_key=None):
        mock = MagicMock()
        if api_key == "key_1":
            err = Exception("Rate limit hit")
            err.status_code = 429
            mock.chat.completions.create.side_effect = err
        else:
            def chunk_gen():
                c = MagicMock()
                c.choices = [MagicMock()]
                c.choices[0].delta.content = "Failover answer"
                yield c
            mock.chat.completions.create.return_value = chunk_gen()
        return mock

    with patch("app.answer_engine.Groq", side_effect=mock_groq_constructor):
        tokens = list(engine.stream_answer("Test question?", mode="Short"))

    full_text = "".join(tokens)
    assert full_text == "Failover answer", f"Expected 'Failover answer', got '{full_text}'"

    assert 0 in engine._cooldowns, "Key 0 should be in cooldown after 429"
    print(f"  Key 1 hit 429 -> cooldown set")
    print(f"  Key 2 succeeded -> streamed: '{full_text}'")

    print("\n[VERIFICATION PASSED] Answer engine key failover works.")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_question_detector()
    test_context_cache()
    test_question_queue()
    test_answer_engine_streaming()
    test_answer_engine_failover()
    print("\n" + "=" * 60)
    print("ALL PHASE 3 ANSWER PIPELINE TESTS PASSED [OK]")
    print("=" * 60)
