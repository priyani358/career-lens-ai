"""Convert the official O*NET CSV database archive to CareerLens occupation JSON."""
import argparse
import csv
import json
import pathlib
import zipfile
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
SOURCE = "https://www.onetcenter.org/database.html"


def rows(archive, filename):
    path = f"db_31_0_csv/{filename}"
    with archive.open(path) as stream:
        for row in csv.DictReader(line.decode("utf-8-sig") for line in stream):
            yield row


def career_id(code):
    return "onet-" + code.replace(".", "-")


def import_database(archive_path, output_path):
    with zipfile.ZipFile(archive_path) as archive:
        occupations = {
            row["O*NET-SOC Code"]: {
                "id": career_id(row["O*NET-SOC Code"]),
                "onet_code": row["O*NET-SOC Code"],
                "name": row["Title"],
                "description": row["Description"],
                "skills": {},
                "skill_ratings": [],
                "technology_skills": [],
                "tasks": [],
                "tags": [],
                "projects": [],
                "certifications": [],
                "related": [],
                "job_zone": None,
                "onet_url": f"https://www.onetonline.org/link/summary/{row['O*NET-SOC Code']}",
            }
            for row in rows(archive, "occupation_data.csv")
        }

        skill_values = defaultdict(dict)
        for filename, category in (("essential_skills.csv", "Essential"), ("transferable_skills.csv", "Transferable")):
            for row in rows(archive, filename):
                code = row["O*NET-SOC Code"]
                if code not in occupations or row["Scale ID"] != "IM":
                    continue
                name = row["Element Name"]
                importance = float(row["Data Value"])
                skill_values[code][name] = max(skill_values[code].get(name, 0.0), importance)
                occupations[code]["skill_ratings"].append({
                    "name": name,
                    "importance": importance,
                    "category": category,
                })

        for code, values in skill_values.items():
            for name, importance in values.items():
                # O*NET importance (1-5) is mapped to CareerLens' 3-level scale.
                level = 1 if importance < 3 else 2 if importance < 4 else 3
                occupations[code]["skills"][name] = level

        tech_seen = defaultdict(set)
        for row in rows(archive, "software_skills.csv"):
            code = row["O*NET-SOC Code"]
            if code not in occupations:
                continue
            name = row["Workplace Example"].strip()
            if not name or name.casefold() in tech_seen[code]:
                continue
            hot = row["Hot Technology"].strip().upper() == "Y"
            in_demand = row["In Demand"].strip().upper() == "Y"
            if hot or in_demand:
                tech_seen[code].add(name.casefold())
                occupations[code]["technology_skills"].append({
                    "name": name,
                    "hot": hot,
                    "in_demand": in_demand,
                })

        for row in rows(archive, "task_statements.csv"):
            code = row["O*NET-SOC Code"]
            if code in occupations and row["Task Type"].strip().casefold() == "core":
                occupations[code]["tasks"].append(row["Task"].strip())

        for row in rows(archive, "job_zones.csv"):
            if row["O*NET-SOC Code"] in occupations:
                occupations[row["O*NET-SOC Code"]]["job_zone"] = int(row["Job Zone"])

        interests = defaultdict(list)
        for row in rows(archive, "career_interest_types.csv"):
            code = row["O*NET-SOC Code"]
            if code in occupations:
                interests[code].append((float(row["Data Value"]), row["Element Name"]))
        for code, values in interests.items():
            occupations[code]["tags"] = [name for _, name in sorted(values, reverse=True)[:3]]

        related = defaultdict(list)
        for row in rows(archive, "related_occupations.csv"):
            code = row["O*NET-SOC Code"]
            if code in occupations and row["Related O*NET-SOC Code"] in occupations:
                related[code].append(career_id(row["Related O*NET-SOC Code"]))
        for code, ids in related.items():
            occupations[code]["related"] = ids[:10]

    data = {
        "source": "O*NET 31.0 Database, U.S. Department of Labor, Employment and Training Administration",
        "source_url": SOURCE,
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "modifications": "Occupation skill importance ratings are mapped to CareerLens' three-level scale; only hot/in-demand technology examples and core tasks are retained; no projects or certifications are inferred.",
        "occupations": sorted(occupations.values(), key=lambda item: item["name"].casefold()),
    }
    output_path = pathlib.Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(occupations), output_path.stat().st_size


def main():
    parser = argparse.ArgumentParser(description="Import the official O*NET 31.0 CSV database.")
    parser.add_argument("archive", help="Path to the O*NET 31.0 CSV zip download")
    parser.add_argument("--output", default=str(ROOT / "data/onet/careers_31_0.json"), help="CareerLens JSON output path")
    args = parser.parse_args()
    count, size = import_database(args.archive, args.output)
    print(f"Imported {count} O*NET occupations into {args.output} ({size:,} bytes).")


if __name__ == "__main__":
    main()
