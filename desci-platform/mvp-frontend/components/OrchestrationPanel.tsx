"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface AgentResponse {
  agent: string;
  summary: string;
  assumptions: string[];
  evidence_refs: string[];
  risks: string[];
  open_questions: string[];
  next_actions: string[];
}

interface DecisionRecord {
  context: string;
  decision: string;
  rationale: string;
  alternatives_considered: string;
  consequences: string;
  owner: string;
  date: string;
}

export default function OrchestrationPanel() {
  const [requestText, setRequestText] = useState("");
  const [summary, setSummary] = useState("");
  const [agentResponses, setAgentResponses] = useState<AgentResponse[]>([]);
  const [decisionRecord, setDecisionRecord] = useState<DecisionRecord | null>(null);

  const handleRun = async () => {
    const response = await fetch(`${API_BASE}/orchestrations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_text: requestText })
    });
    const data = await response.json();
    setSummary(data.summary);
    setAgentResponses(data.agent_responses);
    setDecisionRecord(data.decision_record);
  };

  return (
    <section>
      <h2>에이전트 오케스트레이션</h2>
      <label>PM 요청</label>
      <textarea
        value={requestText}
        onChange={(e) => setRequestText(e.target.value)}
      />
      <button onClick={handleRun}>오케스트레이션 실행</button>
      {summary && (
        <div className="card">
          <strong>통합 요약</strong>
          <p className="small">{summary}</p>
        </div>
      )}
      <div className="grid">
        {agentResponses.map((response) => (
          <div key={response.agent} className="card">
            <strong>{response.agent}</strong>
            <p className="small">{response.summary}</p>
            <p className="small">리스크: {response.risks.join(" · ")}</p>
          </div>
        ))}
      </div>
      {decisionRecord && (
        <div className="card">
          <strong>Decision Record (ADR)</strong>
          <p className="small">Decision: {decisionRecord.decision}</p>
          <p className="small">Rationale: {decisionRecord.rationale}</p>
          <p className="small">Owner: {decisionRecord.owner}</p>
        </div>
      )}
    </section>
  );
}
