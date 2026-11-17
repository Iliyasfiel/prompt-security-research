"""Rescore saved extraction traces without making new model calls."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("experiment", ROOT / "scripts" / "experiment.py")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
for folder in (ROOT / "runs").glob("*/extraction"):
    result_path = folder / "results.jsonl"
    if not result_path.exists():
        continue
    old_rows = [json.loads(line) for line in result_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in old_rows:
        trace_path = folder / "traces" / (row["id"] + ".json")
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        case = experiment.make_case(row["domain"], bool(row.get("pilot")))
        score = experiment.extraction_score(trace.get("combined_output", ""), case)
        old = {key: row.get(key) for key in ("fact_recall", "random_fact_recall", "matched_fact_ids")}
        row.update(score)
        row["rescored_from"] = old
        row["scoring_version"] = "strict-business-phrases-v2"
        trace["result"] = row
        trace["previous_score"] = old
        trace_path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    result_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in old_rows), encoding="utf-8"
    )
    print(json.dumps({"folder": str(folder), "rescored": len(old_rows)}, ensure_ascii=False))
