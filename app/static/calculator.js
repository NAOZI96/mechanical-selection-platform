"use strict";

const form = document.querySelector("#winch-form");
const calculateButton = document.querySelector("#calculate-button");
const formErrors = document.querySelector("#form-errors");
const emptyState = document.querySelector("#empty-state");
const loadingState = document.querySelector("#loading-state");
const resultContent = document.querySelector("#result-content");
const resultPanel = document.querySelector("#results");
const SESSION_STORAGE_KEY = "winch_drum.calculator.session.v1";
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let resultState = "idle";

const numericFields = [
  "rated_line_pull_kn", "rope_diameter_mm", "rope_speed_m_per_min",
  "target_rope_capacity_m", "service_factor", "total_efficiency",
  "motor_rated_speed_rpm", "drum_core_diameter_mm", "drum_face_length_mm",
  "pitch_factor", "side_margin_mm", "reeving_ratio", "brake_safety_factor",
  "approved_core_ratio", "pulley_efficiency", "actual_groove_pitch_mm",
  "termination_allowance_m", "duty_cycle_percent", "supply_voltage",
  "supply_frequency", "backdrive_efficiency", "minimum_dd_ratio",
];
const integerFields = ["max_layers", "dead_wraps", "starts_per_hour", "actual_usable_groove_count"];
const optionalFields = new Set(["drum_core_diameter_mm", "drum_face_length_mm", "approved_core_ratio", "actual_groove_pitch_mm", "actual_usable_groove_count", "backdrive_efficiency"]);

const goldenSample = {
  rated_line_pull_kn: 100,
  rope_diameter_mm: 20,
  rope_speed_m_per_min: 12,
  target_rope_capacity_m: 300,
  service_factor: 1.2,
  total_efficiency: 0.85,
  motor_rated_speed_rpm: 1470,
  motor_type: "三相异步电动机",
  drum_core_diameter_mm: 400,
  drum_face_length_mm: 800,
  max_layers: 6,
  pitch_factor: 1.05,
  side_margin_mm: 20,
  reeving_ratio: 1,
  brake_safety_factor: 1.5,
  duty_class: "测试工况，仅提示",
  rope_type: "镀锌钢丝绳",
  rope_construction: "6×36-IWRC",
  rope_material: "镀锌钢",
  load_spectrum: "中等载荷",
  environment_type: "室内常温干燥环境",
  dead_wraps: 3,
  force_input_location: "drum_rope_end",
  speed_input_location: "drum_rope_end",
  force_input_type: "rated",
  pulley_efficiency: 1,
};

function loadGoldenSample() {
  Object.entries(goldenSample).forEach(([name, value]) => {
    form.elements[name].value = String(value);
  });
  form.elements.backdrive_efficiency.value = "";
  form.elements.allow_forward_efficiency_as_reverse_approx.checked = false;
  formErrors.hidden = true;
  saveSessionState();
}

function clearCalculatorSession() {
  const confirmed = window.confirm("确认清空当前标签页中的计算参数和最近结果吗？已保存的历史报告不会删除。");
  if (!confirmed) return;

  form.reset();
  clearFieldErrors();
  formErrors.replaceChildren();
  formErrors.hidden = true;
  try {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch (error) {
    console.warn("无法清除本次访问的计算参数。", error);
  }
  document.querySelector("#report-link").href = "#";
  setResultState("idle");
  form.querySelector("input, select")?.focus({preventScroll: true});
}

document.querySelector("#clear-calculator").addEventListener("click", clearCalculatorSession);
document.querySelector("#load-golden-sample").addEventListener("click", loadGoldenSample);
document.querySelector("#back-to-input").addEventListener("click", () => {
  form.scrollIntoView({behavior: scrollBehavior(), block: "start"});
  form.querySelector("input, select")?.focus({preventScroll: true});
});
form.addEventListener("input", () => saveSessionState());
form.addEventListener("change", () => saveSessionState());
if (new URLSearchParams(window.location.search).get("sample") === "golden") {
  loadGoldenSample();
} else {
  restoreSessionState();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFieldErrors();
  if (!form.checkValidity()) {
    form.reportValidity();
    showError("请先完成所有必填字段，并检查数值范围。", []);
    return;
  }

  const previousResultState = resultState;
  setLoading(true);
  setResultState("loading");
  try {
    const response = await fetch("/api/v1/modules/winch_drum/calculations", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(buildPayload()),
    });
    const data = await response.json();
    if (!response.ok) {
      const error = data.error || {message: "计算请求失败", details: []};
      showError(error.message, error.details || []);
      setResultState(previousResultState);
      return;
    }
    formErrors.hidden = true;
    saveSessionState(data);
    renderSnapshot(data);
  } catch (error) {
    showError("无法连接计算服务，请确认本地应用仍在运行。", []);
    setResultState(previousResultState);
  } finally {
    setLoading(false);
  }
});

