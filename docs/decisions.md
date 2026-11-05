# Decisions

## 2026-11-05: Codex, tests, and review for this repository

- **Context:** The connected GitHub account exposes this Python-based repository, while no Unity/Meta Quest 3/RDS research repository is connected. This repository already has `AGENTS.md`, a Python verifier, and a `Verify` GitHub Actions workflow.
- **Decision:** Keep the existing source, idea backlog, experiment content, and draft-generation workflow unchanged. Add focused tests for the verifier, a short work log, and repository-specific Codex review rules. Use Draft PRs for review.
- **Reason:** The existing checks can be exercised without changing product behavior or research conditions. PRs show the exact diff before any merge.
- **Review boundary:** Request an independent Codex review only when Codex Code Review is enabled for this repository. A review request or rule file alone does not prove that a review ran. Record the actual review and CI outcomes in `docs/progress.md`.
- **Revisit when:** A research repository becomes available, or the product gains executable application code needing behavior tests.
