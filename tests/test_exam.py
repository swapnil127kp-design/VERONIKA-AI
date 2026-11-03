"""
Tests for the exam predictor.
"""
from ai.exam_predictor import (
    ExamPredictor,
    ExamPrediction,
    PredictedTopic,
    PAST_QUESTIONS_CATEGORY,
    PREDICTIONS_CATEGORY,
)
from ai.provider_base import AIResponse
from automation.action_registry import ActionRegistry


class FakeMemory:
    def __init__(self):
        self.store = {}

    def save_memory(self, category, key, value):
        self.store[(category, key)] = value

    def recall_memory(self, category, key):
        return self.store.get((category, key))

    def get_all_memories(self, category=None):
        return [
            {"category": c, "key": k, "value": v}
            for (c, k), v in self.store.items()
            if category is None or c == category
        ]

    def record_automation(self, *args, **kwargs):
        pass


class FakeProvider:
    def __init__(self, content):
        self._content = content

    def send_message(self, user_message, **kwargs):
        return AIResponse(content=self._content)


class ErrorProvider:
    def send_message(self, user_message, **kwargs):
        return AIResponse(content="", error="down")


AI_JSON = """
{
  "topics": [
    {"topic": "Normalization", "probability": 0.9, "importance": "high", "reason": "heavy weightage"},
    {"topic": "Transactions", "probability": 1.7, "importance": "medium", "reason": "clamp test"}
  ],
  "questions": ["Explain 3NF with an example.", "What is a deadlock?"],
  "strategy": "Do normalization problems first."
}
"""


def test_predict_ai_parses_topics_and_questions():
    p = ExamPredictor(provider_manager=FakeProvider(AI_JSON))
    pred = p.predict("DBMS", syllabus="Normalization, Transactions")
    assert pred.source == "ai"
    assert pred.topics[0].topic == "Normalization"
    assert pred.topics[0].probability == 0.9
    assert len(pred.questions) == 2
    assert "normalization" in pred.strategy.lower()
    assert pred.generated_at


def test_predict_clamps_probability():
    p = ExamPredictor(provider_manager=FakeProvider(AI_JSON))
    pred = p.predict("DBMS")
    assert pred.topics[1].probability == 1.0


def test_predict_falls_back_to_heuristic_on_error():
    p = ExamPredictor(provider_manager=ErrorProvider(), memory_manager=FakeMemory())
    p.add_past_question("DBMS", "Explain normalization in database design")
    p.add_past_question("DBMS", "Explain normalization and indexing")
    pred = p.predict("DBMS")
    assert pred.source == "heuristic"
    assert any(t.topic == "normalization" for t in pred.topics)


def test_heuristic_no_data():
    p = ExamPredictor(provider_manager=ErrorProvider(), memory_manager=FakeMemory())
    pred = p.predict("Unknown Subject")
    assert pred.source == "heuristic"
    assert pred.topics == []
    assert "No past questions" in pred.strategy


def test_add_and_get_past_questions():
    mem = FakeMemory()
    p = ExamPredictor(provider_manager=None, memory_manager=mem)
    p.add_past_question("DBMS", "Q1", year="2023", marks=5)
    p.add_past_question("DBMS", "Q2")
    items = p.get_past_questions("DBMS")
    assert len(items) == 2
    assert items[0]["question"] == "Q1"
    assert items[0]["year"] == "2023"
    # stored under normalized (lowercased) subject key
    assert (PAST_QUESTIONS_CATEGORY, "dbms") in mem.store


def test_list_subjects():
    mem = FakeMemory()
    p = ExamPredictor(memory_manager=mem)
    p.add_past_question("DBMS", "Q1")
    p.add_past_question("OS", "Q2")
    assert sorted(p.list_subjects()) == ["dbms", "os"]


def test_save_prediction_persists():
    mem = FakeMemory()
    p = ExamPredictor(provider_manager=FakeProvider(AI_JSON), memory_manager=mem)
    pred = p.predict("DBMS")
    p.save_prediction(pred)
    assert (PREDICTIONS_CATEGORY, "dbms") in mem.store


def test_summary_contains_topics_and_strategy():
    pred = ExamPrediction(
        subject="DBMS",
        topics=[PredictedTopic(topic="Indexing", probability=0.75, importance="high")],
        questions=["What is a B-tree?"],
        strategy="Focus on indexing.",
    )
    text = pred.summary()
    assert "Exam prediction for DBMS" in text
    assert "Indexing" in text
    assert "75%" in text
    assert "What is a B-tree?" in text
    assert "Focus on indexing." in text


def test_prediction_to_dict():
    pred = ExamPrediction(subject="OS", topics=[PredictedTopic(topic="Scheduling", probability=0.5)])
    data = pred.to_dict()
    assert data["subject"] == "OS"
    assert data["topics"][0]["topic"] == "Scheduling"
    assert data["topics"][0]["probability"] == 0.5


# ── ActionRegistry integration ───────────────────────────────

def test_action_add_past_question_and_predict():
    reg = ActionRegistry(
        memory_manager=FakeMemory(),
        provider_manager=FakeProvider(AI_JSON),
    )
    add = reg.execute("add_past_question", {"subject": "DBMS", "question": "Q1"})
    assert add.success
    res = reg.execute("predict_exam", {"subject": "DBMS"})
    assert res.success
    assert res.data["topics"][0]["topic"] == "Normalization"


def test_action_predict_exam_requires_subject():
    reg = ActionRegistry(memory_manager=FakeMemory(), provider_manager=FakeProvider(AI_JSON))
    assert not reg.execute("predict_exam", {}).success


def test_action_swarm_run_with_fake_agents():
    from ai.swarm_coordinator import SwarmCoordinator
    from mcp.rea_bridge import ReaResult

    reg = ActionRegistry()
    reg.swarm = SwarmCoordinator(
        agent_factory=lambda goal, depth: type(
            "A", (), {"run": lambda self, g, context=None: ReaResult(goal=g, success=True, final_answer=f"done:{g}")}
        )()
    )
    res = reg.execute("swarm_run", {"goals": ["a", "b"]})
    assert res.success
    assert "done:a" in res.message


def test_actions_registered():
    reg = ActionRegistry()
    actions = reg.get_available_actions()
    for name in ("swarm_run", "predict_exam", "add_past_question"):
        assert name in actions
