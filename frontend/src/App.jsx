import { useEffect, useRef, useState } from "react";
import { api, auth } from "./api.js";

const LV = ["", "Beginner", "Intermediate", "Advanced"];
const INTERESTS = ["AI", "Data", "Web", "Design", "Product", "Cloud", "Research", "Business", "LLM", "Automation"];

function DataAttribution() {
  return <footer className="data-attribution">Career information adapted from the <a href="https://www.onetcenter.org/database.html">O*NET® 31.0 Database</a> by the U.S. Department of Labor, Employment and Training Administration, under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. CareerLens modified selected data; O*NET is a trademark of USDOL/ETA. Not affiliated with or endorsed by USDOL/ETA.</footer>;
}

function Bar({ value, max = 3, label }) {
  return <div className="bar" role="img" aria-label={label}><span style={{ width: `${(value / max) * 100}%` }} /></div>;
}

function Landing({ onStart }) {
  return (
    <main className="landing">
      <section className="landing-hero">
        <div className="landing-copy"><p className="eyebrow">Career intelligence platform</p>
          <h1>Find the direction<br />that <em>fits you.</em></h1>
          <p className="lead">CareerLens AI connects your skills, interests and ambitions to a clearer path forward.</p>
          <button className="btn" onClick={onStart}>Start your assessment <span aria-hidden="true">→</span></button>
        </div>
        <div className="career-map" aria-label="A map of connected career paths">
          <svg viewBox="0 0 560 380" role="img" aria-label="Career map connecting AI engineering, data science, product, design, software and analytics">
            <circle cx="270" cy="190" r="150" className="map-halo" /><circle cx="270" cy="190" r="95" className="map-orbit" />
            {[[150,90],[330,60],[470,170],[400,300],[190,290],[70,200]].map(([x,y], i, nodes) => <g key={i}>
              <line x1="270" y1="190" x2={x} y2={y} className="map-spoke" />
              <line x1={x} y1={y} x2={nodes[(i + 1) % nodes.length][0]} y2={nodes[(i + 1) % nodes.length][1]} className="map-link" />
            </g>)}
            <circle cx="270" cy="190" r="26" className="map-you" /><text x="270" y="194" textAnchor="middle" className="map-label you">YOU</text>
            {[["AI ENGINEERING",150,90],["DATA SCIENCE",330,60],["PRODUCT",470,170],["DESIGN",400,300],["SOFTWARE",190,290],["ANALYTICS",70,200]].map(([label,x,y],i) => <g key={label}>
              <circle cx={x} cy={y} r="9" className={`map-node node-${i}`} /><text x={x} y={y + (y > 190 ? 28 : -18)} textAnchor="middle" className="map-label">{label}</text>
            </g>)}
          </svg>
        </div>
      </section>
      <p className="eyebrow journey-label">Your career journey, organized.</p>
      <section className="journey-steps">{[["01", "Discover", "Find suitable directions based on who you are and what you enjoy."], ["02", "Understand", "See exactly where your skill gaps are and how they were measured."], ["03", "Build", "Follow a personal roadmap and track each step as you go."]].map(([n, title, text]) => <article key={n}><b>{n}</b><h3>{title}</h3><p>{text}</p></article>)}</section>
      <DataAttribution />
    </main>
  );
}

function Auth({ onDone }) {
  const [mode, setMode] = useState("login"), [email, setEmail] = useState(""), [pw, setPw] = useState(""), [err, setErr] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setErr("");
    try { const r = await api(`/auth/${mode}`, { email, password: pw }); auth.set(r.token); onDone(); } catch (x) { setErr(x.message); }
  };
  return (
    <form className="glass narrow" onSubmit={submit}>
      <h2>{mode === "login" ? "Log in" : "Create account"}</h2>
      <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
      <label>Password (8+ characters)<input type="password" minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} required /></label>
      {err && <p role="alert" className="err">{err}</p>}
      <button className="btn">{mode === "login" ? "Log in" : "Register"}</button>
      <button type="button" className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Need an account?" : "Have an account?"}</button>
    </form>
  );
}

