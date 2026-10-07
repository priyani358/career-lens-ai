"""Deterministic skill-gap engine. The numbers are computed, never LLM-invented."""
import re

LV = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}
ACTION = {1: "Start with fundamentals and one guided tutorial.",
          2: "Build a small project to move from basics to working proficiency.",
          3: "Deepen through a substantial project and real-world practice."}

def user_levels(profile):
    return {s["name"].strip().lower(): int(s["level"]) for s in profile.get("skills", [])}

def analyze(levels, career):
    rows = []
    for skill, req in career["skills"].items():
        cur = levels.get(skill.lower(), 0)
        gap = max(req - cur, 0)
        rows.append({"skill": skill, "current": cur, "current_label": LV.get(cur, "None"), "required": req,
                     "required_label": LV[req], "gap": gap, "gap_label": ["None", "Small", "Medium", "Large"][min(gap, 3)],
                     "action": ACTION[min(cur + 1, 3)] if gap else "Maintain through use."})
    total = sum(r["required"] for r in rows)
    covered = sum(min(r["current"], r["required"]) for r in rows)
    coverage = round(covered / total, 2) if total else 0.0
    method = ("No O*NET skill ratings are available for this occupation; skill coverage is not scored." if not total else
              "For each required skill: gap = required level - your level (Beginner=1, Intermediate=2, Advanced=3). "
              "Coverage = sum of min(your level, required) / sum of required levels.")
    return {"career_id": career["id"], "coverage": coverage, "rows": rows, "method": method}

def fit(levels, profile, career):
    return breakdown(levels, profile, career)["score"]


def breakdown(levels, profile, career):
    """Return the deterministic match components used to rank occupations."""
    cov = analyze(levels, career)["coverage"]
    profile_text = " ".join(profile.get("interests", []) + [profile.get("goals", ""), profile.get("industry", "")] + profile.get("roles", [])).lower()
    career_text = " ".join([career["name"], career["description"]] + career.get("tags", []) + list(career.get("skills", {})) +
                           [t["name"] for t in career.get("technology_skills", [])] + career.get("tasks", [])).lower()
    ignored = {"about", "after", "also", "from", "into", "more", "that", "their", "this", "want", "with", "work", "your", "career"}
    terms = {word for word in re.findall(r"[a-z0-9+#.-]{3,}", profile_text) if word not in ignored}
    career_terms = set(re.findall(r"[a-z0-9+#.-]{3,}", career_text))
    overlap = len(terms & career_terms) / max(len(terms), 1)
    interest_aliases = {
        "ai": {"artificial", "intelligence", "machine", "learning", "technology"},
        "data": {"data", "statistics", "analytics", "database"},
        "web": {"web", "software", "internet", "programming"},
        "design": {"design", "artistic", "creative", "visual"},
        "product": {"product", "business", "management", "development"},
        "cloud": {"cloud", "network", "computer", "infrastructure"},
        "research": {"research", "investigative", "science", "scientific"},
        "business": {"business", "enterprising", "management", "finance"},
        "llm": {"language", "model", "artificial", "intelligence"},
        "automation": {"automation", "technology", "systems", "programming"},
    }
    interests = {word for word in re.findall(r"[a-z0-9+#.-]+", " ".join(profile.get("interests", [])).lower())}
    interest_terms = {word for word in interests if len(word) >= 3} | set().union(*(interest_aliases.get(word, set()) for word in interests))
    tag = len(interest_terms & career_terms) / max(len(interest_terms), 1)
    role = 0.3 if any(career["name"].lower() in r.lower() or r.lower() in career["name"].lower() for r in profile.get("roles", []) if r) else 0
    score = 0.55 * cov + 0.25 * overlap + 0.2 * tag + role
    return {
        "skill_coverage": round(cov, 2),
        "profile_content_match": round(overlap, 2),
        "interest_match": round(tag, 2),
        "role_bonus": role,
        "weights": {"skill_coverage": 0.55, "profile_content_match": 0.25, "interest_match": 0.2},
        "score": round(score, 2),
    }
