"""Run the Northstar reconciliation and exception-prioritisation pipeline.

Sequence:
    dbt build -> extract exceptions -> score -> compare queues -> chart

Prerequisites:
    - Source feeds are already loaded into Snowflake RAW tables.
    - Local dbt and ML virtual environments are installed.
    - Snowflake key-pair authentication is configured.
    - A previously trained model bundle exists.

This runner processes the fixed portfolio snapshot, 2025-05-15.
Extraction validation also expects this snapshot. Changing the date
requires reviewing those checks and the model's suitability.

Each run writes separate step logs and a JSON execution summary.
A failed step prevents all later steps from running.

Outputs are updated by individual steps. The entire pipeline is not
one transaction: a later failure does not roll back earlier outputs.
Consumers should check the run summary before using refreshed results.
"""

import getpass
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


# Resolve paths relative to this script rather than the terminal's
# current directory, so file locations remain predictable.
ROOT = Path(__file__).resolve().parents[1]

# Use explicit executables to avoid accidentally running packages
# from the wrong virtual environment.
DBT = ROOT / ".venv313" / "Scripts" / "dbt.exe"
PYTHON = ROOT / ".venv-ml" / "Scripts" / "python.exe"

AS_OF_DATE = "2025-05-15"

# Bound each step's runtime so a stalled process cannot wait forever.
STEP_TIMEOUT_SECONDS = 600

# Order matters: every step consumes results from an earlier step.
# Scoring uses the saved model; training is a separate operation.
STEPS = [
    (
        "dbt_build",
        [str(DBT), "build", "--vars", f"as_of_date: '{AS_OF_DATE}'"],
        ROOT / "dbt",
    ),
    (
        "extract",
        [str(PYTHON), str(ROOT / "ml" / "extract_exceptions.py")],
        ROOT,
    ),
    (
        "score",
        [str(PYTHON), str(ROOT / "ml" / "score_exceptions.py")],
        ROOT,
    ),
    (
        "compare",
        [str(PYTHON), str(ROOT / "ml" / "compare_rankings.py")],
        ROOT,
    ),
    (
        "chart",
        [str(PYTHON), str(ROOT / "ml" / "plot_comparison.py")],
        ROOT,
    ),
]


def utc_now():
    """Return a timezone-aware timestamp for execution records."""
    return datetime.now(timezone.utc).isoformat()


def main():
    """Validate local prerequisites and execute steps sequentially."""

    # Fail before connecting to Snowflake if essential local files
    # are missing. Preflight failures occur before run logs are created.
    required = [
        DBT,
        PYTHON,
        ROOT / "dbt" / "dbt_project.yml",
        ROOT / "ml" / "models" / "isolation_forest_by_status.joblib",
    ]
    required.extend(Path(command[1]) for _, command, _ in STEPS[1:])

    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    # Reuse an existing environment secret or prompt without echoing it.
    # Unattended execution must supply the environment variable securely.
    # The passphrase is never included in command-line arguments.
    secret = os.environ.get("NORTHSTAR_KEY_PASSPHRASE")
    if not secret:
        secret = getpass.getpass("Private-key passphrase: ")
    if not secret:
        raise ValueError("Private-key passphrase is required.")

    # Give child processes the credentials and consistent text encoding.
    # Copying the environment avoids modifying the parent environment.
    child_env = os.environ.copy()
    child_env["NORTHSTAR_KEY_PASSPHRASE"] = secret
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"

    # Keep each run's evidence separate. The random suffix distinguishes
    # runs started within the same second; it does not prevent overlap.
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "_"
        + uuid4().hex[:8]
    )
    run_dir = ROOT / "logs" / "northstar" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    summary_file = run_dir / "summary.json"

    summary = {
        "run_id": run_id,
        "as_of_date": AS_OF_DATE,
        "started_at": utc_now(),
        "status": "running",
        "steps": [
            {"name": name, "status": "pending"}
            for name, _, _ in STEPS
        ],
    }

    def save_summary():
        """Persist progress so completed steps remain identifiable."""
        summary_file.write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )

    save_summary()
    failed = False

    for record, (name, command, cwd) in zip(summary["steps"], STEPS):
        # Stop downstream work after a failure rather than letting it
        # consume incomplete or outdated results.
        if failed:
            record["status"] = "skipped"
            continue

        print(f"\nSTART: {name}", flush=True)
        record["status"] = "running"
        record["started_at"] = utc_now()
        save_summary()

        # Use a monotonic clock for durations, independent of clock changes.
        started = time.perf_counter()

        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=child_env,
                # Child processes must not wait for interactive input.
                stdin=subprocess.DEVNULL,
                # Combine normal output and errors into one diagnostic log.
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
                timeout=STEP_TIMEOUT_SECONDS,
                # Pass arguments directly without shell interpretation.
                shell=False,
            )

            # Redact the exact passphrase if a child unexpectedly prints it.
            # This is a precaution, not a general-purpose secret scrubber.
            output = result.stdout.replace(secret, "[REDACTED]")
            (run_dir / f"{name}.log").write_text(
                output,
                encoding="utf-8",
            )

            record["exit_code"] = result.returncode
            if result.returncode != 0:
                raise RuntimeError(
                    f"Command exited with code {result.returncode}"
                )

            record["status"] = "success"

        except (Exception, KeyboardInterrupt) as error:
            # Record failures and user interruption, then skip later steps.
            # A timeout is recorded here; this version does not save the
            # timed-out process's partial output as a separate step log.
            record["status"] = "failed"
            record["error"] = str(error).replace(secret, "[REDACTED]")
            failed = True

        record["duration_seconds"] = round(
            time.perf_counter() - started,
            2,
        )
        record["finished_at"] = utc_now()

        print(
            f"{record['status'].upper()}: {name} "
            f"({record['duration_seconds']} seconds)",
            flush=True,
        )
        save_summary()

    # Overall success requires every step to complete successfully.
    summary["status"] = "failed" if failed else "success"
    summary["finished_at"] = utc_now()
    save_summary()

    print(f"\nPIPELINE {summary['status'].upper()}")
    print(f"Run logs: {run_dir}")
    print(f"Run summary: {summary_file}")

    # A scheduler or calling script can detect failure from the exit code.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())