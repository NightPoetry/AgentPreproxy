import { invoke } from "@tauri-apps/api/core";

// ============ i18n ============

const I18N: Record<string, Record<string, string>> = {
  en: {
    "sidebar.config": "CONFIGURATION",
    "sidebar.upstream": "Upstream API",
    "sidebar.proxy": "Proxy Settings",
    "sidebar.runtime": "RUNTIME",
    "sidebar.control": "Control",
    "upstream.title": "Upstream API Configuration",
    "proxy.title": "Proxy Settings",
    "control.title": "Proxy Control",
    "control.start": "▶ Start Proxy",
    "control.stop": "■ Stop Proxy",
    "control.endpoint": "Proxy endpoint:",
    "control.hint": "Point your AI agent software to this URL",
    "status.stopped": "Stopped",
    "status.running": "Running",
    "status.failed": "Failed",
    "mode.both": "both (recommended)",
    "mode.strong": "strong (fixed-period)",
    "mode.weak": "weak (on-demand)",
    "mode.off": "off (passthrough)",
  },
  zh: {
    "sidebar.config": "配置",
    "sidebar.upstream": "上游 API",
    "sidebar.proxy": "代理设置",
    "sidebar.runtime": "运行",
    "sidebar.control": "控制面板",
    "upstream.title": "上游 API 配置",
    "proxy.title": "代理设置",
    "control.title": "代理控制",
    "control.start": "▶ 启动代理",
    "control.stop": "■ 停止代理",
    "control.endpoint": "代理地址：",
    "control.hint": "将此地址填入你的智能体软件的 API 设置中",
    "status.stopped": "未启动",
    "status.running": "运行中",
    "status.failed": "启动失败",
    "mode.both": "both（强+弱，推荐）",
    "mode.strong": "strong（固定周期）",
    "mode.weak": "weak（按需触发）",
    "mode.off": "off（纯透传）",
  },
};

let currentLang = navigator.language.startsWith("zh") ? "zh" : "en";

function applyLang() {
  const dict = I18N[currentLang] || I18N.en;
  document.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n")!;
    if (dict[key]) el.textContent = dict[key];
  });
  document.querySelectorAll<HTMLOptionElement>("[data-i18n-opt]").forEach((el) => {
    const key = el.getAttribute("data-i18n-opt")!;
    if (dict[key]) el.textContent = dict[key];
  });
  document.getElementById("langZh")!.classList.toggle("active", currentLang === "zh");
  document.getElementById("langEn")!.classList.toggle("active", currentLang === "en");
}

(window as any).setLang = (lang: string) => {
  currentLang = lang;
  applyLang();
};

// ============ Panel navigation ============

function initSidebar() {
  document.querySelectorAll<HTMLElement>(".sidebar-item").forEach((item) => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".sidebar-item").forEach((i) => i.classList.remove("active"));
      item.classList.add("active");
      const panel = item.getAttribute("data-panel");
      document.querySelectorAll<HTMLElement>(".panel").forEach((p) => {
        p.style.display = p.id === `panel-${panel}` ? "block" : "none";
      });
    });
  });
}

// ============ Proxy control ============

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
  const dot = document.getElementById("statusDot")!;
  const text = document.getElementById("statusText")!;
  const box = document.getElementById("endpointBox")!;
  const btnStart = document.getElementById("btnStart") as HTMLButtonElement;
  const btnStop = document.getElementById("btnStop") as HTMLButtonElement;
  const dict = I18N[currentLang] || I18N.en;

  if (running) {
    dot.className = "status-dot on";
    text.textContent = `${dict["status.running"]} (PID: ${message})`;
    box.style.display = "block";
    document.getElementById("endpointUrl")!.textContent = `http://127.0.0.1:${port || 8600}`;
    btnStart.disabled = true;
    btnStop.disabled = false;
  } else {
    dot.className = "status-dot off";
    text.textContent = message || dict["status.stopped"];
    box.style.display = "none";
    btnStart.disabled = false;
    btnStop.disabled = true;
  }
}

async function startProxy() {
  try {
    const config = getConfig();
    document.getElementById("footerMode")!.textContent = config.mode;
    const result = await invoke<ProxyStatus>("start_proxy", { config });
    setUI(result.running, String(result.pid || ""), config.port);
  } catch (e) {
    const dict = I18N[currentLang] || I18N.en;
    setUI(false, dict["status.failed"] + ": " + e);
  }
}

async function stopProxy() {
  try {
    await invoke<ProxyStatus>("stop_proxy");
    setUI(false, "");
  } catch (e) {
    setUI(false, "Error: " + e);
  }
}

// ============ Init ============

window.addEventListener("DOMContentLoaded", () => {
  applyLang();
  initSidebar();

  document.getElementById("btnStart")!.addEventListener("click", startProxy);
  document.getElementById("btnStop")!.addEventListener("click", stopProxy);
  document.getElementById("mode")!.addEventListener("change", (e) => {
    document.getElementById("footerMode")!.textContent = (e.target as HTMLSelectElement).value;
  });

  invoke<ProxyStatus>("get_status").then((s) => {
    if (s.running) setUI(true, String(s.pid || ""), 8600);
  }).catch(() => {});
});
