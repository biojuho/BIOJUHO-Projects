"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface Task {
  id: number;
  title: string;
  description?: string | null;
  regulatory_basis: string;
  status: string;
  assignee_agent?: string | null;
}

export default function TaskPanel() {
  const [workstreamId, setWorkstreamId] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [regulatoryBasis, setRegulatoryBasis] = useState("");
  const [assignee, setAssignee] = useState("Regulatory");

  const loadTasks = async () => {
    if (!workstreamId) return;
    const response = await fetch(
      `${API_BASE}/workstreams/${workstreamId}/tasks`
    );
    const data = await response.json();
    setTasks(data);
  };

  const handleCreateTask = async () => {
    if (!workstreamId) return;
    await fetch(`${API_BASE}/workstreams/${workstreamId}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        description,
        regulatory_basis: regulatoryBasis,
        status: "todo",
        assignee_agent: assignee
      })
    });
    setTitle("");
    setDescription("");
    setRegulatoryBasis("");
    loadTasks();
  };

  return (
    <section>
      <h2>태스크 관리</h2>
      <label>워크스트림 ID</label>
      <input
        value={workstreamId}
        onChange={(e) => setWorkstreamId(e.target.value)}
      />
      <button className="secondary" onClick={loadTasks}>
        태스크 조회
      </button>
      <div className="grid">
        <div>
          <label>태스크 제목</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
          <label>설명</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <label>규제 근거</label>
          <textarea
            value={regulatoryBasis}
            onChange={(e) => setRegulatoryBasis(e.target.value)}
          />
          <label>담당 에이전트</label>
          <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="Regulatory">Regulatory</option>
            <option value="Bioprocess/CMC">Bioprocess/CMC</option>
            <option value="Preclinical/Pharm">Preclinical/Pharm</option>
            <option value="Clinical Dev">Clinical Dev</option>
            <option value="Discovery">Discovery</option>
            <option value="CSO">CSO</option>
          </select>
          <button onClick={handleCreateTask}>태스크 생성</button>
        </div>
        <div>
          {tasks.map((task) => (
            <div key={task.id} className="card">
              <strong>{task.title}</strong>
              <p className="small">{task.regulatory_basis}</p>
              <p className="small">담당: {task.assignee_agent || "미지정"}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
