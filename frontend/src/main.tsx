
  import { createRoot } from "react-dom/client";
  import App from "./app/App.tsx";
  import { initSentry } from "./app/sentry";
  import { installPreloadErrorRecovery } from "./app/utils/preloadRecovery";
  import "./styles/index.css";

  initSentry();
  installPreloadErrorRecovery();

  createRoot(document.getElementById("root")!).render(<App />);
