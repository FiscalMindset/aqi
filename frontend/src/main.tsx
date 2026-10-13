import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/index.css";
import { App } from "./app/App";
import { refreshIfStale, watchForUpdates } from "./lib/versionCheck";

void refreshIfStale();
watchForUpdates();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
