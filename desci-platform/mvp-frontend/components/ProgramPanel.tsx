"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface Program {
  id: number;
  name: string;
  description?: string | null;
  regulatory_context?: string | null;
  status: string;
}

interface Workstream {
  id: number;
  program_id: number;
  name: string;
  type: string;
  status: string;
}

export default function ProgramPanel() {
  const [programs, setPrograms] = useState<Program[]>([]);
  const [workstreams, setWorkstreams] = useState<Record<number, Workstream[]>>({});
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [regulatoryContext, setRegulatoryContext] = useState("");

  const loadPrograms = async () => {
    const response = await fetch(`${API_BASE}/programs`);
    const data = await response.json();
    setPrograms(data);
  };

  const loadWorkstreams = async (programId: number) => {
    const response = await fetch(`${API_BASE}/programs/${programId}/workstreams`);
    const data = await response.json();
    setWorkstreams((prev) => ({ ...prev, [programId]: data }));
  };

  useEffect(() => {
    loadPrograms();
  }, []);

  const handleCreateProgram = async () => {
    await fetch(`${API_BASE}/programs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        description,
        regulatory_context: regulatoryContext,
        status: "active"
      })
    });
    setName("");
    setDescription("");
    setRegulatoryContext("");
    loadPrograms();
  };

  return (
    <section>
      <h2>프로그램 관리</h2>
      <div className="grid">
        <div>
          <label>프로그램 이름</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <label>설명</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <label>규제 컨텍스트</label>
          <textarea
            value={regulatoryContext}
            onChange={(e) => setRegulatoryContext(e.target.value)}
          />
          <button onClick={handleCreateProgram}>프로그램 생성</button>
        </div>
        <div>
          {programs.map((program) => (
            <div key={program.id} className="card">
              <strong>{program.name}</strong>
              <p className="small">{program.description || "설명 없음"}</p>
              <button
                className="secondary"
                onClick={() => loadWorkstreams(program.id)}
              >
                워크스트림 보기
              </button>
              <ul className="small">
                {(workstreams[program.id] || []).map((ws) => (
                  <li key={ws.id}>
                    {ws.type}: {ws.name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