function buildPayload() {
  const input = {
    motor_type: form.elements.motor_type.value.trim(),
    duty_class: form.elements.duty_class.value.trim(),
    force_input_location: form.elements.force_input_location.value,
    speed_input_location: form.elements.speed_input_location.value,
    force_input_type: form.elements.force_input_type.value,
    motor_duty_type: form.elements.motor_duty_type.value,
    motor_power_series_id: form.elements.motor_power_series_id.value,
    rope_type: form.elements.rope_type.value.trim(),
    rope_construction: form.elements.rope_construction.value.trim(),
    rope_material: form.elements.rope_material.value.trim(),
    load_spectrum: form.elements.load_spectrum.value.trim(),
    environment_type: form.elements.environment_type.value.trim(),
    brake_basis_type: form.elements.brake_basis_type.value,
    brake_installation_shaft: form.elements.brake_installation_shaft.value,
    transmission_backdrive_type: form.elements.transmission_backdrive_type.value,
    allow_forward_efficiency_as_reverse_approx:
      form.elements.allow_forward_efficiency_as_reverse_approx.checked,
  };
  numericFields.forEach((name) => {
    const raw = form.elements[name].value.trim();
    if (raw !== "" || !optionalFields.has(name)) input[name] = Number(raw);
  });
  integerFields.forEach((name) => {
    const raw = form.elements[name].value.trim();
    if (raw !== "" || !optionalFields.has(name)) input[name] = Number.parseInt(raw, 10);
  });
  return {
    input,
    assumption_sources: {
      service_factor: form.elements.source_service_factor.value,
      pitch_factor: form.elements.source_pitch_factor.value,
      brake_safety_factor: form.elements.source_brake_safety_factor.value,
      approved_core_ratio: form.elements.source_approved_core_ratio.value,
      minimum_dd_ratio: form.elements.source_minimum_dd_ratio.value,
      pulley_efficiency: form.elements.source_pulley_efficiency.value,
      dead_wrap_count: form.elements.source_dead_wrap_count.value,
      backdrive_efficiency: form.elements.source_backdrive_efficiency.value,
    },
  };
}

function serializeForm() {
  const values = {};
  Array.from(form.elements).forEach((field) => {
    if (!field.name) return;
    values[field.name] = field.type === "checkbox" ? field.checked : field.value;
  });
  return values;
}

function saveSessionState(snapshot) {
  try {
    const previous = readSessionState();
    const state = {
      version: 1,
      form: serializeForm(),
      snapshot: snapshot === undefined ? previous?.snapshot || null : snapshot,
    };
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.warn("无法保存本次访问的计算参数。", error);
  }
}

function readSessionState() {
  try {
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const state = JSON.parse(raw);
    return state?.version === 1 && state.form && typeof state.form === "object" ? state : null;
  } catch (error) {
    console.warn("无法读取本次访问的计算参数。", error);
    return null;
  }
}

function restoreSessionState() {
  const state = readSessionState();
  if (!state) return;
  Object.entries(state.form).forEach(([name, value]) => {
    const field = form.elements[name];
    if (!field) return;
    if (field.type === "checkbox") {
      field.checked = value === true;
    } else if (typeof value === "string") {
      field.value = value;
    }
  });
  if (state.snapshot?.module_id === "winch_drum" && state.snapshot?.results && state.snapshot?.links) {
    renderSnapshot(state.snapshot, {focus: false});
  }
}

function renderSnapshot(snapshot, {focus = true} = {}) {
  setResultState("result");
  document.querySelector("#report-link").href = snapshot.links.html_report;

  const meta = document.querySelector("#result-meta");
  meta.replaceChildren(
    metaItem("计算状态", statusLabel(snapshot.status), snapshot.status.includes("warnings") ? "amber" : "green"),
    metaItem("容量判定", snapshot.results.capacity_satisfied ? "满足" : "不满足", snapshot.results.capacity_satisfied ? "green" : "red"),
    metaItem("计算时工程状态", releaseStatusLabel(snapshot.release_status), "amber"),
    metaItem("模型版本", snapshot.calculation_model_version, "blue"),
    metaItem("计算 ID", snapshot.calculation_id, "neutral"),
  );

  renderWarnings(snapshot.warnings);
  renderDesignConclusion(snapshot);
  renderChecks(snapshot);
  renderKeyResults(snapshot.results);
  renderLayers(snapshot.results.layer_details || []);
  renderAssumptions(snapshot.assumptions || []);
  if (focus) {
    resultContent.focus({preventScroll: true});
    resultContent.scrollIntoView({behavior: scrollBehavior(), block: "start"});
  }
}

