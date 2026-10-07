"""End-to-end, explainable O*NET career recommender.

This is a content-based TF-IDF model: it learns occupation term weights from the
whole O*NET catalog and combines profile similarity with measured skill coverage,
interest fit, and explicit role preference. It does not claim to be supervised
or trained on job-placement outcomes.
"""
import math
import re
from collections import Counter

from .skill_gap import analyze

TOKEN = re.compile(r"[a-z0-9+#.-]+")
STOP_WORDS = {
    "about", "after", "also", "and", "are", "based", "being", "build", "career", "from",
    "have", "into", "more", "our", "that", "the", "their", "them", "there", "these",
    "they", "this", "through", "want", "with", "work", "your",
}
INTEREST_CONCEPTS = {
    "ai": {"artificial", "intelligence", "machine", "learning", "technology", "computer"},
    "llm": {"language", "model", "natural", "processing", "artificial", "intelligence"},
    "data": {"data", "statistics", "analytics", "mathematics", "database", "research"},
    "web": {"web", "software", "internet", "programming", "computer"},
    "design": {"design", "artistic", "creative", "visual", "originality"},
    "product": {"product", "business", "management", "development", "innovation"},
    "cloud": {"cloud", "network", "computer", "infrastructure", "systems"},
    "research": {"research", "investigative", "science", "scientific", "analytical"},
    "business": {"business", "enterprising", "management", "finance", "sales"},
    "automation": {"automation", "technology", "systems", "programming", "computer"},
}


def tokenize(text):
    return [token for token in TOKEN.findall((text or "").casefold()) if len(token) > 1 and token not in STOP_WORDS]


def occupation_text(career):
    technology = [item.get("name", "") for item in career.get("technology_skills", [])]
    return " ".join([
        career.get("name", ""), career.get("description", ""),
        *career.get("tags", []), *career.get("skills", {}).keys(),
        *career.get("tasks", []), *technology,
    ])


def profile_text(profile):
    skills = [item.get("name", "") for item in profile.get("skills", [])]
    roles = profile.get("roles", [])
    fields = [profile.get("goals", ""), profile.get("experience", ""), profile.get("industry", ""), profile.get("degree", ""), profile.get("education", "")]
    return " ".join([*fields, *skills, *profile.get("interests", []), *roles])


def _tfidf(tokens, idf):
    frequencies = Counter(tokens)
    if not frequencies:
        return {}
    length = len(tokens)
    return {term: (1 + math.log(count)) * idf.get(term, 0.0) for term, count in frequencies.items()}


def _cosine(left, right):
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(term, 0.0) for term, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _interest_score(profile, career):
    interests = [value.casefold().strip() for value in profile.get("interests", []) if value.strip()]
    if not interests:
        return 0.0
    occupation_terms = set(tokenize(occupation_text(career)))
    occupation_tags = {tag.casefold() for tag in career.get("tags", [])}
    scores = []
    for interest in interests:
        aliases = set(INTEREST_CONCEPTS.get(interest, {interest})) | {interest}
        matches = sum(1 for alias in aliases if alias in occupation_terms or alias in occupation_tags)
        scores.append(matches / max(len(aliases), 1))
    return sum(scores) / len(scores)


def _role_score(profile, career):
    requested = [value.casefold().strip() for value in profile.get("roles", []) if value.strip()]
    if not requested:
        return 0.0
    title = career.get("name", "").casefold()
    occupation_tokens = set(tokenize(title))
    scores = []
    for role in requested:
        if role in title or title in role:
            scores.append(1.0)
            continue
        role_tokens = set(tokenize(role))
        scores.append(len(role_tokens & occupation_tokens) / max(len(role_tokens), 1))
    return max(scores, default=0.0)


def rank_careers(profile, careers, limit=5):
    """Fit a TF-IDF profile vector against O*NET occupation text and rank candidates."""
    careers = list(careers)
    if not careers:
        return []
    tokenized_careers = [tokenize(occupation_text(career)) for career in careers]
    document_frequency = Counter(term for tokens in tokenized_careers for term in set(tokens))
    total = len(careers)
    inverse_document_frequency = {
        term: math.log(1 + (total + 1) / (frequency + 1)) + 1
        for term, frequency in document_frequency.items()
    }
    occupation_vectors = [_tfidf(tokens, inverse_document_frequency) for tokens in tokenized_careers]
    profile_tokens = tokenize(profile_text(profile))
    profile_vector = _tfidf(profile_tokens, inverse_document_frequency)
    # Skill levels remain a separate deterministic signal; they are never inferred from prose.
    skill_levels = {item["name"].casefold().strip(): int(item["level"]) for item in profile.get("skills", [])}
    ranked = []
    for career, vector in zip(careers, occupation_vectors):
        skill_coverage = analyze(skill_levels, career)["coverage"]
        text_similarity = _cosine(profile_vector, vector)
        interest_fit = _interest_score(profile, career)
        role_fit = _role_score(profile, career)
        score = 0.50 * skill_coverage + 0.25 * text_similarity + 0.15 * interest_fit + 0.10 * role_fit
        components = {
            "skill_coverage": round(skill_coverage, 4),
            "profile_similarity": round(text_similarity, 4),
            "interest_fit": round(interest_fit, 4),
            "role_fit": round(role_fit, 4),
            "weights": {"skill_coverage": 0.50, "profile_similarity": 0.25, "interest_fit": 0.15, "role_fit": 0.10},
            "score": round(score, 4),
            "model": "O*NET content-based TF-IDF + deterministic skill coverage",
        }
        ranked.append((score, career, components))
    ranked.sort(key=lambda item: (-item[0], item[1].get("name", "").casefold()))
    return [{"career": career, "score": score, "breakdown": breakdown} for score, career, breakdown in ranked[:max(1, limit)]]
