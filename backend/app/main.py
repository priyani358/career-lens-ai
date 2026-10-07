import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional
import bcrypt, jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from . import config
from .database import Base, engine, get_db, User, Profile, Assessment, Roadmap, Conversation, Message, Selection
from .rag import store
from .services import career_recommender, llm_service as llm, prompts, skill_gap, workspace

app = FastAPI(title="CareerLens AI")
logger = logging.getLogger(__name__)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
Base.metadata.create_all(engine)
bearer = HTTPBearer()

@app.get("/api/health")
def health():
    key = config.OPENROUTER_API_KEY if config.LLM_PROVIDER == "openrouter" else config.ANTHROPIC_API_KEY
    configured = bool(key and key.strip() not in {"your_key_here", "change-me"})
    return {"status": "ok", "llm_provider": config.LLM_PROVIDER, "llm_model": config.MODEL,
            "llm_key_configured": configured, "llm_ready": configured}

@app.on_event("startup")
def startup():
    def ingest_in_background():
        try:
            logger.info("O*NET indexing complete: %s chunks", store.ingest())
        except Exception:
            logger.exception("O*NET indexing failed; rerun python -m app.rag.store to retry")
    threading.Thread(target=ingest_in_background, name="onet-indexer", daemon=True).start()

# ---------- schemas ----------
class Cred(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    password: str = Field(min_length=8, max_length=72)

class Skill(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    level: int = Field(ge=1, le=3)

class ProfileIn(BaseModel):
    education: str = Field("", max_length=100); degree: str = Field("", max_length=100); year: str = Field("", max_length=40)
    skills: list[Skill] = Field(default_factory=list, max_length=40)
    interests: list[str] = Field(default_factory=list, max_length=20)
    experience: str = Field("", max_length=1000); goals: str = Field("", max_length=1000)
    industry: str = Field("", max_length=100); roles: list[str] = Field(default_factory=list, max_length=10)

class CareerReq(BaseModel):
    career_id: str
class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=2000); conversation_id: Optional[int] = None
class ProgressReq(BaseModel):
    roadmap_id: int; item_id: str; done: bool

class RecOpt(BaseModel):
    career_id: str; why_it_may_fit: str; next_steps: list[str] = []
class RecOut(BaseModel):
    summary: str; strengths: list[str] = []; career_options: list[RecOpt]
class RoadItem(BaseModel):
    title: str; description: str; skills: list[str] = []; difficulty: str = "Intermediate"; estimated_time: str = ""; resources: list[str] = []
class RoadPhase(BaseModel):
    title: str; items: list[RoadItem]
class RoadOut(BaseModel):
    phases: list[RoadPhase]

# ---------- helpers ----------
def current_user(cred=Depends(bearer), db: Session = Depends(get_db)) -> User:
    try:
        uid = int(jwt.decode(cred.credentials, config.SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        raise HTTPException(401, "Session expired. Please log in again.")
    u = db.get(User, uid)
    if not u: raise HTTPException(401, "Unknown user.")
    return u

def token(uid): return jwt.encode({"sub": str(uid), "exp": datetime.utcnow() + timedelta(days=7)}, config.SECRET, "HS256")
def career_or_404(cid):
    c = next((c for c in store.careers() if c["id"] == cid), None)
    if not c: raise HTTPException(404, "Career not found")
    return c
def profile_of(u): return (u.profile.data if u.profile else {}) or {}
def profile_text(p): return f"{p.get('goals','')} skills: {', '.join(s['name'] for s in p.get('skills', []))} interests: {', '.join(p.get('interests', []))} {p.get('industry','')}"
def llm_http(e): return HTTPException(502, str(e))

def starter_roadmap(career, gap, resources):
    """Create a useful, transparent plan when the optional LLM is unavailable."""
    missing = sorted((row for row in gap["rows"] if row["gap"]), key=lambda row: (-row["gap"], row["skill"]))
    phases = []

    def item(title, description, skills, difficulty, duration, links=()):
        return {"title": title, "description": description, "skills": list(skills),
                "difficulty": difficulty, "estimated_time": duration, "resources": list(links), "done": False}

    foundation = []
    for row in missing[:4]:
        matches = [r["title"] for r in resources if r["skill"].casefold() == row["skill"].casefold()][:2]
        foundation.append(item(f"Learn {row['skill']} fundamentals", row["action"], [row["skill"]], "Beginner", "2 weeks", matches))
    if not foundation:
        foundation.append(item("Review the core skills for this occupation", "Choose one listed skill and refresh it through a short tutorial or guided practice.", list(career["skills"])[:3], "Beginner", "1 week"))
    phases.append({"title": "Build foundations", "items": foundation})

    practice = []
    for row in missing[4:8]:
        matches = [r["title"] for r in resources if r["skill"].casefold() == row["skill"].casefold()][:2]
        practice.append(item(f"Practice {row['skill']}", f"Apply this skill in a small exercise and record what you learned. {row['action']}", [row["skill"]], "Intermediate", "2 weeks", matches))
    if not practice:
        practice.append(item("Strengthen a role-critical skill", "Use a guided exercise to practise one skill required for the selected occupation.", list(career["skills"])[:2], "Intermediate", "2 weeks"))
    phases.append({"title": "Practice and apply", "items": practice})

    tasks = career.get("tasks", [])[:3]
    if tasks:
        project_items = [item("Prepare for this work activity", f"Break this occupation task into a small practice exercise and document your approach: {task}", list(career["skills"])[:3], "Intermediate", "1 week") for task in tasks]
    else:
        project_items = [item("Create a portfolio example", f"Build a small example that demonstrates {', '.join(list(career['skills'])[:3]) or career['name']} and explain your decisions.", list(career["skills"])[:3], "Intermediate", "2 weeks")]
    phases.append({"title": "Prepare for the work", "items": project_items})

    preparation = [item("Review your evidence of readiness", "Update your resume or portfolio with the skills you practised, then identify one next learning goal.", [row["skill"] for row in missing[:3]], "Intermediate", "1 week")]
    phases.append({"title": "Career preparation", "items": preparation})
    return {"phases": phases, "ai_note": "Generated with the built-in O*NET-based planner because the AI provider is unavailable. This plan is a starting point, not an official O*NET recommendation."}

# ---------- auth ----------
@app.post("/api/auth/register")
def register(c: Cred, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=c.email.lower()).first(): raise HTTPException(409, "Email already registered")
    u = User(email=c.email.lower(), pw_hash=bcrypt.hashpw(c.password.encode(), bcrypt.gensalt()).decode())
    db.add(u); db.flush(); db.add(Profile(user_id=u.id, data={}, saved_careers=[])); db.commit()
    return {"token": token(u.id)}

@app.post("/api/auth/login")
def login(c: Cred, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=c.email.lower()).first()
    if not u or not bcrypt.checkpw(c.password.encode(), u.pw_hash.encode()): raise HTTPException(401, "Invalid email or password")
    return {"token": token(u.id)}

# ---------- profile ----------
@app.get("/api/profile")
def get_profile(u: User = Depends(current_user)):
    return {"email": u.email, "profile": profile_of(u), "saved_careers": u.profile.saved_careers or []}

@app.post("/api/profile")
def save_profile(p: ProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    u.profile.data = p.model_dump(); db.commit(); return {"ok": True}

@app.post("/api/profile/save-career")
def save_career(r: CareerReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    career_or_404(r.career_id)
    s = list(u.profile.saved_careers or [])
    u.profile.saved_careers = [x for x in s if x != r.career_id] if r.career_id in s else s + [r.career_id]
    db.commit(); return {"saved_careers": u.profile.saved_careers}

# ---------- knowledge ----------
@app.get("/api/skills")
def skills(): return sorted({s for c in store.careers() for s in c["skills"]})
@app.get("/api/careers")
def careers(): return [{k: c[k] for k in ("id", "name", "description", "skills", "onet_code", "job_zone", "onet_url", "technology_skills")} for c in store.careers()]

@app.get("/api/career-search")
def career_search(q: str = "", job_zone: Optional[int] = None, limit: int = 20, offset: int = 0):
    """Search the O*NET occupation catalog by title, skill, task, or technology."""
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    terms = [term.casefold() for term in q.split() if term.strip()]
    matches = []
    for career in store.careers():
        if job_zone is not None and career.get("job_zone") != job_zone:
            continue
        name = career["name"].casefold()
        description = career["description"].casefold()
        skills_text = " ".join(career.get("skills", {})).casefold()
        tasks_text = " ".join(career.get("tasks", [])).casefold()
        tech_text = " ".join(item["name"] for item in career.get("technology_skills", [])).casefold()
        searchable = f"{name} {description} {skills_text} {tasks_text} {tech_text}"
        if terms and not all(term in searchable for term in terms):
            continue
        score = sum(5 if term in name else 3 if term in skills_text else 2 if term in tasks_text or term in tech_text else 1 for term in terms)
        matches.append((score, career))
    matches.sort(key=lambda item: (-item[0], item[1]["name"].casefold()))
    page = matches[offset:offset + limit]
    return {
        "items": [{
            "id": career["id"], "name": career["name"], "description": career["description"],
            "onet_code": career.get("onet_code"), "job_zone": career.get("job_zone"),
            "onet_url": career.get("onet_url"), "skills": career.get("skills", {}),
            "tasks": career.get("tasks", [])[:3],
            "technology_skills": career.get("technology_skills", [])[:5],
        } for _, career in page],
        "total": len(matches), "limit": limit, "offset": offset,
    }

@app.get("/api/careers/{cid}")
def career(cid: str): return career_or_404(cid)
@app.get("/api/resources")
def resources(skill: Optional[str] = None, difficulty: Optional[str] = None, type: Optional[str] = None):
    return [r for r in store.resources() if (not skill or r["skill"] == skill) and (not difficulty or r["difficulty"] == difficulty) and (not type or r["type"] == type)]

# ---------- AI features ----------
@app.post("/api/assessment")
def assessment(p: ProfileIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    u.profile.data = p.model_dump(); pd = u.profile.data
    levels = skill_gap.user_levels(pd)
    ranked_model = career_recommender.rank_careers(pd, store.careers(), limit=5)
    ranked = [item["career"] for item in ranked_model]
    model_scores = {item["career"]["id"]: item["breakdown"] for item in ranked_model}
    gaps = {c["id"]: skill_gap.analyze(levels, c) for c in ranked}
    ctx = store.retrieve(profile_text(pd), k=6)
    payload = {"profile": pd, "candidates": [{"career_id": c["id"], "name": c["name"], "coverage": gaps[c["id"]]["coverage"],
               "gaps": [r for r in gaps[c["id"]]["rows"] if r["gap"]]} for c in ranked], "retrieved_context": ctx}
    ai, note = None, None
    try:
        ai = llm.complete_json(prompts.RECOMMEND, json.dumps(payload), RecOut)
    except llm.LLMError as e:
        if e.code == "authentication":
            variable = "OPENROUTER_API_KEY" if config.LLM_PROVIDER == "openrouter" else "ANTHROPIC_API_KEY"
            provider = "OpenRouter" if config.LLM_PROVIDER == "openrouter" else "Anthropic"
            note = f"{provider} rejected the configured key. Check {variable} in backend/.env (a shell environment variable overrides .env), then restart the backend. Showing computed O*NET-based explanations for now."
        elif e.code == "missing_api_key":
            variable = "OPENROUTER_API_KEY" if config.LLM_PROVIDER == "openrouter" else "ANTHROPIC_API_KEY"
            note = f"AI explanations are disabled because {variable} is not configured. Add your provider key to backend/.env and restart the backend. These recommendations use computed profile matches and O*NET data."
        else:
            logger.warning("AI assessment explanation unavailable (%s): %s", e.code, e)
            note = f"The AI explanation could not be generated: {e} Showing computed O*NET-based explanations for now."
    why = {o.career_id: o for o in ai.career_options} if ai else {}
    options = [{"career_id": c["id"], "name": c["name"], "description": c["description"], "coverage": gaps[c["id"]]["coverage"],
                "onet_code": c.get("onet_code"), "onet_url": c.get("onet_url"), "job_zone": c.get("job_zone"),
                "tasks": c.get("tasks", [])[:5], "technology_skills": c.get("technology_skills", [])[:8],
                "breakdown": model_scores[c["id"]],
                "have": [r["skill"] for r in gaps[c["id"]]["rows"] if not r["gap"]],
                "missing": [r["skill"] for r in gaps[c["id"]]["rows"] if r["gap"]],
                "label": "Potentially suitable based on your profile",
                "why_it_may_fit": why[c["id"]].why_it_may_fit if c["id"] in why else
                    (f"Your profile already meets the listed O*NET skill level for {', '.join([r['skill'] for r in gaps[c['id']]['rows'] if not r['gap']][:4])}. " if any(not r["gap"] for r in gaps[c["id"]]["rows"]) else "") +
                    f"This is a computed match using your profile and O*NET occupation data; skill coverage is {round(gaps[c['id']]['coverage'] * 100)}%.",
                "next_steps": why[c["id"]].next_steps if c["id"] in why else
                    [r["action"] + " Focus on " + r["skill"] + "." for r in gaps[c["id"]]["rows"] if r["gap"]][:3]} for c in ranked]
    result = {"summary": ai.summary if ai else "These potential career matches are ranked by a content-based model using your profile and O*NET occupational data. Add a supported LLM provider key for generated explanations.",
              "strengths": ai.strengths if ai else [s["name"] for s in pd["skills"] if s["level"] >= 2],
              "career_options": options, "ai_note": note,
              "recommendation_model": "O*NET content-based TF-IDF + deterministic skill coverage, interest and role-fit signals",
              "retrieved_evidence": ctx}
    if db.get(Selection, u.id) is None and ranked:
        workspace.select(db, u.id, ranked[0]["id"])
    db.add(Assessment(user_id=u.id, result=result)); db.commit()
    return result

@app.get("/api/assessment/latest")
def latest(u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.query(Assessment).filter_by(user_id=u.id).order_by(Assessment.id.desc()).first()
    return a.result if a else None

@app.post("/api/skill-gap")
def skill_gap_ep(r: CareerReq, u: User = Depends(current_user)):
    return skill_gap.analyze(skill_gap.user_levels(profile_of(u)), career_or_404(r.career_id))

@app.post("/api/roadmap")
def roadmap(r: CareerReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = career_or_404(r.career_id); pd = profile_of(u)
    gap = skill_gap.analyze(skill_gap.user_levels(pd), c)
    retrieved = store.retrieve(f"{c['name']} roadmap {profile_text(pd)}", 4)
    payload = {"profile": pd, "career": c["name"], "gaps": [x for x in gap["rows"] if x["gap"]], "projects": c.get("projects", []),
               "occupation_tasks": c.get("tasks", [])[:10], "technology_skills": c.get("technology_skills", [])[:20],
               "certifications": c.get("certifications", []), "retrieved_context": retrieved,
               "resource_list": [{"title": x["title"], "skill": x["skill"]} for x in store.resources()]}
    try:
        out = llm.complete_json(prompts.ROADMAP, json.dumps(payload), RoadOut, 5000)
        phases = [
            {"title": phase.title, "items": [{**it.model_dump(), "id": f"{i}-{j}", "done": False} for j, it in enumerate(phase.items)]}
            for i, phase in enumerate(out.phases)
        ]
        ai_note = None
    except llm.LLMError as e:
        logger.info("Using deterministic roadmap fallback (%s): %s", e.code, e)
        fallback = starter_roadmap(c, gap, store.resources())
        phases = [
            {"title": phase["title"], "items": [{**it, "id": f"{i}-{j}"} for j, it in enumerate(phase["items"])]}
            for i, phase in enumerate(fallback["phases"])
        ]
        ai_note = fallback["ai_note"]
    data = {"phases": phases, "retrieved_evidence": retrieved, "ai_note": ai_note}
    rm = Roadmap(user_id=u.id, career_id=c["id"], data=data); db.add(rm)
    workspace.select(db, u.id, c["id"]); db.commit()
    return {"roadmap_id": rm.id, "career_id": c["id"], **data}

@app.get("/api/roadmap/latest")
def roadmap_latest(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rm = db.query(Roadmap).filter_by(user_id=u.id).order_by(Roadmap.id.desc()).first()
    return {"roadmap_id": rm.id, "career_id": rm.career_id, **rm.data} if rm else None

@app.post("/api/progress")
def progress(r: ProgressReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    rm = db.get(Roadmap, r.roadmap_id)
    if not rm or rm.user_id != u.id: raise HTTPException(404, "Roadmap not found")
    d = json.loads(json.dumps(rm.data))
    for ph in d["phases"]:
        for it in ph["items"]:
            if it["id"] == r.item_id: it["done"] = r.done
    rm.data = d; db.commit(); return {"ok": True}

@app.get("/api/conversations")
def conversations(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": c.id, "title": c.title} for c in db.query(Conversation).filter_by(user_id=u.id).order_by(Conversation.id.desc())]

@app.get("/api/conversations/{cid}")
def conversation(cid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, cid)
    if not c or c.user_id != u.id: raise HTTPException(404, "Not found")
    return [{"role": m.role, "content": m.content} for m in c.messages]

@app.post("/api/chat")
def chat(r: ChatReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(Conversation, r.conversation_id) if r.conversation_id else None
    if c and c.user_id != u.id: raise HTTPException(404, "Not found")
    if not c:
        c = Conversation(user_id=u.id, title=r.message[:50]); db.add(c); db.flush()
    pd = profile_of(u)
    retrieved = store.retrieve(f"{r.message} {profile_text(pd)}", 5)
    ctx = "\n".join(f"[{x['career_name']} · {x['chunk_type']} · {', '.join(x['retrieved_by'])}] {x['text']}" for x in retrieved)
    current_workspace = workspace.build(u, db)
    system = (f"{prompts.CHAT}\n\nUSER PROFILE:\n{json.dumps(pd) if pd else 'Not provided yet - consider suggesting the assessment.'}"
              f"\n\nCAREER WORKSPACE (computed by the app; treat as ground truth):\n{workspace.coach_context(current_workspace)}"
              f"\n\nRETRIEVED CONTEXT:\n{ctx}")
    hist = [{"role": m.role, "content": m.content} for m in c.messages[-10:]] + [{"role": "user", "content": r.message}]
    try: reply = llm.complete(system, hist, 1500)
    except llm.LLMError as e:
        db.rollback(); raise HTTPException(502, "The assistant is unavailable right now. Please try again. (" + str(e) + ")")
    db.add(Message(conversation_id=c.id, role="user", content=r.message)); db.add(Message(conversation_id=c.id, role="assistant", content=reply))
    db.commit(); return {"conversation_id": c.id, "reply": reply, "retrieved_evidence": retrieved}

# ---------- connected career workspace ----------
@app.get("/api/workspace")
def get_workspace(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return workspace.build(u, db)

@app.post("/api/select-career")
def select_career(r: CareerReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    career_or_404(r.career_id)
    workspace.select(db, u.id, r.career_id)
    db.commit()
    return workspace.build(u, db)
