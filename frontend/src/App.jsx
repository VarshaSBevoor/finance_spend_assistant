import ChatPanel from "./components/ChatPanel.jsx";
import SummaryPanel from "./components/SummaryPanel.jsx";

export default function App() {
  return (
    <main className="page">
      <h1>Finance spend assistant</h1>
      <div className="layout">
        <SummaryPanel />
        <ChatPanel />
      </div>
    </main>
  );
}