function Assessment({ initial, onResult }) {
  const [step, setStep] = useState(0), [vocab, setVocab] = useState([]), [custom, setCustom] = useState("");
  const [p, setP] = useState({ education: "", degree: "", year: "", skills: [], interests: [], experience: "", goals: "", industry: "", roles: [], ...initial });
  const [busy, setBusy] = useState(""), [err, setErr] = useState("");
  useEffect(() => { api("/skills").then(setVocab).catch(() => {}); }, []);
  const set = (k, v) => setP((o) => ({ ...o, [k]: v }));
  const lvl = (n) => p.skills.find((s) => s.name === n)?.level;
  const toggleSkill = (n) => set("skills", lvl(n) ? p.skills.filter((s) => s.name !== n) : [...p.skills, { name: n, level: 1 }]);
  const setLvl = (n, level) => set("skills", p.skills.map((s) => (s.name === n ? { ...s, level } : s)));
  const toggleInt = (i) => set("interests", p.interests.includes(i) ? p.interests.filter((x) => x !== i) : [...p.interests, i]);
  const run = async () => {
    setErr(""); setBusy("Finding relevant career information…");
    const t = setTimeout(() => setBusy("Analyzing your profile…"), 2500);
    try { onResult(await api("/assessment", p)); } catch (x) { setErr(x.message); } finally { clearTimeout(t); setBusy(""); }
  };
  const steps = [
    <><h2>Education</h2>
      <label>Institution<input value={p.education} onChange={(e) => set("education", e.target.value)} /></label>
      <label>Degree<input value={p.degree} onChange={(e) => set("degree", e.target.value)} /></label>
      <label>Current year / level<select value={p.year} onChange={(e) => set("year", e.target.value)}><option value="">Skip</option>{["1st year", "2nd year", "3rd year", "Final year", "Graduate", "Working"].map((y) => <option key={y}>{y}</option>)}</select></label></>,
    <><h2>Skills</h2><div className="chips" role="group" aria-label="Skills">
      {[...new Set([...vocab, ...p.skills.map((s) => s.name)])].map((n) => <button type="button" key={n} aria-pressed={!!lvl(n)} className={"chip" + (lvl(n) ? " on" : "")} onClick={() => toggleSkill(n)}>{n}</button>)}</div>
      <div className="row"><input placeholder="Add another skill" value={custom} onChange={(e) => setCustom(e.target.value)} /><button type="button" className="btn ghost" onClick={() => { if (custom.trim()) { toggleSkill(custom.trim()); setCustom(""); } }}>Add</button></div>
      {p.skills.map((s) => <label key={s.name}>{s.name}: <b>{LV[s.level]}</b><input type="range" min="1" max="3" value={s.level} onChange={(e) => setLvl(s.name, +e.target.value)} /></label>)}</>,
    <><h2>Interests</h2><div className="chips" role="group" aria-label="Interests">{INTERESTS.map((i) => <button type="button" key={i} aria-pressed={p.interests.includes(i)} className={"chip" + (p.interests.includes(i) ? " on" : "")} onClick={() => toggleInt(i)}>{i}</button>)}</div>
      <label>Experience (optional)<textarea value={p.experience} onChange={(e) => set("experience", e.target.value)} /></label></>,
    <><h2>Career goals</h2>
      <label>What do you want to achieve?<textarea value={p.goals} onChange={(e) => set("goals", e.target.value)} placeholder="e.g. I want to get into AI but I'm not sure where to start" /></label>
      <label>Preferred industry (optional)<input value={p.industry} onChange={(e) => set("industry", e.target.value)} /></label>
      <label>Preferred role (optional)<input value={p.roles[0] || ""} onChange={(e) => set("roles", e.target.value ? [e.target.value] : [])} /></label></>,
  ];
  if (busy) return <div className="glass narrow center" role="status"><div className="spinner" /><p>{busy}</p></div>;
  return (
    <div className="glass narrow">
      <p className="muted">Step {step + 1} of {steps.length}</p><progress value={step + 1} max={steps.length} />
      {steps[step]}{err && <p role="alert" className="err">{err}</p>}
      <div className="row">{step > 0 && <button className="btn ghost" onClick={() => setStep(step - 1)}>Back</button>}
        {step < steps.length - 1 ? <button className="btn" onClick={() => setStep(step + 1)}>Continue</button> : <button className="btn" onClick={run}>Get my career guidance</button>}</div>
    </div>
  );
}

