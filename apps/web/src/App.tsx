import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { EventItem, ProjectDetail, ProjectSummary, Question } from "./types";

const terminalStatuses = new Set(["PREVIEW_READY", "FAILED", "PRODUCTION"]);

export default function App() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [creating, setCreating] = useState(true);
  const [detail, setDetail] = useState<ProjectDetail>();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refreshProjects = useCallback(async () => {
    const items = await api.projects();
    setProjects(items);
    if (!creating && !selectedId && items[0]) setSelectedId(items[0].id);
  }, [creating, selectedId]);

  const refreshDetail = useCallback(async () => {
    if (!selectedId) return;
    const [nextDetail, nextQuestions, nextEvents] = await Promise.all([
      api.project(selectedId),
      api.questions(selectedId),
      api.events(selectedId),
    ]);
    setDetail(nextDetail);
    setQuestions(nextQuestions);
    setEvents(nextEvents);
  }, [selectedId]);

  useEffect(() => {
    refreshProjects().catch((cause: unknown) => setError(String(cause)));
  }, [refreshProjects]);

  useEffect(() => {
    refreshDetail().catch((cause: unknown) => setError(String(cause)));
  }, [refreshDetail]);

  useEffect(() => {
    if (!selectedId || !detail || terminalStatuses.has(detail.project.status)) return;
    const timer = window.setInterval(() => {
      refreshDetail().catch(() => undefined);
      refreshProjects().catch(() => undefined);
    }, 1800);
    return () => window.clearInterval(timer);
  }, [detail, refreshDetail, refreshProjects, selectedId]);

  async function withBusy(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      await Promise.all([refreshProjects(), refreshDetail()]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <Sidebar projects={projects} selectedId={selectedId} onSelect={(id) => {
        setCreating(!id);
        setSelectedId(id);
        if (!id) setDetail(undefined);
      }} />
      <main>
        <header className="topbar">
          <div>
            <span className="overline">Control plane</span>
            <h1>{detail?.project.name ?? "Novo projeto"}</h1>
          </div>
          {detail && <Status value={detail.project.status} />}
        </header>

        {error && <div className="error">{error}</div>}

        {!detail ? (
          <CreateProject busy={busy} onCreate={(name, message) => withBusy(async () => {
            const result = await api.create(name, message);
            setCreating(false);
            setSelectedId(result.project.id);
          })} />
        ) : (
          <div className="workspace">
            <section className="conversation panel">
              <div className="panel-title"><span>01</span><div><h2>Discovery</h2><p>Conversa vira especificação estruturada.</p></div></div>
              <MessageComposer busy={busy} onSend={(content) => withBusy(() => api.message(detail.project.id, content))} />
              <Questions questions={questions} busy={busy} onAnswer={(id, answer) => withBusy(() => api.answer(detail.project.id, id, answer))} />
              <button className="primary wide" disabled={busy} onClick={() => withBusy(() => api.pipeline(detail.project.id))}>
                {busy ? "Processando…" : "Executar pipeline completo"}
              </button>
            </section>

            <section className="spec panel">
              <div className="panel-title"><span>02</span><div><h2>ProjectSpec</h2><p>v{detail.project.current_spec_version} · checksum auditável</p></div></div>
              <SpecView spec={detail.spec} />
            </section>

            <section className="timeline panel">
              <div className="panel-title"><span>03</span><div><h2>Timeline real</h2><p>Eventos persistidos pelo backend.</p></div></div>
              <Timeline events={events} />
            </section>

            <section className="build panel">
              <div className="panel-title"><span>04</span><div><h2>Execução</h2><p>ArchitectureSpec, DAG, gates e preview.</p></div></div>
              <ExecutionSummary detail={detail} busy={busy} onPause={() => detail.preview && withBusy(() => api.pause(detail.preview!.id))} onResume={() => detail.preview && withBusy(() => api.resume(detail.preview!.id))} />
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function Sidebar({ projects, selectedId, onSelect }: { projects: ProjectSummary[]; selectedId?: string; onSelect: (id?: string) => void }) {
  return <aside>
    <div className="brand"><div className="brand-mark">N</div><div><strong>NEXORA</strong><small>Agentic Builder</small></div></div>
    <button className="new-project" onClick={() => onSelect(undefined)}>＋ Novo projeto</button>
    <div className="nav-label">Projetos recentes</div>
    <nav>{projects.map((project) => <button key={project.id} className={selectedId === project.id ? "active" : ""} onClick={() => onSelect(project.id)}><i /><span>{project.name}<small>{project.status.replaceAll("_", " ")}</small></span></button>)}</nav>
    <footer><span className="live-dot" /> Orquestrador ativo</footer>
  </aside>;
}

function Status({ value }: { value: string }) { return <div className={`status status-${value.toLowerCase()}`}><i />{value.replaceAll("_", " ")}</div>; }

function CreateProject({ busy, onCreate }: { busy: boolean; onCreate: (name: string, message: string) => Promise<void> }) {
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); await onCreate(name, message); }
  return <form className="create-card" onSubmit={submit}>
    <span className="overline">Comece pela intenção</span><h2>O que vamos construir?</h2><p>Descreva o produto em linguagem natural. A plataforma estrutura o que sabe e pergunta apenas pelas lacunas relevantes.</p>
    <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome do projeto" minLength={2} required />
    <textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ex.: Quero uma plataforma para restaurantes criarem cardápios em vídeo..." minLength={10} required />
    <button className="primary" disabled={busy}>{busy ? "Criando…" : "Criar projeto e compilar spec"}</button>
  </form>;
}

function MessageComposer({ busy, onSend }: { busy: boolean; onSend: (content: string) => Promise<void> }) {
  const [content, setContent] = useState("");
  async function submit(event: FormEvent) { event.preventDefault(); if (!content.trim()) return; await onSend(content); setContent(""); }
  return <form className="composer" onSubmit={submit}><textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="Adicione contexto, regras ou uma mudança…" /><button disabled={busy}>Enviar</button></form>;
}

function Questions({ questions, busy, onAnswer }: { questions: Question[]; busy: boolean; onAnswer: (id: string, answer: string) => Promise<void> }) {
  const open = questions.filter((question) => question.status === "OPEN").slice(0, 5);
  if (!open.length) return <div className="ready-callout"><span>✓</span><p><strong>Sem bloqueios de discovery</strong>O pipeline já pode avançar.</p></div>;
  return <div className="question-list">{open.map((question) => <div className="question" key={question.id}><div><em>{question.severity}</em><strong>{question.question}</strong><small>{question.reason}</small></div><div className="option-row">{question.options.map((option) => <button disabled={busy} key={option} onClick={() => onAnswer(question.id, option)}>{option}{option === question.recommended && <b>recomendado</b>}</button>)}</div></div>)}</div>;
}

function SpecView({ spec }: { spec: Record<string, unknown> | null }) {
  if (!spec) return <p className="muted">Aguardando discovery.</p>;
  const project = spec.project as Record<string, unknown> | undefined;
  const modules = (spec.modules as { name?: string }[] | undefined) ?? [];
  const requirements = (spec.functional_requirements as { description?: string }[] | undefined) ?? [];
  return <div className="spec-content"><h3>{String(project?.summary ?? "Resumo em construção")}</h3><div className="tags">{modules.map((module, index) => <span key={index}>{module.name}</span>)}</div><div className="metric-row"><div><strong>{requirements.length}</strong><small>requisitos extraídos</small></div><div><strong>{modules.length}</strong><small>módulos detectados</small></div></div><details><summary>Ver JSON estruturado</summary><pre>{JSON.stringify(spec, null, 2)}</pre></details></div>;
}

function Timeline({ events }: { events: EventItem[] }) {
  if (!events.length) return <p className="muted">Os eventos aparecerão conforme o backend avançar.</p>;
  return <ol>{events.slice().reverse().slice(0, 12).map((event) => <li key={event.id}><i /><div><strong>{event.message}</strong><small>{event.type} · #{event.sequence}</small></div></li>)}</ol>;
}

function ExecutionSummary({ detail, busy, onPause, onResume }: { detail: ProjectDetail; busy: boolean; onPause: () => void; onResume: () => void }) {
  return <div className="execution-summary">
    {detail.task_graph ? <div className="tasks">{detail.task_graph.tasks.map((task) => <div key={task.id}><span>{task.key}</span><Status value={task.status} /></div>)}</div> : <p className="muted">TaskGraph ainda não gerada.</p>}
    {detail.preview && <div className="preview-card"><div><small>Preview efêmero</small><strong>{detail.preview.state}</strong></div><div className="preview-actions"><a href={detail.preview.url} target="_blank">Abrir ↗</a>{detail.preview.state === "PAUSED" ? <button disabled={busy} onClick={onResume}>Retomar</button> : <button disabled={busy} onClick={onPause}>Pausar</button>}</div></div>}
    {detail.production_plan && <div className="credits"><span>Estimativa mensal</span><strong>{detail.production_plan.monthly_credits} créditos</strong><small>Produção usa banco novo; preview nunca é promovido.</small></div>}
  </div>;
}
