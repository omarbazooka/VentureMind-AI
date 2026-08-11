from app.chat.turn_understanding import TurnUnderstandingService
from app.llm.gateway import LLMGatewayError


SMOKE_CASES = [
    "Hello",
    "My target customers are small restaurants in Egypt.",
    "Start the analysis.",
    "Change my budget to 500000 EGP.",
    "Change my budget to 500000 EGP and rerun the scenario.",
    "Do it.",
    "Change my budget to 500000 EGP, actually keep the old budget.",
]


def main() -> None:
    service = TurnUnderstandingService()

    for index, message in enumerate(
        SMOKE_CASES,
        start=1,
    ):
        print()
        print("=" * 70)
        print(f"CASE {index}")
        print(f"USER: {message}")
        print("-" * 70)

        try:
            result = service.understand(
                message
            )

        except LLMGatewayError as exc:
            print(
                f"LLM ERROR: {type(exc).__name__}: {exc}"
            )
            continue

        except ValueError as exc:
            print(
                f"INPUT ERROR: {exc}"
            )
            continue

        print(
            result.model_dump_json(
                indent=2
            )
        )


if __name__ == "__main__":
    main()