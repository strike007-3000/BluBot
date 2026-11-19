"""Fail if a workflow job reads a secret without declaring a GitHub environment.

Environment secrets are only released to jobs on branches allowed by the environment
(`production` -> main only). A job that reads repo-level secrets without `environment:`
lets any pushed branch exfiltrate them.
"""
import re
from pathlib import Path

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))
SECRET_RE = re.compile(r"secrets\.(?!GITHUB_TOKEN\b)\w+")
JOB_RE = re.compile(r"^  ([\w-]+):\s*$")  # job id: 2-space indent under `jobs:`
ENV_RE = re.compile(r"^    environment:")  # job-level key: 4-space indent


def _jobs(text):
    """Yield (job_id, lines) for each job under the top-level `jobs:` key."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.rstrip() == "jobs:"), None)
    if start is None:
        return
    job, body = None, []
    for line in lines[start + 1:]:
        m = JOB_RE.match(line)
        if m:
            if job:
                yield job, body
            job, body = m.group(1), []
        elif job:
            body.append(line)
    if job:
        yield job, body


def test_workflows_found():
    assert WORKFLOWS, "no workflow files found; path logic is broken"


def test_jobs_using_secrets_declare_environment():
    offenders = []
    for wf in WORKFLOWS:
        for job, body in _jobs(wf.read_text()):
            uses_secret = any(SECRET_RE.search(line) for line in body)
            has_env = any(ENV_RE.match(line) for line in body)
            if uses_secret and not has_env:
                offenders.append(f"{wf.name}:{job}")
    assert not offenders, f"jobs read secrets.* without `environment:`: {offenders}"
