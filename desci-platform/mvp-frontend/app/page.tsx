import ProgramPanel from "@/components/ProgramPanel";
import TaskPanel from "@/components/TaskPanel";
import OrchestrationPanel from "@/components/OrchestrationPanel";

export default function Home() {
  return (
    <>
      <h1>규제준수 협업 플랫폼 MVP</h1>
      <p className="small">
        규제 근거 기반 태스크 관리, 에이전트 오케스트레이션, 감사추적을
        위한 최소 기능 데모입니다.
      </p>
      <ProgramPanel />
      <TaskPanel />
      <OrchestrationPanel />
    </>
  );
}
