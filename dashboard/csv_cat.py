import csv
from datetime import datetime
from pathlib import Path


TIMESTAMP_COLUMNS = (
    ("Timestamp\xa0for\xa0sample\xa0frequency\xa0every\xa01 min\xa0min", None),
    ("Time(DD/MM/YYYY h:mm:ss A)", "%d/%m/%Y %I:%M:%S %p"),
)


def _rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _normalize(row, input_path):
    row = dict(row)
    for column, date_format in TIMESTAMP_COLUMNS:
        if row.get(column):
            value = row.pop(column)
            row["Time"] = datetime.strptime(value, date_format).isoformat(" ") if date_format else value
            break

    if not row.get("Sensor name"):
        name = Path(input_path).stem.split("_", 1)[0]
        building, separator, location = name.rpartition("-")
        if not separator:
            raise ValueError("CSV filename must start with <building>-<location>.")
        row.update({"Sensor name": name, "Building": building, "Location": location})
    return row


def concatenate(input_path: str, output_path: str) -> None:
    output = Path(output_path)
    rows = _rows(output) if output.exists() and output.stat().st_size else []
    rows.extend(_normalize(row, input_path) for row in _rows(input_path))
    if not rows:
        raise ValueError("No CSV measurements were found.")
    rows = list({(row.get("Time"), row.get("Sensor name")): row for row in rows}.values())
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
