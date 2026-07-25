"use strict";

const root = document.querySelector("[data-engineering-workbench]");
const moduleId = root?.dataset.moduleId;
const moduleName = root?.dataset.moduleName || moduleId;
const form = document.querySelector("#engineering-form");
const fieldsRoot = document.querySelector("#engineering-fields");
const schemaLoading = document.querySelector("#schema-loading");
const formErrors = document.querySelector("#engineering-form-errors");
const resultsPanel = document.querySelector("#engineering-results");
const emptyState = document.querySelector("#engineering-empty");
const loadingState = document.querySelector("#engineering-loading");
const resultContent = document.querySelector("#engineering-result-content");
const resultStatus = document.querySelector("#engineering-result-status");
const sessionKey = `engineering.${moduleId}.session.v1`;

let inputSchema = null;
let requiredFields = new Set();
let resultState = "idle";
let resultLabels = {};
let uncheckedLabels = {};
let assumptionLabels = {};
let exampleInput = {};

const classificationLabels = {
  calculated: "理论计算值",
  preliminary: "初选值",
  review_required: "待校核值",
  informational: "信息值",
};

const statusLabels = {
  completed: "计算完成",
  completed_with_warnings: "计算完成（有警告）",
};

const sourceLabels = {
  user_input: "用户输入",
  project_setting: "项目设定",
  standard_confirmed: "标准已确认",
  manufacturer_data: "制造商数据",
  pending_confirmation: "待确认",
};

initialize();

async function initialize() {
  if (!moduleId) {
    showFatal("页面缺少模块标识，无法读取输入契约。");
    return;
  }
  try {
    const response = await fetch(`/api/v1/modules/${encodeURIComponent(moduleId)}/schema`);
    const data = await response.json();
    if (!response.ok) throw new Error(data?.error?.message || "输入契约读取失败");
    inputSchema = data.input_schema;
    resultLabels = data.result_labels || {};
    uncheckedLabels = data.unchecked_labels || {};
    assumptionLabels = data.assumption_labels || {};
    exampleInput = data.example_input || {};
    requiredFields = new Set(inputSchema.required || []);
    renderForm(inputSchema);
    restoreSessionState();
    schemaLoading.hidden = true;
    form.hidden = false;
  } catch (error) {
    showFatal(error instanceof Error ? error.message : "输入契约读取失败");
  }
}

function renderForm(schema) {
  const groups = new Map();
  Object.entries(schema.properties || {}).forEach(([name, propertySchema]) => {
    const normalized = normalizeSchema(propertySchema);
    const groupName = normalized.group || propertySchema.group || "工程输入";
    if (!groups.has(groupName)) groups.set(groupName, []);
    groups.get(groupName).push(createField(name, propertySchema, normalized));
  });
  groups.forEach((fields, groupName) => {
    const fieldset = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = groupName;
    fieldset.append(legend, ...fields);
    fieldsRoot.append(fieldset);
  });
}

function normalizeSchema(propertySchema) {
  let normalized = {...propertySchema};
  if (Array.isArray(normalized.anyOf)) {
    const nonNull = normalized.anyOf.find((item) => item.type !== "null") || {};
    normalized = {...resolveReference(nonNull), ...normalized};
    delete normalized.anyOf;
  }
  normalized = {...resolveReference(normalized), ...normalized};
  return normalized;
}

function resolveReference(schema) {
  if (!schema?.$ref || !inputSchema?.$defs) return schema || {};
  const key = schema.$ref.split("/").at(-1);
  return inputSchema.$defs[key] || schema;
}

function createField(name, sourceSchema, normalized) {
  const wrapper = document.createElement("div");
  wrapper.className = normalized.type === "boolean" ? "engineering-field engineering-field--boolean" : "engineering-field";

  const label = document.createElement("label");
  label.htmlFor = `field-${name}`;
  label.textContent = normalized.title || sourceSchema.title || name;
  if (requiredFields.has(name)) {
    const required = document.createElement("span");
    required.textContent = " 必填";
    required.className = "engineering-required";
    label.append(required);
  }

  const control = createControl(name, normalized);
  const help = document.createElement("small");
  const unit = normalized.unit || sourceSchema.unit;
  help.textContent = [normalized.description || sourceSchema.description, unit ? `显示单位：${unit}` : ""]
    .filter(Boolean)
    .join(" · ");
  help.id = `help-${name}`;
  control.setAttribute("aria-describedby", help.id);

  const error = document.createElement("small");
  error.className = "engineering-field-error";
  error.id = `error-${name}`;
  error.hidden = true;
  wrapper.append(label, control, help, error);
  return wrapper;
}

