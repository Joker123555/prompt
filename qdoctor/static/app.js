"use strict";

const STATUS_LABELS = { found: "有", weak: "弱", missing: "缺" };
const STATUS_CLASS = { found: "is-found", weak: "is-weak", missing: "is-missing" };

const byId = (id) => document.getElementById(id);

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function block(title, children, action) {
  const wrapper = element("section", "block");
  const head = element("div", "block-head");
  head.appendChild(element("h2", "", title));
  if (action) head.appendChild(action);
  wrapper.appendChild(head);
  (children || []).forEach((child) => wrapper.appendChild(child));
  return wrapper;
}

async function request(path, options) {
  const response = await fetch(path, options || {});
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (err) {
    data = null;
  }
  if (!response.ok) {
    const message = (data && data.error) || `请求失败（HTTP ${response.status}）`;
    throw new Error(message);
  }
  return data;
}

function showError(id, message) {
  const node = byId(id);
  node.textContent = message;
  node.hidden = false;
}

function hideError(id) {
  const node = byId(id);
  node.textContent = "";
  node.hidden = true;
}

function setupTabs() {
  const tabs = Array.from(document.querySelectorAll(".tab"));
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((item) => {
        const active = item === tab;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", String(active));
        const panel = byId("panel-" + item.dataset.tab);
        if (panel) {
          panel.classList.toggle("is-active", active);
          panel.hidden = !active;
        }
      });
      if (tab.dataset.tab === "stats") loadStats();
    });
  });
}

async function loadHealth() {
  try {
    const health = await request("/api/health");
    const enabled = Boolean(health.llm);
    ["check-llm", "review-llm"].forEach((id) => {
      byId(id).disabled = !enabled;
    });
    const hint = enabled
      ? "开启后会把当前问题发给配置的 LLM"
      : "未配置 LLM；规则结果照常可用";
    byId("check-llm-hint").textContent = hint;
    byId("review-llm-hint").textContent = hint;
  } catch (err) {
    // 健康检查失败时保持开关禁用，规则功能仍可使用。
  }
}

function renderScore(score, summary) {
  const card = element("div", "score-card");
  const copy = element("div", "score-copy");
  const line = element("p", "score-line");
  line.appendChild(element("span", "score-number", score));
  line.appendChild(element("span", "score-unit", "/100"));
  copy.appendChild(line);
  copy.appendChild(element("p", "summary", summary));
  card.appendChild(copy);

  const bar = document.createElement("progress");
  bar.className = "score-bar";
  bar.max = 100;
  bar.value = score;
  bar.setAttribute("aria-label", `完整度 ${score} 分`);
  if (score < 50) bar.classList.add("is-low");
  else if (score < 80) bar.classList.add("is-mid");
  card.appendChild(bar);
  return card;
}

function renderSlot(slot) {
  const statusClass = STATUS_CLASS[slot.status] || "";
  const item = element("li", "slot");
  item.appendChild(
    element("span", `chip ${statusClass}`.trim(), STATUS_LABELS[slot.status] || slot.status)
  );

  const body = element("div", "slot-body");
  body.appendChild(element("p", "slot-label", slot.label));
  if (slot.status === "found") {
    body.appendChild(
      element("p", "slot-text", slot.excerpt ? `已检测到：${slot.excerpt}` : "已检测到")
    );
  } else {
    body.appendChild(element("p", "slot-text", slot.advice));
    if (slot.excerpt) {
      body.appendChild(element("p", "evidence", `原文：${slot.excerpt}`));
    }
  }
  item.appendChild(body);
  return item;
}

function renderCheck(data) {
  const root = byId("check-result");
  root.replaceChildren();
  root.hidden = false;
  root.appendChild(renderScore(data.score, data.summary));

  const slots = element("ul", "slot-list");
  data.slots.forEach((slot) => slots.appendChild(renderSlot(slot)));
  root.appendChild(block("要素诊断", [slots]));

  if (data.patterns && data.patterns.length) {
    const list = element("ul", "pattern-list");
    data.patterns.forEach((pattern) => {
      const item = element("li", "pattern");
      item.appendChild(element("span", "pattern-label", pattern.label));
      const body = element("div", "pattern-body");
      body.appendChild(element("p", "pattern-advice", pattern.advice));
      if (pattern.evidence && pattern.evidence.length) {
        body.appendChild(element("p", "evidence", `依据：${pattern.evidence.join("；")}`));
      }
      item.appendChild(body);
      list.appendChild(item);
    });
    root.appendChild(block("反模式", [list]));
  }

  if (data.followups && data.followups.length) {
    const list = element("ol", "followups");
    data.followups.forEach((question) => list.appendChild(element("li", "", question)));
    root.appendChild(block("先补这些信息", [list]));
  }

  const rewrite = element("pre", "rewrite");
  rewrite.textContent = data.rewrite;
  const copy = element("button", "secondary small", "复制改写稿");
  copy.type = "button";
  copy.addEventListener("click", () => copyText(data.rewrite, copy));
  root.appendChild(block("改写后的提问", [rewrite], copy));

  if (data.llm) {
    const llmText = element("pre", "rewrite");
    llmText.textContent = data.llm;
    root.appendChild(block("LLM 改写", [llmText]));
  }
  if (data.llm_error) {
    root.appendChild(block("LLM 未生效", [element("p", "hint", data.llm_error)]));
  }
}

