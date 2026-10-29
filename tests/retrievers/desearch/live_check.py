"""Run one Desearch request using only the retriever's dependencies."""

import importlib.util
from pathlib import Path


def load_retriever():
    path = Path(__file__).resolve().parents[3] / "gpt_researcher/retrievers/desearch/desearch.py"
    spec = importlib.util.spec_from_file_location("desearch_isolated", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DesearchSearch


def main():
    try:
        results = load_retriever()("bittensor").search()
    except ValueError:
        results = []
    print(f"Result count: {len(results)}")
    title = results[0]["title"] if results else ""
    print(f"First title: {' '.join(title.split())}")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
