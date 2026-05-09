import json
from pathlib import Path


def test_eval_dataset_references_existing_files() -> None:
    dataset = Path("evals/questions.jsonl")
    assert dataset.exists()

    for line in dataset.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        assert (dataset.parent / case["file"]).exists()
        assert case["question"]
        assert case["must_include"]
