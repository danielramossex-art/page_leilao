"""Read-only review of the working tree. Never prints secret values or stages files."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GIT = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]


def git(*args):
    return subprocess.check_output([*GIT, *args], cwd=ROOT, text=True, encoding="utf-8")


paths = set(git("diff", "--name-only").splitlines())
paths.update(git("ls-files", "--others", "--exclude-standard").splitlines())
patterns = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp_|github_pat_|sk-proj-|sk-live-|apify_api_)[A-Za-z0-9_\-]{15,}"),
    re.compile(r"(?i)(?:api_key|password|secret|token)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]"),
]
findings = []
for relative in sorted(paths):
    path = ROOT / relative
    if not path.is_file():
        continue
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeError:
        findings.append({"file": relative, "reason": "binary_requires_manual_review"})
        continue
    if "\ufffd" in content:
        findings.append({"file": relative, "reason": "replacement_character"})
    for number, line in enumerate(content.splitlines(), 1):
        if any(pattern.search(line) for pattern in patterns):
            findings.append({"file": relative, "line": number, "reason": "possible_secret"})
tracked = set(git("ls-files").splitlines())
assert ".env" not in tracked
assert not any(path.startswith(("data/backups/", "data/validation/")) for path in tracked)
report = {"files_reviewed": sorted(paths), "findings": findings, "env_tracked": False,
          "note": "Pattern scan plus manual diff review; not a guarantee against every possible secret."}
output = ROOT / "data" / "validation" / "git_review.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=True, indent=2))
if findings:
    raise SystemExit(1)