function Results({ result, onRoadmap, onRetake, onCareerPlan }) {
  const [gap, setGap] = useState(null), [saved, setSaved] = useState([]), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const [query, setQuery] = useState(""), [jobZone, setJobZone] = useState(""), [browse, setBrowse] = useState(null), [browseBusy, setBrowseBusy] = useState(false), [browseErr, setBrowseErr] = useState(""), [offset, setOffset] = useState(0);
  useEffect(() => { api("/profile").then((d) => setSaved(d.saved_careers)); }, []);
  const searchCareers = async (e, nextOffset = 0) => {
    e?.preventDefault(); setBrowseBusy(true); setBrowseErr(""); setOffset(nextOffset);
    try {
      const params = new URLSearchParams({ q: query.trim(), limit: "12", offset: String(nextOffset) });
      if (jobZone) params.set("job_zone", jobZone);
      setBrowse(await api(`/career-search?${params.toString()}`));
    } catch (error) { setBrowseErr(error.message); }
    finally { setBrowseBusy(false); }
  };
  const chooseCareer = async (careerId) => {
    setBrowseBusy(true); setBrowseErr("");
    try { await api("/select-career", { career_id: careerId }); onCareerPlan?.(); }
    catch (error) { setBrowseErr(error.message); setBrowseBusy(false); }
  };
  const show = async (id) => { try { setGap(await api("/skill-gap", { career_id: id })); } catch (x) { setErr(x.message); } };
  const road = async (id) => { setBusy(true); setErr(""); try { onRoadmap(await api("/roadmap", { career_id: id })); } catch (x) { setErr(x.message); setBusy(false); } };
  if (!result) return <div className="glass narrow"><p>Complete your career assessment to receive personalized recommendations.</p></div>;
  if (busy) return <div className="glass narrow center" role="status"><div className="spinner" /><p>Building your personalized roadmap…</p></div>;
  return (
    <div className="stack">
      <div className="glass"><h2>Your career snapshot</h2>{result.ai_note && <p className="err" role="alert">{result.ai_note}</p>}
        <p>{result.summary}</p><p><b>Current strengths:</b> {result.strengths.join(", ") || "Add skills to see strengths"}</p>
        <EvidenceDetails items={result.retrieved_evidence} title="O*NET evidence retrieved for this assessment" />
        <button className="btn ghost" onClick={onRetake}>Update profile / re-run assessment</button></div>
      {err && <p role="alert" className="err">{err}</p>}
      <div className="cards">{result.career_options.map((c) => (
        <div className="glass" key={c.career_id}><h3>{c.name}</h3><p className="tag">{c.label}</p><p>{c.description}</p>
          {c.why_it_may_fit && <p><b>Why:</b> {c.why_it_may_fit}</p>}
          {c.onet_code && <p className="muted">O*NET-SOC {c.onet_code}{c.job_zone ? ` · Job Zone ${c.job_zone}` : ""} · <a href={c.onet_url} target="_blank" rel="noreferrer">Official occupation profile ↗</a></p>}
          <p><b>You have:</b> {c.have.join(", ") || "—"}</p><p><b>Missing:</b> {c.missing.join(", ") || "—"}</p>
          {c.tasks?.length > 0 && <details className="onet-details"><summary>What this occupation does</summary><ul>{c.tasks.map((task) => <li key={task}>{task}</li>)}</ul></details>}
          {c.technology_skills?.length > 0 && <p className="muted"><b>Hot / in-demand technologies:</b> {c.technology_skills.map((technology) => technology.name).join(", ")}</p>}
          <p className="muted">Skill coverage {Math.round(c.coverage * 100)}%</p>
          {c.breakdown && <details className="score-breakdown"><summary>How this model scored the match</summary><div className="score-components">
            {[["Skill coverage", c.breakdown.weights?.skill_coverage, c.breakdown.skill_coverage], ["Profile similarity (TF-IDF)", c.breakdown.weights?.profile_similarity, c.breakdown.profile_similarity], ["Interest fit", c.breakdown.weights?.interest_fit, c.breakdown.interest_fit], ["Preferred role fit", c.breakdown.weights?.role_fit, c.breakdown.role_fit]].filter(([, weight]) => weight > 0).map(([label, weight, value]) => <div className="score-component" key={label}><span>{label}<small>{Math.round(weight * 100)}% weight</small></span><progress value={value} max="1" aria-label={`${label}: ${Math.round(value * 100)}%`} /><b>{Math.round(value * 100)}%</b></div>)}
            <p className="muted">Combined score: {c.breakdown.score}. Model: {c.breakdown.model || "content-based career matching"}. Scores rank career relevance; they are not a probability of employment.</p>
          </div></details>}
          {c.next_steps.length > 0 && <ul>{c.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>}
          <div className="row"><button className="btn ghost" onClick={() => show(c.career_id)}>Skill gaps</button>
            <button className="btn" onClick={() => road(c.career_id)}>Build roadmap</button>
            <button className="btn ghost" onClick={async () => setSaved((await api("/profile/save-career", { career_id: c.career_id })).saved_careers)}>{saved.includes(c.career_id) ? "Saved ✓" : "Save"}</button></div></div>))}</div>
      {gap && <div className="glass"><h2>Skill-gap analysis</h2><p className="muted">{gap.method}</p>
        <table><thead><tr><th>Skill</th><th>Current</th><th>Required</th><th>Gap</th><th>Next action</th></tr></thead><tbody>
          {gap.rows.map((r) => <tr key={r.skill}><td>{r.skill}</td><td><Bar value={r.current} label={r.current_label} />{r.current_label}</td><td>{r.required_label}</td><td>{r.gap_label}</td><td>{r.action}</td></tr>)}</tbody></table></div>}
      <section className="career-browser">
        <PageHead eyebrow="Explore O*NET" title="Search more career paths." />
        <form className="career-search" onSubmit={searchCareers}>
          <label>Occupation, skill, task, or technology<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. software developer, statistics, healthcare" /></label>
          <label>Preparation level<select value={jobZone} onChange={(event) => setJobZone(event.target.value)}><option value="">Any Job Zone</option>{[1,2,3,4,5].map((zone) => <option key={zone} value={zone}>Job Zone {zone}</option>)}</select></label>
          <button className="btn" type="submit" disabled={browseBusy}>Search occupations</button>
        </form>
        {browseErr && <p className="err" role="alert">{browseErr}</p>}
        {browseBusy && <p className="muted" role="status">Searching O*NET occupations…</p>}
        {browse && <><p className="small muted">{browse.total.toLocaleString()} occupations found</p><div className="browse-results">{browse.items.map((career) => <article className="browse-card" key={career.id}>
          <div className="browse-title"><div><h3>{career.name}</h3><p className="small muted">{career.onet_code}{career.job_zone ? ` · Job Zone ${career.job_zone}` : ""}</p></div>{career.onet_url && <a href={career.onet_url} target="_blank" rel="noreferrer">O*NET ↗</a>}</div>
          <p>{career.description}</p>
          {Object.keys(career.skills || {}).length > 0 && <p className="small"><b>Key skills:</b> {Object.keys(career.skills).slice(0, 6).join(" · ")}</p>}
          {career.technology_skills?.length > 0 && <p className="small muted"><b>Technologies:</b> {career.technology_skills.map((item) => item.name).join(" · ")}</p>}
          <button className="btn ghost sm" disabled={browseBusy} onClick={() => chooseCareer(career.id)}>Make this my career plan</button>
        </article>)}</div>
          <div className="browse-pagination"><button className="btn ghost sm" disabled={browseBusy || offset === 0} onClick={(event) => searchCareers(event, Math.max(0, offset - browse.limit))}>Previous</button><span className="small muted">{offset + 1}–{Math.min(offset + browse.items.length, browse.total)} of {browse.total}</span><button className="btn ghost sm" disabled={browseBusy || offset + browse.limit >= browse.total} onClick={(event) => searchCareers(event, offset + browse.limit)}>Next</button></div>
        </>}
      </section>
    </div>
  );
}

function Roadmap({ data, setData }) {
  if (!data) return <div className="glass narrow"><p>Choose a career on the results page and select “Build roadmap”.</p></div>;
  const all = data.phases.flatMap((p) => p.items), done = all.filter((i) => i.done).length;
  const toggle = async (id, v) => {
    setData({ ...data, phases: data.phases.map((p) => ({ ...p, items: p.items.map((i) => (i.id === id ? { ...i, done: v } : i)) })) });
    try { await api("/progress", { roadmap_id: data.roadmap_id, item_id: id, done: v }); } catch { /* revert on failure */ setData(data); }
  };
  return (
    <div className="stack"><div className="glass"><h2>Your roadmap</h2>{data.ai_note && <p className="muted" role="status">{data.ai_note}</p>}<progress value={done} max={all.length || 1} /> <span>{done}/{all.length} complete</span></div>
      {data.retrieved_evidence?.length > 0 && <div className="glass"><EvidenceDetails items={data.retrieved_evidence} title="O*NET evidence used for this roadmap" /></div>}
      {data.phases.map((ph, n) => <div className="glass" key={n}><h3>{String(n + 1).padStart(2, "0")} — {ph.title}</h3>
        {ph.items.map((it) => <label className="item" key={it.id}><input type="checkbox" checked={it.done} onChange={(e) => toggle(it.id, e.target.checked)} />
          <span><b>{it.title}</b> <span className="tag">{it.difficulty} · {it.estimated_time}</span><br />{it.description}<br /><span className="muted">Skills: {it.skills.join(", ")} {it.resources.length ? "· Resources: " + it.resources.join(", ") : ""}</span></span></label>)}</div>)}</div>
  );
}

function PageHead({ eyebrow, title, children }) {
  return <header className="page-head"><p className="eyebrow">{eyebrow}</p><h2>{title}</h2>{children}</header>;
}

function EvidenceDetails({ items, title = "Retrieved evidence" }) {
  if (!items?.length) return null;
  return <details className="evidence-details"><summary>{title} · {items.length} passages</summary>
    <div className="evidence-list">{items.map((item, index) => <article key={`${item.career_id}-${item.chunk_type}-${index}`}>
      <div className="evidence-heading"><b>{item.career_name || item.career_id}</b><span>{item.chunk_type || "occupation"}</span></div>
      <p>{item.text}</p>
      <div className="evidence-meta"><span>Matched by {(item.retrieved_by || []).join(" + ") || "retrieval"}</span>{item.onet_code && <span>O*NET-SOC {item.onet_code}</span>}{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Source ↗</a>}</div>
    </article>)}</div>
  </details>;
}

function Overview({ email, result, road, saved, go }) {
  if (!result) return <div className="overview-empty"><PageHead eyebrow="Your starting point" title="A clearer direction starts here." />
    <p className="muted">Tell us a little about your skills, interests and goals. We’ll help map out what could come next.</p>
    <button className="btn" onClick={() => go("assess")}>Start your assessment <span aria-hidden="true">→</span></button></div>;
  const options = result.career_options || [], top = options[0], tasks = road?.phases?.flatMap((phase) => phase.items) || [], done = tasks.filter((item) => item.done).length;
  return <div className="overview-page"><PageHead eyebrow="Your career overview" title={`A good direction to start, ${email.split("@")[0] || "there"}.`}>
      <p className="muted">{result.summary || "Your career snapshot is ready. Explore the matches and choose a next step."}</p>
    </PageHead>
    <div className="overview-grid">
      <section className="overview-feature"><p className="eyebrow">Strongest match</p><h3>{top?.name || "Complete your assessment"}</h3>
        <p>{top?.description || "Your personalized career directions will appear here."}</p>
        {top?.why_it_may_fit && <p className="match-explanation"><b>Why this may fit:</b> {top.why_it_may_fit}</p>}
        {top?.next_steps?.length > 0 && <ul className="match-next-steps">{top.next_steps.slice(0, 3).map((step, index) => <li key={index}>{step}</li>)}</ul>}
        {top && <><div className="coverage"><span>Skill coverage</span><b>{Math.round(top.coverage * 100)}%</b></div><progress value={top.coverage * 100} max="100" aria-label="Skill coverage" />
          <button className="textbtn" onClick={() => go("discover")}>Explore career matches <span aria-hidden="true">→</span></button></>}
      </section>
      <section className="overview-card"><p className="eyebrow">Your strengths</p><div className="tags">{(result.strengths || []).length ? result.strengths.map((skill) => <span className="tag sage" key={skill}>{skill}</span>) : <span className="muted">Add skills to see strengths.</span>}</div>
        {result.ai_note && <p className="err" role="alert">{result.ai_note}</p>}</section>
      <section className="overview-card"><p className="eyebrow">Roadmap progress</p>{road ? <><progress value={done} max={tasks.length || 1} /><p className="small muted">{done} of {tasks.length} steps complete</p><button className="textbtn" onClick={() => go("roadmap")}>Continue roadmap →</button></> : <><p className="muted">No roadmap yet.</p><button className="textbtn" onClick={() => go("discover")}>Choose a career to begin →</button></>}</section>
      <section className="overview-card"><p className="eyebrow">Saved careers</p>{saved.length ? <div className="tags">{saved.map((id) => <span className="tag" key={id}>{options.find((career) => career.career_id === id)?.name || id}</span>)}</div> : <p className="muted">Save interesting paths to revisit them here.</p>}</section>
    </div>
    <div className="overview-actions"><p className="eyebrow">Your next steps</p><button className="btn" onClick={() => go("discover")}>Explore career matches</button><button className="btn ghost" onClick={() => go("assess")}>Update assessment</button></div>
  </div>;
}

function Skills({ result, initialId }) {
  const [id, setId] = useState(initialId || result?.career_options?.[0]?.career_id || ""), [gap, setGap] = useState(null), [err, setErr] = useState("");
  useEffect(() => { if (id) { setGap(null); setErr(""); api("/skill-gap", { career_id: id }).then(setGap).catch((error) => setErr(error.message)); } }, [id]);
  if (!result) return <div className="overview-empty"><PageHead eyebrow="Skill matrix" title="Assessment needed first." /><p className="muted">Complete your assessment to compare your skills with a career target.</p></div>;
  const focus = gap?.rows.filter((row) => row.gap).sort((a, b) => b.gap - a.gap).slice(0, 3) || [];
  return <div><PageHead eyebrow="Skill matrix" title="Where you stand, and where the role sits." />
    <label className="target-select">Target career<select value={id} onChange={(event) => setId(event.target.value)}>{result.career_options.map((career) => <option key={career.career_id} value={career.career_id}>{career.name}</option>)}</select></label>
    {err && <p className="err" role="alert">{err}</p>}{!gap && !err && <div className="load" role="status">Comparing your skills…</div>}
    {gap && <><div className="table-wrap"><table className="matrix"><thead><tr><th>Skill</th><th>Your level</th><th>Target level</th><th>Gap</th><th>Next action</th></tr></thead><tbody>{gap.rows.map((row) => <tr key={row.skill}><td>{row.skill}</td><td><div className="meter" aria-label={`You: ${row.current_label}`}>{[1,2,3].map((level) => <i key={level} className={level <= row.current ? "f" : ""} />)}</div><span className="small muted">{row.current_label}</span></td><td><div className="meter target" aria-label={`Target: ${row.required_label}`}>{[1,2,3].map((level) => <i key={level} className={level <= row.required ? "f" : ""} />)}</div><span className="small muted">{row.required_label}</span></td><td>{row.gap_label}</td><td>{row.action}</td></tr>)}</tbody></table></div>
      <p className="small muted matrix-note">{gap.method}</p>{focus.length > 0 && <section className="focus-list"><p className="eyebrow">What to focus on next</p>{focus.map((row, index) => <article key={row.skill}><b>0{index + 1}</b><p><strong>{row.skill}</strong><br /><span className="muted">{row.current_label} → {row.required_label}. {row.action}</span></p></article>)}</section>}</>}
  </div>;
}

function Resources() {
  const [filters, setFilters] = useState({ skill: "", type: "", difficulty: "" }), [all, setAll] = useState([]), [rows, setRows] = useState([]), [err, setErr] = useState("");
  useEffect(() => { api("/resources").then(setAll).catch((error) => setErr(error.message)); }, []);
  useEffect(() => { const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value)).toString(); api("/resources" + (query ? `?${query}` : "")).then(setRows).catch((error) => setErr(error.message)); }, [filters]);
  const options = (key) => [...new Set(all.map((item) => item[key]))].sort();
  return <div><PageHead eyebrow="Resource library" title="Curated, not scattered." /><div className="filters">{[["skill","Skill"],["type","Type"],["difficulty","Difficulty"]].map(([key,label]) => <label key={key}>{label}<select value={filters[key]} onChange={(event) => setFilters({ ...filters, [key]: event.target.value })}><option value="">All</option>{options(key).map((option) => <option key={option}>{option}</option>)}</select></label>)}</div>
    {err && <p className="err" role="alert">{err}</p>}<div className="resource-list">{rows.map((item, index) => <a className="resource-row" key={item.url} href={item.url} target="_blank" rel="noreferrer"><span className="resource-number">{String(index + 1).padStart(2, "0")}</span><span><strong>{item.title}</strong><small>{item.type} · {item.difficulty} · {item.duration} · {item.skill}</small></span><span aria-hidden="true">↗</span></a>)}{!rows.length && !err && <p className="muted">No resources match these filters.</p>}</div></div>;
}

