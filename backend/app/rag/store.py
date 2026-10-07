"""RAG: careers.json -> chunks -> Chroma embeddings -> similarity search."""
import json, pathlib
from functools import lru_cache
import chromadb
from .hybrid import BM25, reciprocal_rank_fusion

ROOT = pathlib.Path(__file__).resolve().parents[3]
BACKEND = pathlib.Path(__file__).resolve().parents[2]
LV = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}
ONET_DATA = ROOT / "data/onet/careers_31_0.json"
ONET_COLLECTION_NAME = "onet_31_0"

@lru_cache
def careers():
    path = ONET_DATA if ONET_DATA.exists() else ROOT / "data/careers/careers.json"
    data = json.loads(path.read_text())
    return data["occupations"] if isinstance(data, dict) else data

@lru_cache
def resources():
    return json.loads((ROOT / "data/resources/resources.json").read_text())

@lru_cache
def collection():
    return chromadb.PersistentClient(path=str(BACKEND / "chroma_db")).get_or_create_collection(ONET_COLLECTION_NAME)

def chunk(c):
    skills = ", ".join(f"{k} ({LV[v]})" for k, v in c["skills"].items())
    zone = f"Job Zone {c['job_zone']}" if c.get("job_zone") else "Job zone not available"
    tasks = "; ".join(c.get("tasks", [])[:4])
    overview = f"{c['name']} ({c.get('onet_code', '')}): {c['description']} {zone}. O*NET career interests: {', '.join(c['tags'])}. Core work activities: {tasks}."
    technologies = [t["name"] for t in c.get("technology_skills", [])]
    skill_doc = f"{c['name']} essential and transferable skills (O*NET importance mapped to CareerLens levels): {skills}. Hot or in-demand technologies: {'; '.join(technologies[:12])}."
    yield "overview", overview
    yield "skills", skill_doc

def ingest(force=False, collection_name=None):
    global ONET_COLLECTION_NAME
    if collection_name is not None:
        ONET_COLLECTION_NAME = collection_name
    col = collection()
    ids, docs, metas = [], [], []
    for c in careers():
        for kind, text in chunk(c):
            ids.append(f"{c['id']}:{kind}"); docs.append(text); metas.append({"career_id": c["id"], "onet_code": c.get("onet_code", ""), "chunk_type": kind})
    stored = col.get(include=["documents", "metadatas"])
    existing = {
        item_id: (document, metadata)
        for item_id, document, metadata in zip(stored["ids"], stored["documents"], stored["metadatas"])
    }
    desired = set(ids)
    if force:
        if existing:
            col.delete(ids=list(existing))
        existing = {}
    else:
        stale = set(existing) - desired
        if stale:
            col.delete(ids=list(stale))
            for item_id in stale:
                del existing[item_id]
        changed = [item_id for item_id, document, metadata in zip(ids, docs, metas)
                   if item_id in existing and existing[item_id] != (document, metadata)]
        if changed:
            col.delete(ids=changed)
            for item_id in changed:
                del existing[item_id]
    pending = [(i, doc, meta) for i, doc, meta in zip(ids, docs, metas) if i not in existing]
    for start in range(0, len(pending), 100):
        batch = pending[start:start + 100]
        col.add(ids=[item[0] for item in batch], documents=[item[1] for item in batch], metadatas=[item[2] for item in batch])
    _keyword_index.cache_clear()
    return col.count()

@lru_cache(maxsize=4)
def _keyword_index(collection_name):
    col = collection() if collection_name == ONET_COLLECTION_NAME else chromadb.PersistentClient(path=str(BACKEND / "chroma_db")).get_or_create_collection(collection_name)
    data = col.get()
    return data["ids"], data["documents"], data["metadatas"], BM25(data["documents"])

def retrieve(query, k=6, collection_name=None):
    name = collection_name or ONET_COLLECTION_NAME
    ids, docs, metas, bm25 = _keyword_index(name)
    if not ids:
        return []
    col = collection() if name == ONET_COLLECTION_NAME else chromadb.PersistentClient(path=str(BACKEND / "chroma_db")).get_or_create_collection(name)
    semantic_ranking = []
    try:
        semantic_ids = col.query(query_texts=[query], n_results=min(len(ids), k * 2))["ids"][0]
        positions = {item_id: position for position, item_id in enumerate(ids)}
        semantic_ranking = [positions[item_id] for item_id in semantic_ids if item_id in positions]
    except Exception:
        # Keep keyword retrieval available if the embedding model/index is unavailable.
        pass
    keyword_scores = bm25.scores(query)
    keyword_ranking = [position for position in sorted(range(len(keyword_scores)), key=lambda n: keyword_scores[n], reverse=True)
                       if keyword_scores[position] > 0][:k * 2]
    ranked = reciprocal_rank_fusion([semantic_ranking, keyword_ranking])[:k]
    semantic_positions, keyword_positions = set(semantic_ranking), set(keyword_ranking)
    rrf_scores = {}
    for ranking in (semantic_ranking, keyword_ranking):
        for rank, position in enumerate(ranking):
            rrf_scores[position] = rrf_scores.get(position, 0.0) + 1 / (60 + rank + 1)
    catalog = {career["id"]: career for career in careers()}
    results = []
    for position in ranked:
        metadata = metas[position]
        career_id = metadata["career_id"]
        career = catalog.get(career_id, {})
        onet_code = metadata.get("onet_code") or career.get("onet_code")
        results.append({
            "text": docs[position],
            "career_id": career_id,
            "career_name": career.get("name", career_id),
            "chunk_type": metadata.get("chunk_type", "occupation"),
            "onet_code": onet_code,
            "source_url": career.get("onet_url"),
            "retrieved_by": [
                method for method, positions in (("semantic", semantic_positions), ("keyword", keyword_positions))
                if position in positions
            ],
            "rrf_score": round(rrf_scores.get(position, 0.0), 5),
        })
    return results

if __name__ == "__main__":
    print("Ingested chunks:", ingest(force=True))
