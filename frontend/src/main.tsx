
  import { createRoot } from "react-dom/client";
  import App from "./app/App.tsx";
  import { initSentry } from "./app/sentry";
  import "./styles/index.css";

  initSentry();

  createRoot(document.getElementById("root")!).render(<App />);