function setResultState(state) {
  resultState = state;
  resultPanel.dataset.state = state;
  resultPanel.setAttribute("aria-busy", String(state === "loading"));
  emptyState.hidden = state !== "idle";
  loadingState.hidden = state !== "loading";
  resultContent.hidden = state !== "result";
}

function renderDesignConclusion(snapshot) {
  const container = document.querySelector("#design-conclusion");
  const severities = new Set(snapshot.warnings.map((warning) => warning.severity));
  let tone = "review";
  let title = "完成初步计算，仍需工程复核";
  let message = "当前快照只证明所列公式已执行，不代表整机设计、制造或采购合格。";
  if (severities.has("blocking") || !snapshot.results.capacity_satisfied) {
    tone = "fail";
    title = "当前方案不可行";
    message = "存在阻断项或容绳量不足，请修正输入后重新计算。";
  } else if (severities.has("high")) {
    tone = "risk";
    title = "参数存在高风险，不得判定设计合格";
    message = "高等级警告、专项强度或动态校核尚未关闭，只能用于方案比较与初步选型。";
  } else if (snapshot.warnings.length) {
    tone = "conditional";
    title = "有条件的初步结果";
    message = "请关闭全部警告并完成适用标准与专业审核后，再进入详细设计。";
  }
  const heading = document.createElement("h3");
  heading.textContent = title;
  const body = document.createElement("p");
  body.textContent = message;
  container.className = `design-conclusion design-conclusion--${tone}`;
  container.replaceChildren(heading, body);
}

function renderChecks(snapshot) {
  const results = snapshot.results;
  const input = snapshot.input_original;
  const rows = [
    {
      name: "D/d（第一层绳中心直径）",
      calculated: formatNumber(results.dd_ratio_first_layer),
      requirement: `≥ ${formatNumber(input.minimum_dd_ratio)}`,
      status: results.dd_ratio_first_layer >= input.minimum_dd_ratio ? "满足" : "不满足",
    },
    {
      name: "可用工作绳长",
      calculated: `${formatNumber(results.available_work_rope_length_m)} m`,
      requirement: `≥ ${formatNumber(input.target_rope_capacity_m)} m`,
      status: results.capacity_satisfied ? "满足" : "不满足",
    },
    {
      name: "电机稳态功率",
      calculated: `${formatNumber((results.minimum_motor_power_w.value || 0) / 1000)} kW`,
      requirement: results.suggested_motor_power_w.value === null
        ? "超出已配置功率系列"
        : `初选 ${formatNumber(results.suggested_motor_power_w.value / 1000)} kW`,
      status: results.suggested_motor_power_w.value === null ? "不满足" : "初选满足",
    },
    {
      name: "低速轴静态制动力矩",
      calculated: results.low_speed_brake_torque_nm.value === null
        ? "—"
        : `${formatNumber(results.low_speed_brake_torque_nm.value / 1000)} kN·m`,
      requirement: "选用制动器需不低于计算值",
      status: "待校核",
    },
  ];
  const body = document.querySelector("#check-rows");
  body.replaceChildren();
  rows.forEach((item) => {
    const row = document.createElement("tr");
    [item.name, item.calculated, item.requirement].forEach((value, index) => {
      const cell = document.createElement(index === 0 ? "th" : "td");
      if (index === 0) cell.scope = "row";
      cell.textContent = value;
      row.append(cell);
    });
    const status = document.createElement("td");
    status.append(chip(item.status, checkTone(item.status)));
    row.append(status);
    body.append(row);
  });
}

function renderWarnings(warnings) {
  document.querySelector("#warning-count").textContent = `${warnings.length} 项`;
  const list = document.querySelector("#warning-list");
  list.replaceChildren();
  warnings.forEach((warning) => {
    const item = document.createElement("li");
    item.className = `warning warning--${warning.severity}`;
    const head = document.createElement("div");
    head.append(chip(severityLabel(warning.severity), warning.severity), textNode(` ${warning.code}`));
    const message = document.createElement("p");
    message.textContent = warning.message;
    item.append(head, message);
    list.append(item);
  });
}

function renderKeyResults(results) {
  const definitions = [
    ["设计绳端拉力", results.design_line_pull_n],
    ["理论负载功率", results.theoretical_load_power_w],
    ["最低所需电机功率", results.minimum_motor_power_w],
    ["建议电机功率", results.suggested_motor_power_w],
    ["采用 / 建议芯径", results.used_or_suggested_core_diameter_m],
    ["采用 / 建议面长", results.used_or_suggested_drum_face_length_m],
    ["低速轴静态制动力矩", results.low_speed_brake_torque_nm],
    ["高速轴参考制动力矩", results.high_speed_brake_torque_ref_nm],
  ];
  const container = document.querySelector("#key-results");
  container.replaceChildren();
  definitions.forEach(([label, result]) => container.append(resultCard(label, result)));

  const capacity = document.createElement("article");
  capacity.className = "result-card result-card--wide";
  const title = document.createElement("h4");
  title.textContent = "容绳与转速摘要";
  const body = document.createElement("p");
  const layerText = results.actual_layers === null ? "待确认" : `${results.actual_layers} 层`;
  const outerSpeed = results.capacity_satisfied
    ? results.full_drum_speed_rpm
    : results.max_layer_drum_speed_rpm;
  const outerLabel = results.capacity_satisfied ? "满卷" : "允许最大层";
  body.textContent = `实际层数 ${layerText}；最大层容量 ${formatNumber(results.capacity_at_max_layers_m)} m；空卷/${outerLabel}转速 ${formatNumber(results.empty_drum_speed_rpm)} / ${formatNumber(outerSpeed)} r/min；参考速比 ${formatNumber(results.reference_ratio_nominal)}。`;
  capacity.append(title, body);
  container.append(capacity);
}

