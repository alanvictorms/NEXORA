from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import (
    ArchitectureSpecVersion,
    Project,
    ProjectSpecVersion,
    Task,
    TaskDependency,
    TaskGraph,
)
from app.services.common import checksum
from app.services.events import EventService
from app.services.specs import next_graph_version

TASK_BLUEPRINTS: list[dict[str, Any]] = [
    {
        "key": "bootstrap",
        "task_type": "bootstrap",
        "objective": "Criar o repositório e a base executável da aplicação gerada.",
        "dependencies": [],
        "allowed_paths": ["generated-app/**", "README.md"],
        "criteria": ["Repositório possui aplicação inicial", "README contém instruções"],
    },
    {
        "key": "backend",
        "task_type": "backend_feature",
        "objective": "Implementar contratos e endpoints centrais do produto.",
        "dependencies": ["bootstrap"],
        "allowed_paths": ["generated-app/backend/**"],
        "criteria": ["Healthcheck existe", "Regras centrais estão representadas"],
    },
    {
        "key": "frontend",
        "task_type": "frontend_feature",
        "objective": "Implementar a primeira experiência React alinhada ao ProjectSpec.",
        "dependencies": ["bootstrap"],
        "allowed_paths": ["generated-app/frontend/**", "generated-app/index.html"],
        "criteria": ["Interface responsiva existe", "Fluxo principal está visível"],
    },
    {
        "key": "tests",
        "task_type": "test_generation",
        "objective": "Derivar testes e smoke checks dos critérios de aceite.",
        "dependencies": ["backend", "frontend"],
        "allowed_paths": ["generated-app/tests/**"],
        "criteria": ["Smoke test é executável", "Critérios possuem rastreabilidade"],
    },
]


class TaskGraphService:
    def __init__(self, db: Session):
        self.db = db
        self.events = EventService(db)

    def generate(
        self,
        project: Project,
        spec: ProjectSpecVersion,
        architecture: ArchitectureSpecVersion,
    ) -> TaskGraph:
        version = next_graph_version(self.db, TaskGraph, project.id)
        graph_payload = [{"key": t["key"], "dependencies": t["dependencies"]} for t in TASK_BLUEPRINTS]
        graph = TaskGraph(
            project_id=project.id,
            architecture_spec_version_id=architecture.id,
            version=version,
            checksum=checksum(graph_payload),
        )
        self.db.add(graph)
        self.db.flush()
        by_key: dict[str, Task] = {}
        for blueprint in TASK_BLUEPRINTS:
            task = Task(
                task_graph_id=graph.id,
                key=blueprint["key"],
                task_type=blueprint["task_type"],
                objective=blueprint["objective"],
                context_refs=[f"spec://{spec.id}", f"architecture://{architecture.id}"],
                allowed_paths=blueprint["allowed_paths"],
                forbidden_paths=["infra/production/**", ".env", "**/*secret*"],
                acceptance_criteria=blueprint["criteria"],
                validation_commands=["git diff --check"],
                expected_artifacts=[{"kind": "task_receipt", "required": True}],
                provider_policy={
                    "capability": self._capability(blueprint["task_type"]),
                    "preferred": None,
                    "fallback": ["local_mock"],
                    "allow_fallback": True,
                },
                timeout_seconds=900,
                max_attempts=2,
                retry_policy={"backoff": "exponential", "initial_seconds": 2, "maximum_seconds": 60},
            )
            self.db.add(task)
            self.db.flush()
            by_key[blueprint["key"]] = task
        for blueprint in TASK_BLUEPRINTS:
            for dependency in blueprint["dependencies"]:
                self.db.add(
                    TaskDependency(
                        task_id=by_key[blueprint["key"]].id,
                        depends_on_task_id=by_key[dependency].id,
                    )
                )
        self.db.flush()
        self.validate_dag(graph)
        project.status = "PLANNED"
        self.events.emit(
            project.id,
            "task_graph.completed",
            f"TaskGraph v{version} validada com {len(by_key)} tarefas",
            payload={"graph_id": graph.id, "tasks": len(by_key)},
        )
        self.db.commit()
        return graph

    @staticmethod
    def _capability(task_type: str) -> str:
        return {
            "bootstrap": "bootstrap",
            "backend_feature": "code_backend",
            "frontend_feature": "code_frontend",
            "test_generation": "code_test",
        }.get(task_type, "code_general")

    def validate_dag(self, graph: TaskGraph) -> list[list[str]]:
        tasks = list(self.db.scalars(select(Task).where(Task.task_graph_id == graph.id)))
        ids = {task.id for task in tasks}
        deps = list(
            self.db.execute(
                select(TaskDependency.task_id, TaskDependency.depends_on_task_id).where(
                    TaskDependency.task_id.in_(ids)
                )
            )
        )
        indegree = {task.id: 0 for task in tasks}
        outgoing: dict[str, list[str]] = defaultdict(list)
        for task_id, depends_on in deps:
            if depends_on not in ids:
                raise ValueError("TaskGraph referencia dependência externa")
            indegree[task_id] += 1
            outgoing[depends_on].append(task_id)
        queue = deque([task_id for task_id, degree in indegree.items() if degree == 0])
        waves: list[list[str]] = []
        visited = 0
        while queue:
            wave = list(queue)
            queue.clear()
            waves.append(wave)
            for node in wave:
                visited += 1
                for target in outgoing[node]:
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        queue.append(target)
        if visited != len(tasks):
            raise ValueError("TaskGraph contém ciclo")
        return waves

    def latest(self, project_id: str) -> TaskGraph | None:
        return self.db.scalar(
            select(TaskGraph)
            .where(TaskGraph.project_id == project_id)
            .order_by(TaskGraph.version.desc())
            .limit(1)
        )
