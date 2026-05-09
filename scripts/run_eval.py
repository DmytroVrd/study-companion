from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("CHROMA_PERSIST_DIR", str(Path(".chroma_eval").resolve()))
os.environ.setdefault("OPENROUTER_EMBEDDING_MODEL", "")

from companion.rag.loader import load_document, split_documents  # noqa: E402
from companion.rag.vectorstore import add_documents, delete_collection, query  # noqa: E402


def _load_cases(path: Path) -> list[dict]:
    cases = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _collection_name(case_id: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in case_id.lower())
    return f"eval_{safe}"


def _contains_all(text: str, terms: list[str]) -> tuple[bool, list[str]]:
    normalized = text.casefold()
    missing = [term for term in terms if term.casefold() not in normalized]
    return not missing, missing


def run_eval(dataset_path: Path, top_k: int) -> int:
    root = dataset_path.parent
    cases = _load_cases(dataset_path)
    passed = 0

    for case in cases:
        file_path = root / case["file"]
        collection_name = _collection_name(case["id"])
        delete_collection(collection_name)

        docs = split_documents(load_document(file_path))
        add_documents(collection_name, docs)

        chunks = query(collection_name, case["question"], k=top_k)
        context = "\n\n".join(chunk.page_content for chunk in chunks)
        ok, missing = _contains_all(context, case["must_include"])

        status = "PASS" if ok else "FAIL"
        print(f"{status} {case['id']}")
        if not ok:
            print(f"  missing: {', '.join(missing)}")
            print(f"  top source: {chunks[0].metadata if chunks else 'none'}")
        else:
            passed += 1

    total = len(cases)
    print(f"\n{passed}/{total} eval cases passed")
    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run retrieval smoke evals.")
    parser.add_argument(
        "--dataset",
        default="evals/questions.jsonl",
        help="Path to eval JSONL dataset.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Retrieved chunks per question.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the local eval Chroma directory before running.",
    )
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(os.environ["CHROMA_PERSIST_DIR"], ignore_errors=True)

    return run_eval(Path(args.dataset), args.top_k)


if __name__ == "__main__":
    sys.exit(main())