function createControl(name, schema) {
  let control;
  if (Array.isArray(schema.enum)) {
    control = document.createElement("select");
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "请选择";
    control.append(placeholder);
    schema.enum.forEach((value) => {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = sourceLabels[value] || String(value);
      control.append(option);
    });
    control.dataset.jsonType = "string";
  } else if (schema.type === "array" || schema.type === "object") {
    control = document.createElement("textarea");
    control.rows = schema.type === "array" ? 12 : 8;
    control.spellcheck = false;
    control.dataset.jsonType = "json";
    control.placeholder = schema.type === "array" ? "请输入 JSON 数组" : "请输入 JSON 对象";
  } else if (schema.type === "boolean") {
    control = document.createElement("input");
    control.type = "checkbox";
    control.dataset.jsonType = "boolean";
  } else {
    control = document.createElement("input");
    control.type = schema.type === "number" || schema.type === "integer" ? "number" : "text";
    control.dataset.jsonType = schema.type || "string";
    if (control.type === "number") {
      control.step = schema.type === "integer" ? "1" : "any";
      if (schema.minimum !== undefined) control.min = String(schema.minimum);
      if (schema.maximum !== undefined) control.max = String(schema.maximum);
    }
    if (schema.maxLength !== undefined) control.maxLength = schema.maxLength;
  }
  control.id = `field-${name}`;
  control.name = name;
  control.required = requiredFields.has(name) && schema.type !== "boolean";
  const sample = schema.examples?.[0];
  if (sample !== undefined) control.dataset.sample = JSON.stringify(sample);
  return control;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors();
  if (!form.checkValidity()) {
    form.reportValidity();
    showFormError("请完成所有必填字段，并检查浏览器标出的数值范围。");
    return;
  }
  const previousState = resultState;
  setResultState("loading");
  document.querySelector("#engineering-calculate").disabled = true;
  try {
    const input = readInput();
    const response = await fetch(`/api/v1/modules/${encodeURIComponent(moduleId)}/calculations`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({input}),
    });
    const data = await response.json();
    if (!response.ok) {
      showApiErrors(data?.error);
      setResultState(previousState);
      return;
    }
    renderSnapshot(data);
    saveSessionState(input, data);
  } catch (error) {
    showFormError(error instanceof Error ? error.message : "无法连接计算服务。");
    setResultState(previousState);
  } finally {
    document.querySelector("#engineering-calculate").disabled = false;
  }
});

document.querySelector("#engineering-load-sample")?.addEventListener("click", () => {
  form.querySelectorAll("[name]").forEach((control) => {
    const sample = Object.hasOwn(exampleInput, control.name)
      ? exampleInput[control.name]
      : control.dataset.sample === undefined
        ? undefined
        : JSON.parse(control.dataset.sample);
    if (sample === undefined || sample === null) return;
    if (control.type === "checkbox") control.checked = Boolean(sample);
    else control.value = formatControlValue(control, sample);
  });
  clearErrors();
  saveSessionState(readInput(), null);
});

document.querySelector("#engineering-clear")?.addEventListener("click", () => {
  if (!window.confirm("确认清空当前模块参数和本标签页中的最近结果吗？已保存的报告不会删除。")) return;
  form.reset();
  clearErrors();
  window.sessionStorage.removeItem(sessionKey);
  setResultState("idle");
});

document.querySelector("#engineering-back-to-input")?.addEventListener("click", () => {
  form.scrollIntoView({behavior: "smooth", block: "start"});
  form.querySelector("input, select, textarea")?.focus({preventScroll: true});
});

form?.addEventListener("input", () => {
  try {
    saveSessionState(readInput(), readSessionState()?.snapshot || null);
  } catch {
    // Incomplete numeric input is expected while the user is editing.
  }
});

