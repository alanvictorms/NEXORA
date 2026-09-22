from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings


class RepositoryError(RuntimeError):
    pass


class GitRepositoryService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.settings.repository_root.mkdir(parents=True, exist_ok=True)
        self.worktree_root = self.settings.repository_root.parent / "worktrees"
        self.worktree_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _run(args: list[str], cwd: Path) -> str:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=120, check=False)
        if result.returncode:
            raise RepositoryError(f"{' '.join(args)}: {result.stderr.strip()}")
        return result.stdout.strip()

    def initialize(self, project_id: str, name: str) -> tuple[Path, str]:
        path = (self.settings.repository_root / project_id).resolve()
        expected_root = self.settings.repository_root.resolve()
        if expected_root not in path.parents:
            raise RepositoryError("Caminho de repositório inválido")
        path.mkdir(parents=True, exist_ok=True)
        if not (path / ".git").exists():
            self._run(["git", "init", "-b", "main"], path)
            self._run(["git", "config", "user.email", "nexora@local"], path)
            self._run(["git", "config", "user.name", "NEXORA Orchestrator"], path)
            (path / "README.md").write_text(
                f"# {name}\n\nRepositório criado e governado pelo NEXORA Agentic Builder.\n",
                encoding="utf-8",
            )
            self._run(["git", "add", "README.md"], path)
            self._run(["git", "commit", "-m", "chore: initialize generated project"], path)
        return path, self.head(path)

    def head(self, repo: Path) -> str:
        return self._run(["git", "rev-parse", "HEAD"], repo)

    def create_worktree(self, repo: Path, task_id: str) -> tuple[Path, str, str]:
        safe_id = task_id.replace("/", "-")
        branch = f"task/{safe_id}"
        worktree = (self.worktree_root / safe_id).resolve()
        expected_root = self.worktree_root.resolve()
        if expected_root not in worktree.parents:
            raise RepositoryError("Caminho de worktree inválido")
        if worktree.exists():
            shutil.rmtree(worktree)
        base_sha = self.head(repo)
        self._run(["git", "worktree", "add", "-b", branch, str(worktree), base_sha], repo)
        return worktree, branch, base_sha

    def commit(self, worktree: Path, task_key: str) -> str:
        self._run(["git", "add", "-A"], worktree)
        status = self._run(["git", "status", "--porcelain"], worktree)
        if not status:
            marker = worktree / ".nexora" / f"{task_key}.complete"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("completed\n", encoding="utf-8")
            self._run(["git", "add", "-A"], worktree)
        self._run(["git", "commit", "-m", f"feat: complete {task_key}"], worktree)
        return self.head(worktree)

    def merge_and_cleanup(self, repo: Path, worktree: Path, branch: str) -> str:
        self._run(["git", "merge", "--no-ff", branch, "-m", f"merge: {branch}"], repo)
        self._run(["git", "worktree", "remove", "--force", str(worktree)], repo)
        self._run(["git", "branch", "-D", branch], repo)
        return self.head(repo)


