"""
VERONIKA AI - Phase 7 Memory Engine Tests
Tests for extended memory system with categories, semantic retrieval, and UI.
"""
import unittest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

from memory.database import Database
from memory.memory_manager import MemoryManager


class Phase7MemoryTests(unittest.TestCase):
    """Test Phase 7 memory engine enhancements."""

    def setUp(self):
        """Create a temporary database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db = Database(Path(self.temp_db.name))
        self.manager = MemoryManager(self.db)

    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        Path(self.temp_db.name).unlink(missing_ok=True)

    # ═══════════════════════════════════════════════════════════
    # Test 1: User Profile Memory
    # ═══════════════════════════════════════════════════════════

    def test_add_user_profile(self):
        """Test adding user profile information."""
        profile_id = self.manager.add_user_profile(
            name="John Doe",
            bio="Senior Software Engineer",
            preferences={"timezone": "EST", "language": "en"}
        )
        self.assertIsNotNone(profile_id)
        self.assertGreater(profile_id, 0)
        print(f"✓ User profile added: ID {profile_id}")

    def test_retrieve_user_profile(self):
        """Test retrieving user profile."""
        profile_id = self.manager.add_user_profile(
            name="Jane Smith",
            bio="Product Manager"
        )

        profiles = self.manager.get_all_by_category("user_profile")
        self.assertGreater(len(profiles), 0)
        self.assertIn("Jane Smith", profiles[0]["content"])
        print(f"✓ User profile retrieved: {profiles[0]['content'][:50]}")

    # ═══════════════════════════════════════════════════════════
    # Test 2: Project Memory
    # ═══════════════════════════════════════════════════════════

    def test_add_project(self):
        """Test adding project information."""
        project_id = self.manager.add_project(
            name="VERONIKA AI",
            path="/c/Users/Swapnil/OneDrive/Desktop/claude code/VERONIKA",
            description="Advanced AI personal assistant with voice, automation, and memory",
            status="active"
        )
        self.assertIsNotNone(project_id)
        self.assertGreater(project_id, 0)
        print(f"✓ Project added: ID {project_id}")

    def test_retrieve_projects(self):
        """Test retrieving all projects."""
        self.manager.add_project("Project A", description="First project")
        self.manager.add_project("Project B", description="Second project")

        projects = self.manager.get_all_by_category("projects")
        self.assertEqual(len(projects), 2)
        print(f"✓ Retrieved {len(projects)} projects")

    # ═══════════════════════════════════════════════════════════
    # Test 3: Task Memory
    # ═══════════════════════════════════════════════════════════

    def test_add_task(self):
        """Test adding task information."""
        task_id = self.manager.add_task(
            goal="Complete Phase 7 memory engine",
            status="in_progress",
            agent_assignments=["Claude Code", "AI Assistant"]
        )
        self.assertIsNotNone(task_id)
        self.assertGreater(task_id, 0)
        print(f"✓ Task added: ID {task_id}")

    def test_retrieve_tasks(self):
        """Test retrieving all tasks."""
        self.manager.add_task("Task 1", status="pending")
        self.manager.add_task("Task 2", status="in_progress")
        self.manager.add_task("Task 3", status="completed")

        tasks = self.manager.get_all_by_category("tasks")
        self.assertEqual(len(tasks), 3)
        print(f"✓ Retrieved {len(tasks)} tasks")

    # ═══════════════════════════════════════════════════════════
    # Test 4: Preference Memory
    # ═══════════════════════════════════════════════════════════

    def test_add_preference(self):
        """Test adding preference."""
        pref_id = self.manager.add_preference(
            key="notification_level",
            value="important_only",
            category="notifications"
        )
        self.assertIsNotNone(pref_id)
        self.assertGreater(pref_id, 0)
        print(f"✓ Preference added: ID {pref_id}")

    def test_retrieve_preferences(self):
        """Test retrieving preferences."""
        self.manager.add_preference("theme", "dark")
        self.manager.add_preference("font_size", "12px")
        self.manager.add_preference("animation_enabled", "true")

        prefs = self.manager.get_all_by_category("preferences")
        self.assertEqual(len(prefs), 3)
        print(f"✓ Retrieved {len(prefs)} preferences")

    # ═══════════════════════════════════════════════════════════
    # Test 5: Session Memory
    # ═══════════════════════════════════════════════════════════

    def test_add_session_context(self):
        """Test adding session context."""
        session_id = self.manager.add_session_context(
            context="User asked about project status and team assignments",
            context_type="interaction"
        )
        self.assertIsNotNone(session_id)
        self.assertGreater(session_id, 0)
        print(f"✓ Session context added: ID {session_id}")

    def test_retrieve_session_memory(self):
        """Test retrieving session memories."""
        self.manager.add_session_context("First interaction")
        self.manager.add_session_context("User query about tasks")
        self.manager.add_session_context("Status check requested")

        session_mem = self.manager.get_all_by_category("session")
        self.assertEqual(len(session_mem), 3)
        print(f"✓ Retrieved {len(session_mem)} session memories")

    # ═══════════════════════════════════════════════════════════
    # Test 6: Search by Category
    # ═══════════════════════════════════════════════════════════

    def test_search_projects(self):
        """Test searching within projects."""
        self.manager.add_project("VERONIKA Phase 1", description="Initial voice setup")
        self.manager.add_project("VERONIKA Phase 2", description="Memory integration")
        self.manager.add_project("MyApp Mobile", description="Mobile application")

        results = self.manager.search_memory("projects", "VERONIKA")
        self.assertEqual(len(results), 2)
        print(f"✓ Searched projects, found {len(results)} matches for 'VERONIKA'")

    def test_search_tasks(self):
        """Test searching within tasks."""
        self.manager.add_task("Implement voice recognition")
        self.manager.add_task("Test voice engine")
        self.manager.add_task("Optimize database queries")

        results = self.manager.search_memory("tasks", "voice")
        self.assertEqual(len(results), 2)
        print(f"✓ Searched tasks, found {len(results)} matches for 'voice'")

    # ═══════════════════════════════════════════════════════════
    # Test 7: Semantic Relevance Ranking
    # ═══════════════════════════════════════════════════════════

    def test_relevance_scoring(self):
        """Test relevance score calculation."""
        # Add multiple memories
        self.manager.add_project("Python Project", description="Built with Python and Django")
        self.manager.add_project("JavaScript Project", description="Built with Node.js")
        self.manager.add_task("Learn Python", status="in_progress")
        self.manager.add_task("Learn JavaScript", status="pending")

        # Query for "Python"
        results = self.manager.get_relevant_context("Python projects", limit=10)
        self.assertGreater(len(results), 0)

        # Check that results are sorted by relevance (highest first)
        scores = [r["relevance_score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        print(f"✓ Relevance scoring working, top score: {scores[0]:.2f}")

    # ═══════════════════════════════════════════════════════════
    # Test 8: Cross-Category Search
    # ═══════════════════════════════════════════════════════════

    def test_get_relevant_context(self):
        """Test retrieving relevant context across all categories."""
        # Add diverse memories
        self.manager.add_user_profile("Alice", "AI researcher focusing on NLP")
        self.manager.add_project("NLP Engine", description="Natural language processing")
        self.manager.add_task("Improve NLP model accuracy", status="in_progress")
        self.manager.add_preference("research_area", "NLP and ML")
        self.manager.add_session_context("Discussed NLP improvements and benchmarks")

        # Search for "NLP"
        results = self.manager.get_relevant_context("NLP", limit=10)
        self.assertGreaterEqual(len(results), 3)

        # Verify we get results from multiple categories
        categories = {r["category_name"] for r in results}
        self.assertGreater(len(categories), 1)
        print(f"✓ Cross-category search found {len(results)} results from {len(categories)} categories")

    # ═══════════════════════════════════════════════════════════
    # Test 9: Delete Memory
    # ═══════════════════════════════════════════════════════════

    def test_delete_memory(self):
        """Test deleting a specific memory."""
        task_id = self.manager.add_task("Temporary task")

        # Verify it exists
        tasks_before = self.manager.get_all_by_category("tasks")
        initial_count = len(tasks_before)

        # Delete it
        self.manager.delete_memory(task_id, "tasks")

        # Verify it's gone
        tasks_after = self.manager.get_all_by_category("tasks")
        self.assertEqual(len(tasks_after), initial_count - 1)
        print(f"✓ Memory deleted successfully")

    # ═══════════════════════════════════════════════════════════
    # Test 10: Metadata Handling
    # ═══════════════════════════════════════════════════════════

    def test_metadata_storage(self):
        """Test storing and retrieving metadata."""
        project_id = self.manager.add_project(
            "Enterprise App",
            path="/projects/enterprise",
            description="Large scale app",
            status="planning"
        )

        projects = self.manager.get_all_by_category("projects")
        project = projects[0]

        # Verify metadata was stored
        self.assertIsNotNone(project["metadata_json"])
        metadata = json.loads(project["metadata_json"])
        self.assertEqual(metadata["name"], "Enterprise App")
        self.assertEqual(metadata["status"], "planning")
        print(f"✓ Metadata stored and retrieved: {metadata}")

    # ═══════════════════════════════════════════════════════════
    # Integration Test: Complete Workflow
    # ═══════════════════════════════════════════════════════════

    def test_complete_workflow(self):
        """Test a complete workflow with all memory types."""
        print("\n--- Complete Phase 7 Workflow Test ---")

        # 1. Create user profile
        self.manager.add_user_profile(
            "Alex Chen",
            "Full-stack developer specializing in AI",
            {"timezone": "PST", "notifications": "enabled"}
        )
        print("✓ Step 1: User profile created")

        # 2. Add projects
        self.manager.add_project("AI Assistant", "/projects/ai", "Personal AI assistant", "active")
        self.manager.add_project("Web Portal", "/projects/web", "Company web portal", "planning")
        print("✓ Step 2: Projects added")

        # 3. Add tasks
        self.manager.add_task("Implement voice interface", "in_progress", ["voice_team"])
        self.manager.add_task("Deploy web portal v2", "pending", ["deploy_team"])
        print("✓ Step 3: Tasks added")

        # 4. Add preferences
        self.manager.add_preference("theme", "dark", "ui")
        self.manager.add_preference("auto_save", "enabled", "editor")
        print("✓ Step 4: Preferences added")

        # 5. Add session context
        self.manager.add_session_context("User reviewed project status and upcoming tasks")
        print("✓ Step 5: Session context added")

        # 6. Search by category
        projects = self.manager.search_memory("projects", "AI")
        self.assertGreater(len(projects), 0)
        print(f"✓ Step 6: Category search found {len(projects)} projects")

        # 7. Get relevant context (semantic search)
        results = self.manager.get_relevant_context("What tasks are in progress for AI projects?", limit=5)
        self.assertGreater(len(results), 0)
        print(f"✓ Step 7: Semantic search found {len(results)} relevant memories")

        # 8. Verify data by category
        all_categories = ["user_profile", "projects", "tasks", "preferences", "session"]
        for category in all_categories:
            items = self.manager.get_all_by_category(category)
            self.assertGreater(len(items), 0)
            print(f"  ✓ {category}: {len(items)} item(s)")

        print("\n✓✓✓ Phase 7 Complete Workflow Test PASSED ✓✓✓")


def run_tests():
    """Run all Phase 7 tests."""
    print("\n" + "="*70)
    print("VERONIKA AI - Phase 7: Memory Engine Enhancement - TEST SUITE")
    print("="*70 + "\n")

    suite = unittest.TestLoader().loadTestsFromTestCase(Phase7MemoryTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*70 + "\n")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
