"""
VERONIKA AI - Workflow Engine
Executes multistep task workflows with validation, cancellation, and progress tracking.
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable

from app.config import config

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    action: str
    args: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    requires_confirmation: bool = False
    status: WorkflowStatus = WorkflowStatus.PENDING
    result_message: str = ""
    error: Optional[str] = None


@dataclass
class Workflow:
    """A multi-step workflow definition."""
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: int = 0
    created_at: str = ""


# Predefined workflow templates
WORKFLOW_TEMPLATES = {
    "coding_session": Workflow(
        name="Start Coding Session",
        description="Open your development environment and project",
        steps=[
            WorkflowStep(
                action="launch_app",
                args={"name": "vscode"},
                description="Open Visual Studio Code",
            ),
            WorkflowStep(
                action="open_terminal",
                args={},
                description="Open terminal",
            ),
        ],
    ),
    "morning_routine": Workflow(
        name="Morning Routine",
        description="Start your day with essential apps",
        steps=[
            WorkflowStep(
                action="open_website",
                args={"url": "https://mail.google.com"},
                description="Open Gmail",
            ),
            WorkflowStep(
                action="open_website",
                args={"url": "https://calendar.google.com"},
                description="Open Calendar",
            ),
            WorkflowStep(
                action="browser_search",
                args={"query": "today's news"},
                description="Check today's news",
            ),
        ],
    ),
}


class WorkflowEngine:
    """Executes multi-step workflows with progress tracking and cancellation."""

    def __init__(self, action_registry):
        self.action_registry = action_registry
        if hasattr(action_registry, "workflow_engine"):
            action_registry.workflow_engine = self
        self._current_workflow: Optional[Workflow] = None
        self._cancel_flag = threading.Event()
        self._on_progress: Optional[Callable] = None
        self._on_complete: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        self._max_steps = config.get("automation", "max_workflow_steps", 20)
        self._step_timeout = config.get("automation", "step_timeout_seconds", 30)

    @property
    def is_running(self) -> bool:
        return self._current_workflow is not None and self._current_workflow.status == WorkflowStatus.RUNNING

    @property
    def current_workflow(self) -> Optional[Workflow]:
        return self._current_workflow

    def get_templates(self) -> Dict[str, Workflow]:
        """Return available workflow templates."""
        return WORKFLOW_TEMPLATES

    def start_workflow(
        self,
        workflow_name: str,
        on_progress: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        custom_steps: List[WorkflowStep] = None,
    ) -> bool:
        """Start a workflow execution."""
        if self.is_running:
            logger.warning("A workflow is already running")
            return False

        if custom_steps:
            workflow = Workflow(
                name=workflow_name,
                description=f"Custom workflow: {workflow_name}",
                steps=custom_steps[:self._max_steps],
            )
        elif workflow_name in WORKFLOW_TEMPLATES:
            # Deep copy template
            template = WORKFLOW_TEMPLATES[workflow_name]
            workflow = Workflow(
                name=template.name,
                description=template.description,
                steps=[
                    WorkflowStep(
                        action=s.action,
                        args=dict(s.args),
                        description=s.description,
                        requires_confirmation=s.requires_confirmation,
                    )
                    for s in template.steps
                ],
            )
        else:
            logger.error("Unknown workflow: %s", workflow_name)
            return False

        self._current_workflow = workflow
        self._cancel_flag.clear()
        self._on_progress = on_progress
        self._on_complete = on_complete

        self._thread = threading.Thread(target=self._execute_workflow, daemon=True)
        self._thread.start()
        return True

    def _execute_workflow(self):
        """Execute workflow steps sequentially."""
        workflow = self._current_workflow
        workflow.status = WorkflowStatus.RUNNING

        completed = 0
        failed = 0

        for i, step in enumerate(workflow.steps):
            if self._cancel_flag.is_set():
                step.status = WorkflowStatus.CANCELLED
                workflow.status = WorkflowStatus.CANCELLED
                logger.info("Workflow cancelled at step %d", i + 1)
                break

            workflow.current_step = i
            step.status = WorkflowStatus.RUNNING

            if self._on_progress:
                self._on_progress(i, len(workflow.steps), step.description)

            try:
                result = self.action_registry.execute(step.action, step.args)
                if result.success:
                    step.status = WorkflowStatus.COMPLETED
                    step.result_message = result.message
                    completed += 1
                else:
                    step.status = WorkflowStatus.FAILED
                    step.error = result.message
                    failed += 1
                    logger.warning("Workflow step %d failed: %s", i + 1, result.message)
            except Exception as e:
                step.status = WorkflowStatus.FAILED
                step.error = str(e)
                failed += 1
                logger.error("Workflow step %d error: %s", i + 1, e)

            # Brief pause between steps
            time.sleep(0.5)

        # Determine final status
        if workflow.status != WorkflowStatus.CANCELLED:
            if failed == 0:
                workflow.status = WorkflowStatus.COMPLETED
            elif completed > 0:
                workflow.status = WorkflowStatus.PARTIAL
            else:
                workflow.status = WorkflowStatus.FAILED

        if self._on_complete:
            self._on_complete(workflow)

        logger.info(
            "Workflow '%s' finished: %s (%d/%d steps completed)",
            workflow.name,
            workflow.status.value,
            completed,
            len(workflow.steps),
        )

    def cancel(self):
        """Cancel the running workflow."""
        self._cancel_flag.set()
        if self._current_workflow:
            self._current_workflow.status = WorkflowStatus.CANCELLED
