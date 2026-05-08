import { invoke } from "@tauri-apps/api/core";

interface ProxyConfig {
  port: number;
  openai_url: string;
  openai_key: string;
  anthropic_url: string;
  anthropic_key: string;
  mode: string;
  strong_k: number;
  python_path: string;
}

interface ProxyStatus {
  running: boolean;
  port: number;
  pid: number | null;
  message: string;
}

function getConfig(): ProxyConfig {
  return {
    port: parseInt((document.getElementById("port") as HTMLInputElement).value),
    openai_url: (document.getElementById("openaiUrl") as HTMLInputElement).value,
    openai_key: (document.getElementById("openaiKey") as HTMLInputElement).value,
    anthropic_url: (document.getElementById("anthropicUrl") as HTMLInputElement).value,
    anthropic_key: (document.getElementById("anthropicKey") as HTMLInputElement).value,
    mode: (document.getElementById("mode") as HTMLSelectElement).value,
    strong_k: parseInt((document.getElementById("strongK") as HTMLInputElement).value),
    python_path: (document.getElementById("pythonPath") as HTMLInputElement).value,
  };
}

function setUI(running: boolean, message: string, port?: number) {
  const bar = document.getElementById("statusBar")!;
  const dot = document.getElementById("statusDot")!;
  const text = document.getElementById("statusText")!;
  const box = document.getElementById("endpointBox")!;
  const btnStart = document.getElementById("btnStart") as HTMLButtonElement;
  const btnStop = document.getElementById("btnStop") as HTMLButtonElement;

  if (running) {
    bar.className = "status-bar running";
    dot.className = "dot on";
    text.textContent = message;
    box.style.display = "block";
    document.getElementById("endpointUrl")!.textContent = `http://127.0.0.1:${port || 8600}`;
    btnStart.disabled = true;
    btnStop.disabled = false;
  } else {
    bar.className = "status-bar stopped";
    dot.className = "dot off";
    text.textContent = message;
    box.style.display = "none";
    btnStart.disabled = false;
    btnStop.disabled = true;
  }
}

async function startProxy() {
  try {
    const config = getConfig();
    const result = await invoke<ProxyStatus>("start_proxy", { config });
    setUI(result.running, result.message, config.port);
  } catch (e) {
    setUI(false, "Failed: " + e);
  }
}

async function stopProxy() {
  try {
    const result = await invoke<ProxyStatus>("stop_proxy");
    setUI(false, result.message);
  } catch (e) {
    setUI(false, "Failed: " + e);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btnStart")!.addEventListener("click", startProxy);
  document.getElementById("btnStop")!.addEventListener("click", stopProxy);

  invoke<ProxyStatus>("get_status").then((s) => {
    if (s.running) setUI(true, "Running (PID: " + s.pid + ")", 8600);
  }).catch(() => {});
});
