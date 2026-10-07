"""Derived, single-source-of-truth career workspace data for each user."""
import re

from ..rag import store
from . import skill_gap

LEVEL_NAMES = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}


def estimate_weeks(text):
    match = re.search(r"(\d+(?:\.\d+)?)\s*(day|week|month)", (text or "").lower())
    if not match:
        return 1
    count, unit = float(match.group(1)), match.group(2)
    if unit == "day":
        return max(1, round(count / 7))
    return max(1, round(count if unit == "week" else count * 4))


def roadmap_progress(roadmap):
    if not roadmap:
        return None
    phases = [
        {"title": phase["title"], "done": sum(bool(item.get("done")) for item in phase["items"]), "total": len(phase["items"])}
        for phase in roadmap["phases"]
    ]
    total = sum(phase["total"] for phase in phases)
    done = sum(phase["done"] for phase in phases)
    return {"done": done, "total": total, "percent": round(100 * done / total) if total else 0, "phases": phases}


def weekly_plan(roadmap, weeks=4):
    """Lay the next unfinished roadmap tasks out into a short weekly plan."""
    if not roadmap:
        return []
    plan = []
    for phase in roadmap["phases"]:
        for item in phase["items"]:
            if item.get("done"):
                continue
            duration = estimate_weeks(item.get("estimated_time"))
            for part in range(duration):
                if len(plan) >= weeks:
                    return plan
                plan.append({
                    "week": len(plan) + 1,
                    "phase": phase["title"],
                    "item_id": item["id"],
                    "task": item["title"],
                    "part": f"{part + 1}/{duration}",
                    "skills": item.get("skills", []),
                })
    return plan


def resources_for(gap):
    """Find learning links for the largest exact-name skill gaps."""
    resources = store.resources()
    result = []
    for row in sorted((item for item in gap["rows"] if item["gap"]), key=lambda item: -item["gap"]):
        target_level = LEVEL_NAMES.get(min(row["current"] + 1, 3))
        matches = sorted(
            (resource for resource in resources if resource["skill"].casefold() == row["skill"].casefold()),
            key=lambda resource: resource["difficulty"].casefold() != target_level.casefold(),
        )
        for resource in matches[:2]:
            result.append({
                **resource,
                "for_skill": row["skill"],
                "reason": f"Closes your {row['skill']} gap ({row['current_label']} to {row['required_label']}).",
            })
    return result


def projects_for(career, gap):
    """Return only project ideas actually present in the selected occupation record."""
    gaps = [row["skill"] for row in sorted(gap["rows"], key=lambda item: -item["gap"]) if row["gap"]]
    projects = career.get("projects", []) or []
    return [
        {"title": project, "practises": [name for name in gaps if name.casefold() in project.casefold()] or gaps[:2]}
        for project in projects
    ]


def career_switch_options(levels, selected):
    baseline_effort = sum(row["gap"] for row in skill_gap.analyze(levels, selected)["rows"])
    options = []
    for career in store.careers():
        if career["id"] == selected["id"]:
            continue
        analysis = skill_gap.analyze(levels, career)
        effort = sum(row["gap"] for row in analysis["rows"])
        current_skills = {name.casefold() for name in selected.get("skills", {})}
        transferable = [row["skill"] for row in analysis["rows"] if not row["gap"]]
        options.append({
            "career_id": career["id"],
            "name": career["name"],
            "coverage": analysis["coverage"],
            "transferable": transferable,
            "new_skills": [row["skill"] for row in analysis["rows"] if row["gap"]],
            "effort": effort,
            "effort_vs_current": effort - baseline_effort,
            "shared_with_current": [name for name in career.get("skills", {}) if name.casefold() in current_skills],
        })
    return sorted(options, key=lambda item: (item["effort"], -item["coverage"]))[:5]


def select(db, user_id, career_id):
    from ..database import Selection
    db.merge(Selection(user_id=user_id, career_id=career_id))


def build(user, db):
    from ..database import Assessment, Roadmap, Selection

    profile = (user.profile.data if user.profile else {}) or {}
    assessment = db.query(Assessment).filter_by(user_id=user.id).order_by(Assessment.id.desc()).first()
    selection = db.get(Selection, user.id)
    if not selection and assessment and assessment.result.get("career_options"):
        # Migrate existing accounts into the connected flow using their top match.
        selection = Selection(user_id=user.id, career_id=assessment.result["career_options"][0]["career_id"])
        db.add(selection)
        db.commit()
    workspace = {
        "email": user.email,
        "profile": profile,
        "saved_careers": (user.profile.saved_careers or []) if user.profile else [],
        "assessment": assessment.result if assessment else None,
        "selected_career": None,
        "skill_gap": None,
        "roadmap": None,
        "progress": None,
        "weekly_plan": [],
        "resources": [],
        "projects": [],
        "switch_options": [],
    }
    career = next((item for item in store.careers() if selection and item["id"] == selection.career_id), None)
    if not career:
        return workspace

    levels = skill_gap.user_levels(profile)
    gap = skill_gap.analyze(levels, career)
    roadmap_record = db.query(Roadmap).filter_by(user_id=user.id, career_id=career["id"]).order_by(Roadmap.id.desc()).first()
    roadmap = {"roadmap_id": roadmap_record.id, "career_id": career["id"], **roadmap_record.data} if roadmap_record else None
    workspace.update(
        selected_career={key: career.get(key) for key in ("id", "name", "description", "certifications", "related", "onet_code", "onet_url", "job_zone")},
        skill_gap=gap,
        roadmap=roadmap,
        progress=roadmap_progress(roadmap),
        weekly_plan=weekly_plan(roadmap),
        resources=resources_for(gap),
        projects=projects_for(career, gap),
        switch_options=career_switch_options(levels, career),
    )
    return workspace


def coach_context(workspace):
    career = workspace["selected_career"]
    if not career:
        return "No career selected yet. Suggest completing the assessment and choosing a career."
    gap = workspace["skill_gap"]
    missing = [
        f"{row['skill']} ({row['current_label']} -> {row['required_label']})"
        for row in sorted(gap["rows"], key=lambda item: -item["gap"])
        if row["gap"]
    ]
    lines = [
        f"Selected career: {career['name']} (skill coverage {round(gap['coverage'] * 100)}%)",
        "Skills already meeting the target: " + (", ".join(row["skill"] for row in gap["rows"] if not row["gap"]) or "none"),
        "Skill gaps, largest first: " + ("; ".join(missing) or "none"),
    ]
    progress = workspace["progress"]
    lines.append(
        f"Roadmap progress: {progress['done']}/{progress['total']} tasks ({progress['percent']}%)"
        if progress else "No roadmap generated yet."
    )
    if workspace["weekly_plan"]:
        lines.append("Planned next: " + "; ".join(f"week {item['week']}: {item['task']}" for item in workspace["weekly_plan"][:2]))
    if workspace["roadmap"]:
        completed = [item["title"] for phase in workspace["roadmap"]["phases"] for item in phase["items"] if item.get("done")]
        if completed:
            lines.append("Completed tasks: " + "; ".join(completed[:8]))
    if workspace["switch_options"]:
        lines.append("Closest alternative careers by effort: " + ", ".join(option["name"] for option in workspace["switch_options"][:3]))
    return "\n".join(lines)
