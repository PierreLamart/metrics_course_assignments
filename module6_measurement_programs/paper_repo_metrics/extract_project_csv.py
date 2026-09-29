#!/usr/bin/env python3

"""
Extract subsections of the "project" section from a repository metrics JSON file
into separate CSV files.

Usage:
    python extract_project_csv.py metrics.json

Optional output directory:
    python extract_project_csv.py metrics.json --output-dir project_csv

Example output:
    project_csv/
        project_summary.csv
        halstead_combined_token_stream.csv
        halstead_combined_token_stream_languages.csv
        class_metric_summaries.csv

The script is designed to work with JSON reports produced by the
paper_repo_metrics repository analyzer.
"""

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


def safe_filename(name: str) -> str:
    """
    Convert a JSON key into a filesystem-safe filename.
    """
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return name.strip("_") or "section"


def csv_safe(value: Any) -> Any:
    """
    Convert values that cannot be written directly to CSV into strings.
    """
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return value


def write_scalar_summary(
    scalar_values: dict[str, Any],
    output_path: Path,
) -> None:
    """
    Write scalar project-level values as:

        metric,value
        file_count,321
        loc,118122
        ...
    """
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow(["metric", "value"])

        for key, value in scalar_values.items():
            writer.writerow([key, csv_safe(value)])


def write_dict_of_scalars(
    section_name: str,
    data: dict[str, Any],
    output_path: Path,
) -> None:
    """
    Write a simple dictionary as a single CSV row.

    Example:

        {
            "distinct_operators": 62,
            "distinct_operands": 85261,
            "total_operators": 29714
        }

    becomes:

        distinct_operators,distinct_operands,total_operators
        62,85261,29714
    """
    fieldnames = list(data.keys())

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        writer.writerow(
            {
                key: csv_safe(value)
                for key, value in data.items()
            }
        )


def write_dict_of_dicts(
    section_name: str,
    data: dict[str, dict[str, Any]],
    output_path: Path,
) -> None:
    """
    Write dictionaries such as class_metric_summaries.

    Example:

        {
            "attribute_count": {
                "measured": 391,
                "unavailable": 0,
                "sum": 500,
                "mean": 1.27,
                "max": 116
            },
            "cbo_known": {
                ...
            }
        }

    becomes:

        metric,measured,unavailable,sum,mean,max
        attribute_count,391,0,500,1.27,116
        cbo_known,...
    """

    # Gather every possible column appearing in child dictionaries.
    child_columns = []

    for values in data.values():
        if isinstance(values, dict):
            for key in values:
                if key not in child_columns:
                    child_columns.append(key)

    fieldnames = ["metric"] + child_columns

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for metric_name, values in data.items():
            row = {"metric": metric_name}

            if isinstance(values, dict):
                for key in child_columns:
                    row[key] = csv_safe(values.get(key))
            else:
                row["value"] = csv_safe(values)

            writer.writerow(row)


def write_list(
    section_name: str,
    data: list[Any],
    output_path: Path,
) -> None:
    """
    Export JSON arrays.

    Handles:
        - list of strings
        - list of numbers
        - list of dictionaries
        - more complicated values
    """

    if not data:
        # Still create an empty CSV.
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["value"])
        return

    # List of dictionaries
    if all(isinstance(item, dict) for item in data):
        columns = []

        for item in data:
            for key in item:
                if key not in columns:
                    columns.append(key)

        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()

            for item in data:
                writer.writerow(
                    {
                        key: csv_safe(item.get(key))
                        for key in columns
                    }
                )

        return

    # Simple list
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["value"])

        for item in data:
            writer.writerow([csv_safe(item)])


def write_generic_section(
    section_name: str,
    data: Any,
    output_path: Path,
) -> None:
    """
    Decide how a project subsection should be converted to CSV.
    """

    if isinstance(data, dict):

        # Is this dictionary itself composed mainly of child dictionaries?
        if data and all(isinstance(value, dict) for value in data.values()):
            write_dict_of_dicts(
                section_name,
                data,
                output_path,
            )

        else:
            write_dict_of_scalars(
                section_name,
                data,
                output_path,
            )

    elif isinstance(data, list):
        write_list(
            section_name,
            data,
            output_path,
        )

    else:
        # Fallback for unexpected scalar subsections.
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["value"])
            writer.writerow([csv_safe(data)])


def extract_project_section(
    json_path: Path,
    output_dir: Path,
) -> None:
    """
    Extract the complete top-level "project" section.
    """

    # ---------------------------------------------------------
    # Read JSON
    # ---------------------------------------------------------

    with json_path.open("r", encoding="utf-8") as file:
        report = json.load(file)

    # ---------------------------------------------------------
    # Validate structure
    # ---------------------------------------------------------

    if "project" not in report:
        raise KeyError(
            f'The file "{json_path}" does not contain a top-level '
            '"project" section.'
        )

    project = report["project"]

    if not isinstance(project, dict):
        raise TypeError(
            'The top-level "project" value must be a JSON object.'
        )

    # ---------------------------------------------------------
    # Create output directory
    # ---------------------------------------------------------

    output_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Separate simple project values from nested subsections
    # ---------------------------------------------------------

    scalar_values = {}
    nested_sections = {}

    for key, value in project.items():

        if isinstance(value, (dict, list)):
            nested_sections[key] = value
        else:
            scalar_values[key] = value

    # ---------------------------------------------------------
    # Write main repository/project summary
    # ---------------------------------------------------------

    if scalar_values:
        summary_path = output_dir / "project_summary.csv"

        write_scalar_summary(
            scalar_values,
            summary_path,
        )

        print(f"Created: {summary_path}")

    # ---------------------------------------------------------
    # Write every nested subsection separately
    # ---------------------------------------------------------

    for section_name, section_data in nested_sections.items():

        filename = safe_filename(section_name) + ".csv"
        output_path = output_dir / filename

        write_generic_section(
            section_name,
            section_data,
            output_path,
        )

        print(f"Created: {output_path}")

    print()
    print(
        f"Finished. Extracted {len(nested_sections) + 1} "
        f"project CSV sections into:"
    )
    print(output_dir.resolve())


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            'Extract the "project" section of a repository metrics '
            "JSON report into separate CSV files."
        )
    )

    parser.add_argument(
        "json_file",
        type=Path,
        help="Path to the metrics JSON file.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("project_csv"),
        help=(
            "Directory where CSV files will be written "
            "(default: project_csv)."
        ),
    )

    args = parser.parse_args()

    if not args.json_file.exists():
        parser.error(
            f"JSON file does not exist: {args.json_file}"
        )

    try:
        extract_project_section(
            args.json_file,
            args.output_dir,
        )

    except (json.JSONDecodeError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()