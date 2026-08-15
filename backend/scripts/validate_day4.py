from pathlib import Path
import subprocess
import sys


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


CHECKS = [
    (
        "full pytest suite",
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
        ],
    ),
    (
        "Gemini provider diagnostic",
        [
            sys.executable,
            "-m",
            "scripts.diagnose_gemini",
        ],
    ),
    (
        "Turn Understanding smoke",
        [
            sys.executable,
            "-m",
            "scripts.smoke_turn_understanding",
        ],
    ),
    (
        "Intake smoke",
        [
            sys.executable,
            "-m",
            "scripts.smoke_intake",
        ],
    ),
]


def main() -> int:
    print("=" * 70)
    print("VENTUREMIND DAY 4 VALIDATION")
    print("=" * 70)

    for index, (
        label,
        command,
    ) in enumerate(
        CHECKS,
        start=1,
    ):
        print()
        print(
            f"CHECK {index}/{len(CHECKS)}: "
            f"{label}"
        )
        print("-" * 70)

        result = subprocess.run(
            command,
            cwd=BACKEND_ROOT,
            check=False,
        )

        if result.returncode != 0:
            print()
            print("=" * 70)
            print(
                "DAY 4 VALIDATION: FAIL"
            )
            print(
                f"Failed check: {label}"
            )
            return result.returncode

        print(
            f"PASS: {label}"
        )

    print()
    print("=" * 70)
    print("DAY 4 VALIDATION: PASS")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