function readInput() {
  const input = {};
  form.querySelectorAll("[name]").forEach((control) => {
    const type = control.dataset.jsonType;
    if (type === "boolean") {
      input[control.name] = control.checked;
      return;
    }
    const raw = control.value.trim();
    if (raw === "" && !requiredFields.has(control.name)) return;
    if (type === "number") {
      const numericValue = Number(raw);
      if (!Number.isFinite(numericValue)) {
        throw new Error(`${control.labels?.[0]?.textContent || control.name} 必须是有限数值。`);
      }
      input[control.name] = numericValue;
    }
    else if (type === "integer") {
      const integerValue = Number(raw);
      if (!Number.isInteger(integerValue)) {
        throw new Error(`${control.labels?.[0]?.textContent || control.name} 必须是整数。`);
      }
      input[control.name] = integerValue;
    }
    else if (type === "json") {
      try {
        input[control.name] = JSON.parse(raw);
      } catch {
        throw new Error(`${control.labels?.[0]?.textContent || control.name} 必须是有效 JSON。`);
      }
    }
    else input[control.name] = raw;
  });
  return input;
}

function renderSnapshot(snapshot, {focus = true} = {}) {
  setResultState("result");
  const meta = document.querySelector("#engineering-meta");
  meta.replaceChildren(
    metaItem("模块", moduleName),
    metaItem("状态", statusLabels[snapshot.status] || snapshot.status),
    metaItem("模型版本", snapshot.calculation_model_version),
    metaItem("计算 ID", snapshot.calculation_id),
  );
  renderWarnings(snapshot.warnings || []);
  renderResults(snapshot.results || {});
  renderSteps(snapshot.steps || []);
  renderAssumptions(snapshot.assumptions || []);
  renderUnchecked(snapshot.results?.unchecked_items || []);
  document.querySelector("#engineering-html-report").href = snapshot.links.html_report;
  document.querySelector("#engineering-pdf-report").href = snapshot.links.pdf;
  if (focus) {
    resultContent.focus({preventScroll: true});
    resultContent.scrollIntoView({behavior: "smooth", block: "start"});
  }
}

function renderWarnings(warnings) {
  const container = document.querySelector("#engineering-warnings");
  container.replaceChildren();
  if (!warnings.length) {
    const message = document.createElement("p");
    message.textContent = "本次快照没有记录工程警告。";
    container.append(message);
    return;
  }
  warnings.forEach((warning) => {
    const article = document.createElement("article");
    article.className = `engineering-warning engineering-warning--${warning.severity}`;
    const title = document.createElement("strong");
    title.textContent = `${warning.code} · ${warning.title}`;
    const message = document.createElement("p");
    message.textContent = warning.message;
    const action = document.createElement("small");
    action.textContent = warning.recommended_action;
    article.append(title, message, action);
    container.append(article);
  });
}

function renderResults(results) {
  const tbody = document.querySelector("#engineering-result-rows");
  tbody.replaceChildren();
  Object.entries(results)
    .filter(([, item]) => item && typeof item === "object" && "classification" in item)
    .forEach(([key, item]) => {
      const row = document.createElement("tr");
      [resultLabels[key] || key, formatValue(item.value), item.unit || "", classificationLabels[item.classification] || item.classification,
        (item.formula_ids || []).join("、")].forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      });
      tbody.append(row);
      if (item.reason) {
        const reasonRow = document.createElement("tr");
        reasonRow.className = "engineering-reason-row";
        const reason = document.createElement("td");
        reason.colSpan = 5;
        reason.textContent = item.reason;
        reasonRow.append(reason);
        tbody.append(reasonRow);
      }
    });
}

function renderSteps(steps) {
  const list = document.querySelector("#engineering-steps");
  list.replaceChildren();
  steps.forEach((step) => {
    const item = document.createElement("li");
    const header = document.createElement("strong");
    header.textContent = `${step.sequence}. ${step.formula_id}`;
    const expression = document.createElement("code");
    expression.textContent = step.expression;
    const variables = document.createElement("small");
    variables.textContent = `代入值：${Object.entries(step.variables || {}).map(([key, value]) => `${key}=${formatValue(value)}`).join("；")}`;
    const result = document.createElement("span");
    result.textContent = `结果：${formatValue(step.result_value)} ${step.unit || ""}`;
    item.append(header, expression, variables, result);
    list.append(item);
  });
}

