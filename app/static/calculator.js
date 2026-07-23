"use strict";

const form = document.querySelector("#winch-form");
const calculateButton = document.querySelector("#calculate-button");
const formErrors = document.querySelector("#form-errors");
const emptyState = document.querySelector("#empty-state");
const resultContent = document.querySelector("#result-content");

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
  dead_wraps: 3,
  force_input_location: "drum_rope_end",
  speed_input_location: "drum_rope_end",
  force_input_type: "rated",
  pulley_efficiency: 1,
};

document.querySelector("#load-golden-sample").addEventListener("click", () => {
  Object.entries(goldenSample).forEach(([name, value]) => {
    form.elements[name].value = String(value);
  });
  form.elements.backdrive_efficiency.value = "";
  form.elements.allow_forward_efficiency_as_reverse_approx.checked = false;
  formErrors.hidden = true;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFieldErrors();
  if (!form.checkValidity()) {
    form.reportValidity();
    showError("请先完成所有必填字段，并检查数值范围。", []);
    return;
  }

  setLoading(true);
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
      return;
    }
    formErrors.hidden = true;
    renderSnapshot(data);
  } catch (error) {
    showError("无法连接计算服务，请确认本地应用仍在运行。", []);
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

function renderSnapshot(snapshot) {
  emptyState.hidden = true;
  resultContent.hidden = false;
  document.querySelector("#report-link").href = snapshot.links.html_report;

  const meta = document.querySelector("#result-meta");
  meta.replaceChildren(
    metaItem("计算状态", statusLabel(snapshot.status), snapshot.status.includes("warnings") ? "amber" : "green"),
    metaItem("容量判定", snapshot.results.capacity_satisfied ? "满足" : "不满足", snapshot.results.capacity_satisfied ? "green" : "red"),
    metaItem("模型版本", snapshot.calculation_model_version, "blue"),
    metaItem("计算 ID", snapshot.calculation_id, "neutral"),
  );

  renderWarnings(snapshot.warnings);
  renderKeyResults(snapshot.results);
  renderLayers(snapshot.results.layer_details || []);
  renderAssumptions(snapshot.assumptions || []);
  resultContent.scrollIntoView({behavior: "smooth", block: "start"});
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
      .forEach((value) => {
        const cell = document.createElement("td");
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
  formErrors.scrollIntoView({behavior: "smooth", block: "center"});
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
function severityLabel(value) { return ({blocking: "阻断", high: "高", warning: "警告", info: "提示"})[value] || value; }
function classificationLabel(value) {
  return ({calculated: "理论计算", preliminary: "工程初选", review_required: "待校核", informational: "提示"})[value] || value;
}