function Profile({ email, profile, go }) {
  const sections = [["About you", [profile.degree, profile.education, profile.year].filter(Boolean).join(" · ")], ["Skills", (profile.skills || []).map((skill) => `${skill.name} · ${LV[skill.level]}`).join(" · ")], ["Interests", (profile.interests || []).join(" · ")], ["Experience", profile.experience], ["Career goals", profile.goals]];
  return <div><PageHead eyebrow="Your career profile" title={email}><button className="textbtn" onClick={() => go("assess")}>Edit profile →</button></PageHead>{sections.map(([title, value]) => <section className="profile-section" key={title}><p className="eyebrow">{title}</p><p>{value || <span className="muted">Not provided yet</span>}</p></section>)}</div>;
}

function CareerWorkspace({ onSelected }) {
  const [data, setData] = useState(null), [busy, setBusy] = useState(true), [err, setErr] = useState("");
  const refresh = async () => { setErr(""); try { setData(await api("/workspace")); } catch (error) { setErr(error.message); } finally { setBusy(false); } };
  useEffect(() => { refresh(); }, []);
  const select = async (careerId) => {
    setBusy(true); setErr("");
    try { const next = await api("/select-career", { career_id: careerId }); setData(next); onSelected?.(next); }
    catch (error) { setErr(error.message); }
    finally { setBusy(false); }
  };
  if (busy && !data) return <div className="load" role="status">Loading your connected career workspace…</div>;
  if (err && !data) return <div className="overview-empty"><PageHead eyebrow="Career workspace" title="We couldn’t load your plan." /><p className="err" role="alert">{err}</p><button className="btn" onClick={refresh}>Try again</button></div>;
  const career = data?.selected_career, gap = data?.skill_gap, progress = data?.progress;
  return <div className="overview-page"><PageHead eyebrow="Connected career workspace" title={career ? `Your plan for ${career.name}.` : "Choose a direction to build your plan."}>
      <p className="muted">Your selected career, O*NET skill gaps, learning resources, roadmap progress, and next actions in one place.</p>
    </PageHead>
    {err && <p className="err" role="alert">{err}</p>}
    {!data?.assessment && <div className="overview-card"><p>Complete your career assessment first to get personalized workspace recommendations.</p></div>}
    {career && <>
      <section className="overview-feature workspace-feature"><p className="eyebrow">Selected career{career.onet_code ? ` · O*NET ${career.onet_code}` : ""}</p><h3>{career.name}</h3><p>{career.description}</p>
        {career.onet_url && <a className="textbtn" href={career.onet_url} target="_blank" rel="noreferrer">Official O*NET profile ↗</a>}
        {gap && <><div className="coverage"><span>Skill coverage</span><b>{Math.round(gap.coverage * 100)}%</b></div><progress value={gap.coverage * 100} max="100" aria-label="Skill coverage" /><p className="small muted">{gap.rows.filter((row) => row.gap).length} skill gaps identified</p></>}
      </section>
      <div className="overview-grid workspace-grid">
        <section className="overview-card"><p className="eyebrow">Focus on next</p>{gap?.rows.filter((row) => row.gap).sort((a,b) => b.gap-a.gap).slice(0,4).map((row) => <p className="workspace-gap" key={row.skill}><b>{row.skill}</b><span className="muted">{row.current_label} → {row.required_label}</span><small>{row.action}</small></p>)}{gap && !gap.rows.some((row) => row.gap) && <p className="muted">You meet all listed O*NET skill levels for this occupation.</p>}</section>
        <section className="overview-card"><p className="eyebrow">Roadmap progress</p>{progress ? <><progress value={progress.done} max={progress.total || 1} /><p className="small muted">{progress.done}/{progress.total} actions complete · {progress.percent}%</p><div className="workspace-phase-list">{progress.phases.map((phase) => <p key={phase.title}>{phase.title}<span>{phase.done}/{phase.total}</span></p>)}</div></> : <p className="muted">No roadmap yet. Build one from a career match to create a weekly action plan.</p>}</section>
      </div>
      <section className="workspace-section"><p className="eyebrow">Your weekly action plan</p>{data.weekly_plan?.length ? <div className="workspace-weekly">{data.weekly_plan.map((item) => <article key={`${item.item_id}-${item.part}`}><b>Week {item.week}</b><span>{item.task}{item.part !== "1/1" ? ` · Part ${item.part}` : ""}</span><small>{item.phase}{item.skills?.length ? ` · ${item.skills.join(", ")}` : ""}</small></article>)}</div> : <p className="muted">Generate a roadmap to get a week-by-week plan.</p>}</section>
      {data.resources?.length > 0 && <section className="workspace-section"><p className="eyebrow">Resources matched to your gaps</p><div className="workspace-resources">{data.resources.map((resource) => <a key={`${resource.url}-${resource.for_skill}`} href={resource.url} target="_blank" rel="noreferrer"><b>{resource.title}</b><span>{resource.for_skill} · {resource.type} · {resource.difficulty}</span><small>{resource.reason}</small></a>)}</div></section>}
      {data.switch_options?.length > 0 && <section className="workspace-section"><p className="eyebrow">If your direction changes</p><p className="muted small">Compare alternative careers by skill coverage and estimated gap effort. Shared skills are transferable.</p><div className="workspace-switches">{data.switch_options.slice(0,4).map((option) => <article key={option.career_id}><div><b>{option.name}</b><p className="small muted">{Math.round(option.coverage*100)}% coverage · gap effort {option.effort}{option.effort_vs_current < 0 ? ` · ${Math.abs(option.effort_vs_current)} less than current` : option.effort_vs_current > 0 ? ` · ${option.effort_vs_current} more than current` : " · same effort"}</p><div className="tags">{option.shared_with_current.slice(0,4).map((skill) => <span className="tag sage" key={skill}>{skill}</span>)}{option.new_skills.slice(0,3).map((skill) => <span className="tag warn" key={skill}>{skill}</span>)}</div></div><button className="btn ghost sm" disabled={busy} onClick={() => select(option.career_id)}>Choose</button></article>)}</div></section>}
    </>}
  </div>;
}

