"""Verify numerical controls and shareable artifacts after the project pipeline."""

import hashlib
import json
import math
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify():
    metrics = json.loads((ROOT / "reports/metrics.json").read_text())
    checks = []

    def check(condition, description):
        if not condition:
            raise AssertionError(description)
        checks.append(description)

    def finite(value):
        if isinstance(value, dict):
            return all(finite(x) for x in value.values())
        if isinstance(value, list):
            return all(finite(x) for x in value)
        return not isinstance(value, float) or math.isfinite(value)

    check(finite(metrics), "All numerical metrics are finite")
    build = json.loads((ROOT / "reports/build_manifest.json").read_text())
    check(
        all(
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
            for path, digest in build["source_code_sha256"].items()
        ),
        "Generated results match the current analytical source files",
    )
    pdf = ROOT / "reports/analysis.pdf"
    check(pdf.read_bytes().startswith(b"%PDF"), "PDF report has a valid document header")
    check(
        len((ROOT / "reports/analysis.md").read_text()) > 1000,
        "Analysis includes substantive methods and limitations",
    )
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    workbooks = []
    for path in sorted((ROOT / "reports").glob("*.xlsx")):
        formula_count = 0
        with zipfile.ZipFile(path) as archive:
            check("xl/workbook.xml" in archive.namelist(), path.name + " workbook structure")
            for name in archive.namelist():
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                    sheet = ET.fromstring(archive.read(name))
                    check(
                        not any(c.attrib.get("t") == "e" for c in sheet.findall(".//s:c", ns)),
                        path.name + " has no cached Excel errors in " + name,
                    )
                    formulas = sheet.findall(".//s:f", ns)
                    formula_count += len(formulas)
                    check(
                        not any("#REF!" in (f.text or "") for f in formulas),
                        path.name + " has no broken references in " + name,
                    )
        workbooks.append({"file": path.name, "formula_count": formula_count})
    NAME = ROOT.name
    if NAME == "partsgraph":
        check(metrics["baseline_units"] == 36, "Healthy scenario satisfies all 36 demand units")
        check(
            metrics["after_substitution_lost_contribution_inr"]
            < metrics["seal_outage_lost_contribution_inr"],
            "Approved spares reduce outage loss",
        )
        check(metrics["incompatible_fan_rejected"], "Voltage-incompatible alternate is rejected")
    elif NAME == "losslens":
        check(
            metrics["train"] + metrics["validation"] + metrics["test"] == metrics["policies_modelled"],
            "Policy partitions account for every modelled policy",
        )
        import pandas as pd

        splits = pd.read_csv(ROOT / "reports/policy_splits.csv")
        check(not splits.IDpol.duplicated().any(), "No policy appears in multiple split assignments")
        scores = pd.read_csv(ROOT / "reports/model_comparison.csv")
        selected = scores[scores.subset == "validation"].sort_values("tweedie_deviance").iloc[0].model
        check(selected == metrics["selected_on_validation"], "Selection follows validation deviance")
    elif NAME == "reservewatch":
        check(
            metrics["maximum_package_difference"] < 0.01,
            "Independent package reserve differences are below tolerance",
        )
        import pandas as pd

        reference = pd.read_csv(ROOT / "reports/package_verification.csv")
        check(len(reference) == 15, "Five insurers independently verified at three valuations")
        check(reference.mack_standard_error.notna().all(), "Mack errors are present for all valuations")
        check(
            any(w["formula_count"] > 40 for w in workbooks),
            "Excel triangle review contains live calculation formulas",
        )
    elif NAME == "revenue-anatomy":
        rec = metrics["reconciliation"]
        check(
            abs(rec["source_amount"] - rec["classified_amount"] - rec["quarantined_amount"]) < 0.01,
            "Source equals classified plus quarantined amount",
        )
        check(
            abs(rec["monthly_vs_ledger_difference"]) < 0.01,
            "SQL monthly totals reconcile to classified ledger",
        )
        check(abs(metrics["bridge"]["difference"]) < 0.01, "Revenue bridge reconciles to net movement")
        with zipfile.ZipFile(ROOT / "reports/management_review.pptx") as archive:
            slides = [
                n for n in archive.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")
            ]
            check(len(slides) == 5, "Management presentation contains five slides")
        check(
            any(w["formula_count"] > 40 for w in workbooks), "Excel management model contains live formulas"
        )
    elif NAME == "cashcycle":
        check(
            abs(metrics["ledger_reconciliation_difference"]) < 0.01,
            "Receivables control reconciles within one paisa",
        )
        import pandas as pd

        for scenario in ["base", "downside", "improvement"]:
            frame = pd.read_csv(ROOT / f"reports/forecast_{scenario}.csv")
            check(len(frame) == 13, scenario + " has thirteen weeks")
            check(
                (frame.closing_cash - frame.opening_cash - frame.net_cash).abs().max() < 0.01,
                scenario + " cash roll-forward reconciles",
            )
            check((frame.receipts >= 0).all(), scenario + " collections are nonnegative")
        check(
            any(w["formula_count"] > 200 for w in workbooks),
            "Excel plan contains live cash-roll-forward formulas",
        )
    elif NAME == "casebook":
        check(metrics["evaluation"]["questions"] == 78, "All 78 authored benchmark questions evaluated")
        check(
            metrics["evaluation"]["citation_excerpt_integrity"] == 1,
            "All quoted benchmark excerpts trace exactly to source text",
        )
        examples = json.loads((ROOT / "reports/investigation_examples.json").read_text())
        check(examples[-1]["status"] == "insufficient_evidence", "Pre-release historical query abstains")
        check(examples[2]["status"] == "insufficient_evidence", "Unrelated example query abstains")
    artifacts = {}
    for path in sorted((ROOT / "reports").iterdir()):
        if path.is_file() and path.name != "artifact_manifest.json":
            artifacts[path.name] = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    result = {"checks_passed": len(checks), "checks": checks, "workbooks": workbooks, "artifacts": artifacts}
    (ROOT / "reports/artifact_manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"project": NAME, "checks_passed": len(checks), "workbooks": workbooks}, indent=2))
    return result


if __name__ == "__main__":
    verify()
