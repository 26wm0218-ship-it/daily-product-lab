"""Bounded Codex proposal -> local apply -> verify -> review loop."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "docs" / "autonomous-loop.json"
LOG = ROOT / ".loop-logs" / "latest.jsonl"
PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "next_instruction": {"type": "string"},
        "rationale": {"type": "string"},
        "edits": {"type": "array", "items": {
            "type": "object", "properties": {
                "path": {"type": "string"},
                "expected_sha256": {"type": "string"},
                "content": {"type": "string"},
            }, "required": ["path", "expected_sha256", "content"],
            "additionalProperties": False,
        }},
    },
    "required": ["next_instruction", "rationale", "edits"],
    "additionalProperties": False,
}
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "approved": {"type": "boolean"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["approved", "findings"],
    "additionalProperties": False,
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(event, **fields):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"event": event, "time": time.time(), **fields}, ensure_ascii=False) + "\n")


def path_for(name, allowed):
    if not isinstance(name, str) or name not in allowed or name.startswith("/") or "\\" in name or ".." in Path(name).parts:
        raise ValueError(f"out-of-scope path: {name}")
    path = ROOT / name
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f"unsafe path: {name}")
    return path


def validate_and_apply(proposal, allowed, max_bytes):
    if not isinstance(proposal, dict) or set(proposal) != {"next_instruction", "rationale", "edits"}:
        raise ValueError("invalid proposal fields")
    if not isinstance(proposal["next_instruction"], str) or not proposal["next_instruction"].strip():
        raise ValueError("missing next instruction")
    edits = proposal["edits"]
    if not isinstance(edits, list) or not edits:
        raise ValueError("proposal must edit at least one file")
    prepared = []
    seen = set()
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"path", "expected_sha256", "content"}:
            raise ValueError("invalid edit fields")
        name = edit["path"]
        if name in seen:
            raise ValueError("duplicate edit")
        seen.add(name)
        path = path_for(name, allowed)
        before = path.read_bytes() if path.exists() else b""
        if not isinstance(edit["content"], str) or not isinstance(edit["expected_sha256"], str):
            raise ValueError("invalid edit value")
        after = edit["content"].encode("utf-8")
        if edit["expected_sha256"] != digest(before):
            raise ValueError(f"stale edit: {name}")
        if not after or len(after) > max_bytes:
            raise ValueError(f"empty or oversized edit: {name}")
        prepared.append((path, after))
    for path, after in prepared:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(after)
    return [str(path.relative_to(ROOT)).replace("\\", "/") for path, _ in prepared]


def run_process(args, timeout, env, input_text=None):
    process = subprocess.Popen(
        args, cwd=ROOT, env=env, stdin=subprocess.PIPE if input_text is not None else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        errors="replace", creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, timeout=5, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()
        process.communicate()
        raise
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)


def run_checked(args, timeout):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return run_process(args, timeout, env)


def codex_environment():
    permitted = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
                 "USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH"}
    return {key: value for key, value in os.environ.items() if key.upper() in permitted}


def ask_codex(prompt, schema, timeout, output_path):
    schema_path = LOG.parent / "schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    env = codex_environment()
    cmd = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--sandbox", "read-only", "--json",
           "--output-schema", str(schema_path), "--output-last-message", str(output_path),
           "-C", str(ROOT), "-"]
    result = run_process(cmd, timeout, env, input_text=prompt)
    if result.returncode:
        raise RuntimeError(f"Codex exited {result.returncode}: {result.stderr[-500:]}")
    usage = None
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed":
            usage = event.get("usage")
    if not usage:
        raise RuntimeError("Codex did not report token usage")
    return json.loads(output_path.read_text(encoding="utf-8")), usage


def context(allowed):
    items = []
    for name in allowed:
        path = path_for(name, allowed)
        data = path.read_bytes() if path.exists() else b""
        items.append({"path": name, "sha256": digest(data), "content": data.decode("utf-8")})
    return items


def git_diff(timeout):
    result = run_checked(["git", "diff", "--", "."], timeout)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def check_worktree_scope(allowed, timeout=10):
    result = run_checked(["git", "status", "--porcelain", "-z", "--untracked-files=all"], timeout)
    if result.returncode:
        raise RuntimeError(result.stderr)
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        state, name = entry[:2], entry[3:]
        if state not in {" M", " A"} or name not in allowed:
            raise ValueError(f"unexpected worktree change: {state} {name}")


def protected_snapshot(allowed):
    hashes = {}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in allowed or relative.startswith(".loop-logs/"):
            continue
        if relative.startswith(".git/") and not (
            relative == ".git/config" or relative.startswith(".git/hooks/")
            or relative == ".git/info/exclude"
        ):
            continue
        hashes[relative] = digest(path.read_bytes())
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal-file", type=Path, help="Use an already generated AI proposal for one PoC cycle")
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    allowed = cfg["allowed_edit_paths"]
    if not isinstance(allowed, list) or not allowed or any(
        not isinstance(name, str) or name.startswith(("sources/", ".git/")) for name in allowed
    ):
        raise SystemExit("unsafe allowlist")
    deadline = time.monotonic() + cfg["max_wall_seconds"]
    def remaining(cap):
        left = deadline - time.monotonic()
        if left <= 0:
            raise subprocess.TimeoutExpired("overall time limit", 0)
        return min(cap, left)
    branch = run_checked(["git", "branch", "--show-current"], remaining(10)).stdout.strip()
    if not branch.startswith("codex/autonomous-loop-"):
        raise SystemExit("run only on a codex/autonomous-loop-* branch")
    initial = run_checked(["git", "status", "--porcelain", "--untracked-files=all"], remaining(10)).stdout
    if initial:
        raise SystemExit("commit setup changes before running the loop")
    LOG.parent.mkdir(exist_ok=True)
    if LOG.exists():
        history = LOG.parent / "history"
        history.mkdir(exist_ok=True)
        shutil.move(str(LOG), str(history / f"{time.time_ns()}.jsonl"))
    LOG.write_text("", encoding="utf-8")
    if not args.proposal_file and cfg.get("allow_codex_context_transmission") is not True:
        record("stopped", reason="model_context_approval_required")
        return 2
    baseline = protected_snapshot(allowed)
    failure = ""
    model_calls = 0
    total_tokens = 0
    for iteration in range(1, cfg["max_iterations"] + 1):
        if time.monotonic() >= deadline:
            record("stopped", reason="time_limit", iteration=iteration)
            return 2
        record("iteration_started", iteration=iteration)
        if args.proposal_file:
            if iteration > 1:
                record("stopped", reason="proposal_file_single_cycle", iteration=iteration)
                return 2
            try:
                proposal = json.loads(args.proposal_file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                record("stopped", reason="proposal_error", detail=str(error), iteration=iteration)
                return 2
        else:
            if model_calls >= cfg["max_model_calls"] or total_tokens >= cfg["max_total_tokens"]:
                record("stopped", reason="model_budget", iteration=iteration,
                       model_calls=model_calls, total_tokens=total_tokens)
                return 2
            try:
                prompt = json.dumps({
                    "goal": cfg["goal"], "allowed_files": context(allowed), "previous_failure": failure,
                    "instruction": "Generate the next small work instruction and complete replacement contents for only the allowed files. No tools, shell, network, deletion, or external actions. Return schema JSON only. expected_sha256 must equal the supplied sha256."
                }, ensure_ascii=False)
                proposal, usage = ask_codex(prompt, PROPOSAL_SCHEMA, remaining(cfg["max_call_seconds"]),
                                            LOG.parent / "proposal.json")
                model_calls += 1
                total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                record("model_usage", phase="proposal", iteration=iteration, usage=usage,
                       total_tokens=total_tokens)
            except (OSError, RuntimeError, ValueError, UnicodeError, subprocess.TimeoutExpired) as error:
                record("stopped", reason="ai_error", detail=str(error), iteration=iteration)
                return 2
        record("proposed", iteration=iteration, next_instruction=(
            proposal.get("next_instruction") if isinstance(proposal, dict) else None))
        if time.monotonic() >= deadline:
            record("stopped", reason="time_limit", iteration=iteration)
            return 2
        try:
            changed = validate_and_apply(proposal, allowed, cfg["max_file_bytes"])
        except (ValueError, UnicodeError) as error:
            record("stopped", reason="scope_violation", detail=str(error), iteration=iteration)
            return 2
        record("applied", iteration=iteration, paths=changed)
        intent = run_checked(["git", "add", "-N", "--", *changed], remaining(10))
        if intent.returncode:
            record("stopped", reason="git_error", detail=intent.stderr, iteration=iteration)
            return 2
        try:
            check_worktree_scope(allowed, remaining(10))
            if protected_snapshot(allowed) != baseline:
                raise ValueError("protected file changed")
        except (RuntimeError, ValueError) as error:
            record("stopped", reason="scope_violation", detail=str(error), iteration=iteration)
            return 2
        results = []
        for check in ([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                      [sys.executable, "scripts/verify.py"], ["git", "diff", "--check"]):
            try:
                result = run_checked(check, remaining(cfg["max_check_seconds"]))
                results.append({"command": check, "exit_code": result.returncode,
                                "output": (result.stdout + result.stderr)[-1500:]})
            except subprocess.TimeoutExpired:
                results.append({"command": check, "exit_code": -1, "output": "timeout"})
                if time.monotonic() >= deadline:
                    record("stopped", reason="time_limit", iteration=iteration, results=results)
                    return 2
        record("verified", iteration=iteration, results=results)
        try:
            check_worktree_scope(allowed, remaining(10))
            if protected_snapshot(allowed) != baseline:
                raise ValueError("protected file changed")
        except (RuntimeError, ValueError) as error:
            record("stopped", reason="scope_violation", detail=str(error), iteration=iteration)
            return 2
        if any(item["exit_code"] for item in results):
            failure = json.dumps(results, ensure_ascii=False)
            if iteration == cfg["max_iterations"]:
                record("stopped", reason="test_failure", iteration=iteration)
                return 2
            continue
        diff = git_diff(remaining(10))
        if not diff:
            record("stopped", reason="no_diff", iteration=iteration)
            return 2
        if args.proposal_file:
            record("review_pending", iteration=iteration, reason="manual_proposal_mode",
                   diff_sha256=digest(diff.encode("utf-8")))
            return 3
        if model_calls >= cfg["max_model_calls"] or total_tokens >= cfg["max_total_tokens"]:
            record("stopped", reason="model_budget", iteration=iteration,
                   model_calls=model_calls, total_tokens=total_tokens)
            return 2
        review_prompt = json.dumps({
            "goal": cfg["goal"], "next_instruction": proposal["next_instruction"],
            "diff": diff, "checks": results,
            "instruction": "Independent review. Check scope, factual claims, test evidence, security, and completion. No tools or edits. Return schema JSON only."
        }, ensure_ascii=False)
        try:
            review, usage = ask_codex(review_prompt, REVIEW_SCHEMA, remaining(cfg["max_call_seconds"]),
                                      LOG.parent / "review.json")
            model_calls += 1
            total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            record("model_usage", phase="review", iteration=iteration, usage=usage,
                   total_tokens=total_tokens)
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            record("stopped", reason="review_unavailable", detail=str(error), iteration=iteration)
            return 2
        record("reviewed", iteration=iteration, result=review,
               diff_sha256=digest(diff.encode("utf-8")))
        if review.get("approved") is True and review.get("findings") == []:
            if time.monotonic() >= deadline:
                record("stopped", reason="time_limit", iteration=iteration)
                return 2
            record("completed", iteration=iteration, diff_sha256=digest(diff.encode("utf-8")),
                   file_sha256={name: digest(path_for(name, allowed).read_bytes()) for name in changed})
            return 0
        failure = json.dumps(review, ensure_ascii=False)
    record("stopped", reason="iteration_limit", iteration=cfg["max_iterations"])
    return 2


if __name__ == "__main__":
    sys.exit(main())