function renderLayers(layers) {
  const body = document.querySelector("#layer-rows");
  body.replaceChildren();
  layers.forEach((layer) => {
    const row = document.createElement("tr");
    [layer.layer_number, layer.center_diameter_m, layer.turn_length_m, layer.full_turns,
      layer.used_turns, layer.used_capacity_m, layer.cumulative_used_capacity_m]
      .forEach((value, index) => {
        const cell = document.createElement(index === 0 ? "th" : "td");
        if (index === 0) cell.scope = "row";
        cell.textContent = typeof value === "number" ? formatNumber(value, 4) : String(value ?? "—");
        row.append(cell);
      });
    body.append(row);
  });
}

function renderAssumptions(assumptions) {
  const list = document.querySelector("#assumption-list");
  list.replaceChildren();
  assumptions.forEach((assumption) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = `${assumption.key} · ${assumption.source_status}`;
    const note = document.createElement("span");
    note.textContent = assumption.note;
    item.append(title, note);
    list.append(item);
  });
}

function resultCard(label, result) {
  const card = document.createElement("article");
  card.className = `result-card result-card--${result.classification}`;
  const title = document.createElement("h4");
  title.textContent = label;
  const value = document.createElement("p");
  value.className = "result-value";
  value.textContent = result.value === null ? "待工程师确认" : `${formatNumber(result.value)} ${result.unit}`;
  const footer = document.createElement("div");
  footer.append(chip(classificationLabel(result.classification), result.classification));
  if (result.reason) {
    const reason = document.createElement("small");
    reason.textContent = result.reason;
    card.append(title, value, footer, reason);
  } else {
    card.append(title, value, footer);
  }
  return card;
}

function showError(message, details) {
  formErrors.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = message;
  formErrors.append(title);
  if (details.length) {
    const list = document.createElement("ul");
    details.forEach((detail) => {
      const item = document.createElement("li");
      item.textContent = `${detail.field || "输入"}：${detail.message}`;
      list.append(item);
      const field = form.elements[detail.field];
      if (field) field.setAttribute("aria-invalid", "true");
    });
    formErrors.append(list);
  }
  formErrors.hidden = false;
  formErrors.scrollIntoView({behavior: scrollBehavior(), block: "center"});
}

function clearFieldErrors() {
  form.querySelectorAll("[aria-invalid='true']").forEach((field) => field.removeAttribute("aria-invalid"));
}

function setLoading(loading) {
  calculateButton.disabled = loading;
  calculateButton.textContent = loading ? "正在计算并保存…" : "保存快照并计算";
}

function metaItem(label, value, tone) {
  const item = document.createElement("div");
  item.className = `meta-item meta-item--${tone}`;
  const name = document.createElement("span");
  name.textContent = label;
  const content = document.createElement("strong");
  content.textContent = value;
  item.append(name, content);
  return item;
}

function chip(label, tone) {
  const element = document.createElement("span");
  element.className = `chip chip--${tone}`;
  element.textContent = label;
  return element;
}

function textNode(value) { return document.createTextNode(value); }
function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("zh-CN", {maximumFractionDigits: digits}).format(value);
}
function statusLabel(status) { return status === "completed" ? "计算完成" : "完成，存在警告"; }
function releaseStatusLabel(value) {
  return ({
    internal_testing: "内部测试",
    engineering_review: "工程审核中",
    released: "工程已放行",
    legacy_unknown: "未记录",
  })[value] || "未记录";
}
function scrollBehavior() { return reduceMotion.matches ? "auto" : "smooth"; }
function severityLabel(value) { return ({blocking: "阻断", high: "高", warning: "警告", info: "提示"})[value] || value; }
function checkTone(value) {
  return ({"满足": "calculated", "初选满足": "preliminary", "不满足": "blocking", "待校核": "review_required"})[value] || "informational";
}
function classificationLabel(value) {
  return ({calculated: "理论计算", preliminary: "工程初选", review_required: "待校核", informational: "提示"})[value] || value;
}