function renderReview(data) {
  const root = byId("review-result");
  root.replaceChildren();
  root.hidden = false;

  const head = element("div", "review-head");
  head.appendChild(element("p", "eyebrow", `复盘 · ${data.problem_label}`));
  head.appendChild(
    element("p", "summary", `原问题体检 ${data.diagnosis.score}/100，${data.diagnosis.summary}`)
  );
  root.appendChild(head);

  const weakSlots = data.diagnosis.slots.filter((slot) => slot.status !== "found");
  if (weakSlots.length) {
    const row = element("div", "tag-row");
    weakSlots.forEach((slot) => row.appendChild(element("span", "tag", slot.label)));
    root.appendChild(block("仍然薄弱", [row]));
  }

  if (data.followups && data.followups.length) {
    const list = element("ol", "followups");
    data.followups.forEach((question) => list.appendChild(element("li", "", question)));
    root.appendChild(block("先补这些信息", [list]));
  }

  const nextPrompt = element("pre", "rewrite");
  nextPrompt.textContent = data.next_prompt;
  const copy = element("button", "secondary small", "复制追问");
  copy.type = "button";
  copy.addEventListener("click", () => copyText(data.next_prompt, copy));
  root.appendChild(block("下一轮追问", [nextPrompt], copy));

  if (data.llm) {
    const llmText = element("pre", "rewrite");
    llmText.textContent = data.llm;
    root.appendChild(block("LLM 追问", [llmText]));
  }
  if (data.llm_error) {
    root.appendChild(block("LLM 未生效", [element("p", "hint", data.llm_error)]));
  }
}

function metric(value, label) {
  const item = element("div", "metric");
  item.appendChild(element("p", "metric-value", value));
  item.appendChild(element("p", "metric-label", label));
  return item;
}

function rankList(items) {
  const list = element("ul", "rank-list");
  items.forEach((item) => {
    const row = element("li");
    row.appendChild(element("span", "rank-label", item.label));
    row.appendChild(element("span", "rank-count", `${item.count} 次`));
    list.appendChild(row);
  });
  return list;
}

function renderStats(data) {
  const root = byId("stats-result");
  root.replaceChildren();

  if (!data.count) {
    root.appendChild(element("p", "empty", "还没有记录。先在“体检”里跑一次。"));
    return;
  }

  const metrics = element("div", "metric-row");
  metrics.appendChild(metric(data.count, "最近记录"));
  metrics.appendChild(
    metric(data.average_score === null ? "—" : data.average_score, "平均分")
  );
  metrics.appendChild(metric(data.total, "累计记录"));
  root.appendChild(metrics);

  if (data.top_missing && data.top_missing.length) {
    root.appendChild(block("最常缺的要素", [rankList(data.top_missing)]));
  }
  if (data.top_patterns && data.top_patterns.length) {
    root.appendChild(block("最常见的反模式", [rankList(data.top_patterns)]));
  }
  if (data.skipped) {
    root.appendChild(element("p", "hint", `已跳过 ${data.skipped} 行损坏记录`));
  }
}

async function runCheck(event) {
  event.preventDefault();
  const text = byId("check-text").value.trim();
  if (!text) {
    showError("check-error", "先写一个要体检的问题。");
    return;
  }

  const button = byId("check-run");
  button.disabled = true;
  hideError("check-error");
  try {
    const data = await request("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, use_llm: byId("check-llm").checked }),
    });
    renderCheck(data);
  } catch (err) {
    showError("check-error", err.message);
  } finally {
    button.disabled = false;
  }
}

async function runReview(event) {
  event.preventDefault();
  const question = byId("review-question").value.trim();
  const answer = byId("review-answer").value.trim();
  if (!question) {
    showError("review-error", "先填原问题。");
    return;
  }
  if (!answer) {
    showError("review-error", "先把 AI 的回答贴进来。");
    return;
  }

  const button = byId("review-run");
  button.disabled = true;
  hideError("review-error");
  try {
    const data = await request("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        answer,
        wanted: byId("review-wanted").value.trim(),
        problem: byId("review-problem").value,
        use_llm: byId("review-llm").checked,
      }),
    });
    renderReview(data);
  } catch (err) {
    showError("review-error", err.message);
  } finally {
    button.disabled = false;
  }
}

async function loadStats() {
  hideError("stats-error");
  try {
    renderStats(await request("/api/stats?last=30"));
  } catch (err) {
    showError("stats-error", err.message);
  }
}

async function copyText(text, button) {
  let ok = false;
  try {
    await navigator.clipboard.writeText(text);
    ok = true;
  } catch (err) {
    ok = fallbackCopy(text);
  }
  if (!ok) return;

  const original = button.textContent;
  button.textContent = "已复制";
  window.setTimeout(() => {
    button.textContent = original;
  }, 1500);
}

function fallbackCopy(text) {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.className = "clipboard-helper";
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch (err) {
    ok = false;
  }
  area.remove();
  return ok;
}

document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  loadHealth();
  byId("check-form").addEventListener("submit", runCheck);
  byId("review-form").addEventListener("submit", runReview);
  byId("stats-run").addEventListener("click", loadStats);
});