function Chat() {
  const [msgs, setMsgs] = useState([]), [cid, setCid] = useState(null), [list, setList] = useState([]), [text, setText] = useState(""), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const end = useRef();
  const refresh = () => api("/conversations").then(setList).catch(() => {});
  useEffect(() => { refresh(); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);
  const send = async (m) => {
    m = (m ?? text).trim(); if (!m || busy) return;
    setText(""); setErr(""); setMsgs((o) => [...o, { role: "user", content: m }]); setBusy(true);
    try { const r = await api("/chat", { message: m, conversation_id: cid }); setCid(r.conversation_id); setMsgs((o) => [...o, { role: "assistant", content: r.reply, retrieved_evidence: r.retrieved_evidence }]); refresh(); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  const open = async (id) => { setCid(id); setMsgs(await api(`/conversations/${id}`)); };
  return (
    <div className="chat"><aside className="glass"><button className="btn" onClick={() => { setCid(null); setMsgs([]); }}>+ New conversation</button>
      {list.map((c) => <button key={c.id} className={"link" + (c.id === cid ? " active" : "")} onClick={() => open(c.id)}>{c.title}</button>)}</aside>
      <section className="glass"><div className="msgs" aria-live="polite">
        {!msgs.length && <div><p>Ask anything about your career path.</p><div className="chips">{["Which career paths fit me?", "Analyze my skill gaps.", "Create my AI career roadmap.", "What project should I build next?"].map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}</div></div>}
        {msgs.map((m, i) => <div key={i} className={"bubble " + m.role}>{m.role === "assistant" && <span className="avatar">AI</span>}<div><div className="pre">{m.content}</div>{m.role === "assistant" && <EvidenceDetails items={m.retrieved_evidence} title="Sources used" />}</div></div>)}
        {busy && <div className="bubble assistant"><span className="avatar">AI</span><div className="spinner sm" role="status" aria-label="Thinking" /></div>}
        {err && <p role="alert" className="err">{err}</p>}<div ref={end} /></div>
        <div className="row"><input aria-label="Message" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Ask CareerLens…" /><button className="btn" onClick={() => send()} disabled={busy}>Send</button></div></section></div>
  );
}

export default function App() {
  const [view, setView] = useState("landing"), [authed, setAuthed] = useState(!!auth.get());
  const [email, setEmail] = useState(""), [profile, setProfile] = useState({}), [result, setResult] = useState(null), [road, setRoad] = useState(null), [saved, setSaved] = useState([]), [skillId, setSkillId] = useState(null);
  const load = async () => {
    try { const [pr, a, r] = await Promise.all([api("/profile"), api("/assessment/latest"), api("/roadmap/latest")]); setEmail(pr.email); setProfile(pr.profile); setSaved(pr.saved_careers || []); setResult(a); setRoad(r); setView(a ? "overview" : "assess"); }
    catch { setAuthed(false); }
  };
  useEffect(() => { if (authed) load(); }, [authed]);
  const gate = (v) => (authed ? setView(v) : setView("auth"));
  const logout = () => { auth.clear(); setAuthed(false); setResult(null); setRoad(null); setView("landing"); };
  const navItems = [["overview","Overview","⌂"],["assess","Assessment","✎"],["discover","Career matches","⌕"],["workspace","Career plan","▧"],["roadmap","Roadmap","↗"]];
  if (!authed) return <><header className="public-header"><button className="wordmark" onClick={() => setView("landing")}>Career<span>Lens</span></button><button className="btn ghost small-btn" onClick={() => setView("auth")}>Log in</button></header>{view === "auth" ? <Auth onDone={() => setAuthed(true)} /> : <Landing onStart={() => gate("assess")} />}</>;
  return <div className="shell">
    <aside className="sidebar" aria-label="Main navigation"><button className="wordmark" onClick={() => setView("overview")}>Career<span>Lens</span></button>
      <p className="eyebrow sidebar-label">Your career path</p>{navItems.map(([key,label,icon]) => <button key={key} className={`side-link${view === key ? " selected" : ""}`} aria-current={view === key ? "page" : undefined} onClick={() => setView(key)}><span aria-hidden="true">{icon}</span>{label}</button>)}
      <div className="sidebar-spacer" /><button className={`side-link${view === "profile" ? " selected" : ""}`} onClick={() => setView("profile")}><span aria-hidden="true">◎</span>Profile</button><button className="side-link" onClick={logout}><span aria-hidden="true">↪</span>Log out</button>
    </aside>
    <main className="main-content" key={view}>
      {view === "landing" && <Landing onStart={() => gate("assess")} />}
      {view === "auth" && <Auth onDone={() => setAuthed(true)} />}
      {view === "overview" && <Overview email={email} result={result} road={road} saved={saved} go={setView} />}
      {view === "workspace" && <CareerWorkspace />}
      {view === "assess" && <Assessment initial={profile} onResult={(r) => { setResult(r); api("/profile").then((p) => setProfile(p.profile)); setView("overview"); }} />}
      {view === "discover" && <Results result={result} onRoadmap={(r) => { setRoad(r); setView("roadmap"); }} onRetake={() => setView("assess")} onCareerPlan={() => setView("workspace")} />}
      {view === "skills" && <Skills result={result} initialId={skillId} />}
      {view === "roadmap" && <Roadmap data={road} setData={setRoad} />}
      {view === "resources" && <Resources />}
      {view === "chat" && <Chat />}
      {view === "profile" && <Profile email={email} profile={profile} go={setView} />}
      {view === "discover" && result && <button className="textbtn discover-skills-link" onClick={() => { setSkillId(result.career_options[0]?.career_id); setView("skills"); }}>Open skill matrix →</button>}
      <DataAttribution />
    </main>
    <nav className="mobile-nav" aria-label="Main navigation">{navItems.map(([key,label,icon]) => <button key={key} className={view === key ? "selected" : ""} onClick={() => setView(key)}><span aria-hidden="true">{icon}</span>{label.replace("AI ", "")}</button>)}</nav>
  </div>;
}
