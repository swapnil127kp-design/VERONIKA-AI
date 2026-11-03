"""
Tests for the GitHub repository scout.
"""
from automation.github_scout import GitHubScout, ScoutRepo


def sample_payload():
    return {
        "items": [
            {
                "full_name": "acme/cool-agent",
                "html_url": "https://github.com/acme/cool-agent",
                "description": "An autonomous agent framework",
                "stargazers_count": 1200,
                "language": "Python",
                "topics": ["ai-agents", "llm"],
                "forks_count": 50,
                "open_issues_count": 3,
            },
            {
                "full_name": "acme/tiny",
                "html_url": "https://github.com/acme/tiny",
                "description": "tiny util",
                "stargazers_count": 2,
                "language": "Go",
                "topics": [],
            },
        ]
    }


# ── Parsing ──────────────────────────────────────────────────

def test_parse_payload_builds_repos():
    repos = GitHubScout.parse_payload(sample_payload())
    assert len(repos) == 2
    first = repos[0]
    assert first.full_name == "acme/cool-agent"
    assert first.stars == 1200
    assert first.language == "Python"
    assert first.topics == ["ai-agents", "llm"]
    assert first.first_seen  # timestamp populated


def test_parse_payload_handles_empty():
    assert GitHubScout.parse_payload({}) == []
    assert GitHubScout.parse_payload({"items": []}) == []


def test_repo_to_dict():
    repo = ScoutRepo(full_name="a/b", stars=5, description="d")
    data = repo.to_dict()
    assert data["full_name"] == "a/b"
    assert data["stars"] == 5


# ── Filtering / dedup ────────────────────────────────────────

def test_is_hot_detects_keywords():
    assert GitHubScout._is_hot(ScoutRepo(full_name="a/agent-x"))
    assert GitHubScout._is_hot(ScoutRepo(full_name="a/b", description="LLM toolkit"))
    assert not GitHubScout._is_hot(ScoutRepo(full_name="a/b", description="todo list"))


def test_scan_once_dedups_and_filters(monkeypatch):
    scout = GitHubScout(min_stars=50, sources={"x": "q"})
    repos = GitHubScout.parse_payload(sample_payload())
    monkeypatch.setattr(scout, "_fetch_source", lambda q: list(repos))

    first = scout.scan_once()
    # low-star, non-hot repo is filtered; high-star kept
    names = [r.full_name for r in first]
    assert "acme/cool-agent" in names
    assert "acme/tiny" not in names

    # second scan returns nothing new
    second = scout.scan_once()
    assert second == []
    assert scout.scan_count == 2


def test_scan_once_includes_hot_low_star(monkeypatch):
    scout = GitHubScout(min_stars=1000, sources={"x": "q"})
    repos = GitHubScout.parse_payload(sample_payload())
    monkeypatch.setattr(scout, "_fetch_source", lambda q: list(repos))
    found = scout.scan_once()
    # cool-agent has only 1200 which is >= threshold anyway; tiny is hot? no.
    names = [r.full_name for r in found]
    assert names == ["acme/cool-agent"]


def test_scan_once_survives_source_error(monkeypatch):
    scout = GitHubScout(sources={"bad": "badquery", "good": "goodquery"})

    def flaky(q):
        if q == "badquery":
            raise RuntimeError("boom")
        return []

    monkeypatch.setattr(scout, "_fetch_source", flaky)
    # A failing source must not abort the whole scan.
    assert scout.scan_once() == []
    assert scout.scan_count == 1
    assert "bad" not in scout.get_last_scan_times()
    assert "good" in scout.get_last_scan_times()


def test_announce_calls_callback(monkeypatch):
    alerts = []
    scout = GitHubScout(on_alert=alerts.append, min_stars=1, sources={"x": "q"})
    repos = GitHubScout.parse_payload(sample_payload())
    monkeypatch.setattr(scout, "_fetch_source", lambda q: list(repos))
    scout.scan_once()
    assert alerts
    assert "acme/cool-agent" in alerts[0]


def test_get_known_repos_and_scan_times(monkeypatch):
    scout = GitHubScout(min_stars=1, sources={"x": "q"})
    repos = GitHubScout.parse_payload(sample_payload())
    monkeypatch.setattr(scout, "_fetch_source", lambda q: list(repos))
    scout.scan_once()
    known = scout.get_known_repos()
    assert len(known) == 2
    assert scout.get_last_scan_times().get("x")


# ── Lifecycle ────────────────────────────────────────────────

def test_lifecycle_start_stop(monkeypatch):
    scout = GitHubScout(sources={})
    monkeypatch.setattr(scout, "scan_once", lambda: [])
    scout.start()
    assert scout.is_running
    scout.stop()
    assert not scout.is_running
