from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
required = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "ideas" / "backlog.yml",
    ROOT / "prompts" / "generate-draft.md",
]
errors = [f"missing: {p.relative_to(ROOT)}" for p in required if not p.exists()]

backlog = (ROOT / "ideas" / "backlog.yml").read_text(encoding="utf-8")
ids = re.findall(r"^\s+- id:\s*(\S+)", backlog, re.MULTILINE)
days = re.findall(r"^\s+day:\s*(\d+)", backlog, re.MULTILINE)
for field in ("domain", "audience", "problem", "output", "cta", "product_metric", "brand_metric", "status"):
    count = len(re.findall(rf"^\s+{field}:\s*.+", backlog, re.MULTILINE))
    if count != len(ids):
        errors.append(f"backlog field '{field}' occurs {count} times; expected {len(ids)}")

if len(ids) != 7 or len(set(ids)) != 7:
    errors.append("week-1 backlog must contain 7 unique ids")
if sorted(map(int, days)) != list(range(1, 8)):
    errors.append("week-1 backlog days must be 1 through 7")

for draft in (ROOT / "content" / "drafts").glob("*.md"):
    text = draft.read_text(encoding="utf-8")
    for heading in ("対象者", "課題", "CTA", "顧客指標", "ブランド指標", "人間の確認"):
        if heading not in text:
            errors.append(f"{draft.relative_to(ROOT)}: missing section '{heading}'")

if errors:
    print("Verification failed:")
    print("\n".join(f"- {error}" for error in errors))
    sys.exit(1)
print(f"Verification passed: {len(ids)} backlog items and repository structure are valid.")