function renderAssumptions(assumptions) {
  const list = document.querySelector("#engineering-assumptions");
  list.replaceChildren();
  assumptions.forEach((assumption) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = `${assumptionDisplayLabel(assumption.key)} · ${sourceLabels[assumption.source_status] || assumption.source_status}`;
    const message = document.createElement("span");
    message.textContent = `${formatValue(assumption.value)}${assumption.unit ? ` ${assumption.unit}` : ""}；${assumption.note}`;
    item.append(title, message);
    list.append(item);
  });
}

function assumptionDisplayLabel(key) {
  if (assumptionLabels[key]) return assumptionLabels[key];
  const stageParameter = /^stage_(\d+)_(ratio|efficiency)$/.exec(key);
  if (!stageParameter) return key;
  const parameterLabel = stageParameter[2] === "ratio" ? "传动比" : "正向效率";
  return `第 ${stageParameter[1]} 级${parameterLabel}`;
}

function renderUnchecked(items) {
  const list = document.querySelector("#engineering-unchecked");
  list.replaceChildren();
  items.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = uncheckedLabels[value] || value;
    list.append(item);
  });
}

function metaItem(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value;
  wrapper.append(term, description);
  return wrapper;
}

function setResultState(state) {
  resultState = state;
  resultsPanel.dataset.state = state;
  emptyState.hidden = state !== "idle";
  loadingState.hidden = state !== "loading";
  resultContent.hidden = state !== "result";
  resultStatus.textContent = state === "loading" ? "计算中" : state === "result" ? "已生成快照" : "等待计算";
}

function clearErrors() {
  formErrors.hidden = true;
  formErrors.replaceChildren();
  form.querySelectorAll("[aria-invalid='true']").forEach((control) => control.removeAttribute("aria-invalid"));
  form.querySelectorAll(".engineering-field-error").forEach((error) => {
    error.hidden = true;
    error.textContent = "";
  });
}

function showApiErrors(error) {
  const details = error?.details || [];
  showFormError(error?.message || "输入未通过校验。");
  details.forEach((detail) => {
    const fieldName = String(detail.field || "").split(".").at(-1);
    const control = form.elements[fieldName];
    const fieldError = document.querySelector(`#error-${CSS.escape(fieldName)}`);
    if (control) control.setAttribute("aria-invalid", "true");
    if (fieldError) {
      fieldError.textContent = detail.message || "输入无效";
      fieldError.hidden = false;
    }
  });
}

function showFormError(message) {
  formErrors.textContent = message;
  formErrors.hidden = false;
}

function showFatal(message) {
  schemaLoading.textContent = message;
  schemaLoading.classList.add("engineering-placeholder--error");
}

function formatValue(value) {
  if (value === null || value === undefined) return "待校核";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") {
    if (value === 0) return "0";
    const magnitude = Math.abs(value);
    return magnitude >= 1e8 || magnitude < 1e-5 ? value.toExponential(6) : Number(value.toPrecision(10)).toString();
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function saveSessionState(input, snapshot) {
  try {
    window.sessionStorage.setItem(sessionKey, JSON.stringify({version: 1, input, snapshot}));
  } catch (error) {
    console.warn("无法保存当前模块会话。", error);
  }
}

function readSessionState() {
  try {
    const raw = window.sessionStorage.getItem(sessionKey);
    if (!raw) return null;
    const state = JSON.parse(raw);
    return state?.version === 1 ? state : null;
  } catch {
    return null;
  }
}

function restoreSessionState() {
  const state = readSessionState();
  if (!state) return;
  Object.entries(state.input || {}).forEach(([name, value]) => {
    const control = form.elements[name];
    if (!control) return;
    if (control.type === "checkbox") control.checked = Boolean(value);
    else control.value = formatControlValue(control, value);
  });
  if (state.snapshot?.module_id === moduleId) renderSnapshot(state.snapshot, {focus: false});
}

function formatControlValue(control, value) {
  return control.dataset.jsonType === "json" ? JSON.stringify(value, null, 2) : String(value);
}
