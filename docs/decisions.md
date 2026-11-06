# Decisions

## 2026-11-05: Codex, tests, and review for this repository

- **Context:** The connected GitHub account exposes this Python-based repository, while no Unity/Meta Quest 3/RDS research repository is connected. This repository already has `AGENTS.md`, a Python verifier, and a `Verify` GitHub Actions workflow.
- **Decision:** Keep the existing source, idea backlog, experiment content, and draft-generation workflow unchanged. Add focused tests for the verifier, a short work log, and repository-specific Codex review rules. Use Draft PRs for review.
- **Reason:** The existing checks can be exercised without changing product behavior or research conditions. PRs show the exact diff before any merge.
- **Review boundary:** Request an independent Codex review only when Codex Code Review is enabled for this repository. A review request or rule file alone does not prove that a review ran. Record the actual review and CI outcomes in `docs/progress.md`.
- **Revisit when:** A research repository becomes available, or the product gains executable application code needing behavior tests.

## 2026-11-06: Bounded local autonomous loop PoC

- **Context:** Reuse the existing Draft PR #1 snapshot. The connected GitHub integration can read it but returns HTTP 403 for branch creation. The Codex CLI launches locally, while this session's nested execution policy blocks its file-reading shell calls.
- **Decision:** Keep the loop local on a dedicated branch. Pass only allowlisted file content to a read-only Codex session; accept structured next instructions and complete-file edits. A local script checks paths, source hashes, size, fixed tests, and diff. A separate read-only session reviews successful changes. No GitHub writes or external actions are part of the loop.
- **Limits:** At most 2 iterations, 4 model calls, 180 seconds total, 60 seconds per model call, 30 seconds per check, 250,000 reported tokens before another model call, and 4 KiB per edited file. These bound activity but are not a hard monetary cap or an in-call token cap.
- **Stop:** Invalid or out-of-scope proposal, stale source hash, tool failure, missing review, exceeded limit, or test failure after the last iteration. Keep the diff and log for human inspection; do not auto-push or merge.
- **Revisit when:** The GitHub integration can write, an isolated Codex CLI runtime can complete the full autonomous call, and a real research repo is available with explicit experiment safeguards.

## 2026-11-06: Handoff gate after implementation review

- **Context:** The complete local patch was prepared for an independent Codex implementation review, but automatic approval review rejected sending it to an external AI service under the user's explicit no-external-transmission condition.
- **Decision:** Do not resend the full patch through another route. Add local worktree scope checks before and after fixed tests, pass only minimal environment variables to Codex, and default future model calls to stopped until the user explicitly approves the exact file context in `docs/autonomous-loop.json`.
- **Limit:** The earlier independent reviews covered the small documentation edits, not the full runner implementation. Local unit tests and inspection cover the new guards. Read-only Codex execution does not itself restrict which readable files the model may inspect, so keep research and credentials out of its runtime until separately isolated.

## 2026-11-06: Independent implementation review within existing plan usage

- **Context:** The account is signed in to Codex through ChatGPT Plus, with no purchased credits. The user authorized actions only when no additional charge would result. A separate Codex session reviewed the full local patch using included plan usage and reported five findings.
- **Decision:** Add checks for ignored files and Git configuration, preserve prior run logs, bind completion to diff and file hashes, apply the overall deadline to more steps, and attempt to terminate child processes on timeout. Keep `allow_codex_context_transmission` false by default.
- **Remaining limits:** CLI read-only mode does not confine reads to the allowlist, and process-tree termination is best effort. Do not enable unattended use for research or credential-bearing repositories until isolated execution enforces both boundaries. GitHub Actions and any GitHub write remain subject to the account's no-charge budget.
