"use strict";

const root = document.querySelector("[data-engineering-workbench]");
const moduleId = root?.dataset.moduleId;
const moduleName = root?.dataset.moduleName || moduleId;
const currentCalculationModelVersion = root?.dataset.calculationModelVersion || "";
const form = document.querySelector("#engineering-form");
const fieldsRoot = document.querySelector("#engineering-fields");
const schemaLoading = document.querySelector("#schema-loading");
const formErrors = document.querySelector("#engineering-form-errors");
const resultsPanel = document.querySelector("#engineering-results");
const emptyState = document.querySelector("#engineering-empty");
const loadingState = document.querySelector("#engineering-loading");
const resultContent = document.querySelector("#engineering-result-content");
const resultStatus = document.querySelector("#engineering-result-status");
const calculateButton = document.querySelector("#engineering-calculate");
const loadSampleButton = document.querySelector("#engineering-load-sample");
const clearButton = document.querySelector("#engineering-clear");
const htmlReportLink = document.querySelector("#engineering-html-report");
const pdfReportLink = document.querySelector("#engineering-pdf-report");
const sessionKey = `engineering.${moduleId}.session.v1`;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

let inputSchema = null;
let requiredFields = new Set();
let resultState = "idle";
let resultLabels = {};
let uncheckedLabels = {};
let assumptionLabels = {};
let exampleInput = {};
let pendingSubmission = null;

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
    const data = await fetchJson(`/api/v1/modules/${encodeURIComponent(moduleId)}/schema`, {}, 12000);
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
  control.setAttribute("aria-errormessage", error.id);
  control.setAttribute("aria-describedby", `${help.id} ${error.id}`);
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
      if (schema.exclusiveMinimum !== undefined) {
        control.dataset.exclusiveMinimum = String(schema.exclusiveMinimum);
      }
      if (schema.exclusiveMaximum !== undefined) {
        control.dataset.exclusiveMaximum = String(schema.exclusiveMaximum);
      }
    }
    if (schema.minLength !== undefined) control.minLength = schema.minLength;
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
  validateClientConstraints();
  if (!form.checkValidity()) {
    form.reportValidity();
    showFormError("请完成所有必填字段，并检查浏览器标出的数值范围。");
    return;
  }
  const previousState = resultState;
  let submittedInput = null;
  let logicalSubmission = null;
  setResultState("loading");
  setFormLocked(true);
  try {
    const input = readInput();
    submittedInput = cloneJson(input);
    logicalSubmission = reuseOrCreateSubmission(submittedInput);
    const data = await fetchJson(
      `/api/v1/modules/${encodeURIComponent(moduleId)}/calculations`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": logicalSubmission.idempotencyKey,
        },
        body: JSON.stringify({input}),
      },
      20000,
    );
    if (!sameJson(readInput(), submittedInput) || !responseMatchesRequest(data, submittedInput)) {
      discardMismatchedResponse("返回快照与本次提交不匹配，结果未显示；请重新计算。");
      return;
    }
    renderSnapshot(data);
    saveSessionState(submittedInput, data, submittedInput);
    clearPendingSubmission();
  } catch (error) {
    if (!error?.retryable) clearPendingSubmission();
    if (error?.details?.length) showApiErrors(error);
    else showRequestError(error);
    restoreStateAfterFailedRequest(previousState, submittedInput);
  } finally {
    setFormLocked(false);
  }
});

loadSampleButton?.addEventListener("click", () => {
  clearPendingSubmission();
  invalidateCurrentSnapshot();
  form.reset();
  form.querySelectorAll("[name]").forEach((control) => {
    const sample = Object.hasOwn(exampleInput, control.name)
      ? exampleInput[control.name]
      : control.dataset.sample === undefined
        ? undefined
        : JSON.parse(control.dataset.sample);
    if (sample === undefined || sample === null) {
      if (control.type === "checkbox") control.checked = false;
      else control.value = "";
      return;
    }
    if (control.type === "checkbox") control.checked = Boolean(sample);
    else control.value = formatControlValue(control, sample);
  });
  clearErrors();
  saveSessionState(readInput());
});

clearButton?.addEventListener("click", () => {
  if (!window.confirm("确认清空当前模块参数和本标签页中的最近结果吗？已保存的报告不会删除。")) return;
  clearPendingSubmission();
  form.reset();
  clearErrors();
  window.sessionStorage.removeItem(sessionKey);
  clearReportLinks();
  setResultState("idle");
});

document.querySelector("#engineering-back-to-input")?.addEventListener("click", () => {
  form.scrollIntoView({behavior: scrollBehavior(), block: "start"});
  form.querySelector("input, select, textarea")?.focus({preventScroll: true});
});

function handleFormMutation() {
  clearPendingSubmission();
  clearRetryAction();
  invalidateCurrentSnapshot();
  validateClientConstraints();
  try {
    saveSessionState(readInput());
  } catch {
    // Incomplete numeric input is expected while the user is editing.
  }
}

function clearRetryAction() {
  formErrors.querySelector(".engineering-error-retry")?.remove();
  const context = formErrors.querySelector(".engineering-error-context");
  if (context?.textContent.includes("本次逻辑提交保留了幂等键")) context.remove();
}

form?.addEventListener("input", handleFormMutation);
form?.addEventListener("change", handleFormMutation);

function discardMismatchedResponse(message) {
  clearPendingSubmission();
  invalidateCurrentSnapshot();
  saveSessionState(readInput());
  setResultState("dirty");
  showFormError(message);
}

function restoreStateAfterFailedRequest(previousState, submittedInput) {
  let currentInput;
  try {
    currentInput = readInput();
  } catch {
    invalidateCurrentSnapshot();
    setResultState("dirty");
    return;
  }
  if (submittedInput && !sameJson(currentInput, submittedInput)) {
    invalidateCurrentSnapshot();
    saveSessionState(currentInput);
    setResultState("dirty");
    return;
  }
  if (previousState === "result") {
    setResultState("result");
    return;
  }
  saveSessionState(currentInput);
  setResultState("dirty");
}

function responseMatchesRequest(snapshot, submittedInput) {
  const responseInput = snapshot?.input_original;
  if (!responseInput || typeof responseInput !== "object") return false;
  const requestInput = {};
  Object.entries(inputSchema.properties || {}).forEach(([name, propertySchema]) => {
    if (Object.hasOwn(submittedInput, name)) {
      requestInput[name] = submittedInput[name];
      return;
    }
    requestInput[name] = Object.hasOwn(propertySchema, "default") ? propertySchema.default : null;
  });
  return sameCanonicalJson(responseInput, requestInput);
}

function sameCanonicalJson(left, right) {
  return JSON.stringify(canonicalJson(left)) === JSON.stringify(canonicalJson(right));
}

function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
        .map(([key, entry]) => [key, canonicalJson(entry)]),
    );
  }
  return typeof value === "string" ? value.trim() : value;
}

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
    metaItem("计算时工程状态", releaseStatusLabel(snapshot.release_status)),
    metaItem("模型版本", snapshot.calculation_model_version),
    metaItem("计算 ID", snapshot.calculation_id),
  );
  renderWarnings(snapshot.warnings || []);
  renderResults(snapshot.results || {});
  renderSteps(snapshot.steps || []);
  renderAssumptions(snapshot.assumptions || []);
  renderUnchecked(snapshot.results?.unchecked_items || []);
  htmlReportLink.href = snapshot.links.html_report;
  pdfReportLink.href = snapshot.links.pdf;
  if (focus) {
    resultContent.focus({preventScroll: true});
    resultContent.scrollIntoView({behavior: scrollBehavior(), block: "start"});
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
        (item.formula_ids || []).join("、")].forEach((value, index) => {
        const cell = document.createElement(index === 0 ? "th" : "td");
        if (index === 0) cell.scope = "row";
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
  resultsPanel.setAttribute("aria-busy", String(state === "loading"));
  emptyState.hidden = state !== "idle" && state !== "dirty";
  loadingState.hidden = state !== "loading";
  resultContent.hidden = state !== "result";
  emptyState.textContent = state === "dirty"
    ? "参数已修改。旧快照与报告链接已隐藏，请按当前参数重新计算。"
    : "填写左侧参数后执行计算。结果会显示数值等级、公式编号、警告、来源和未完成专项校核。";
  resultStatus.textContent = state === "loading"
    ? "计算中"
    : state === "result"
      ? "已生成快照"
      : state === "dirty"
        ? "需要重新计算"
        : "等待计算";
}

function invalidateCurrentSnapshot() {
  const persistedState = readSessionState();
  const hadSnapshot = resultState === "result" || resultState === "dirty" || Boolean(persistedState?.snapshot);
  clearReportLinks();
  if (persistedState?.snapshot) {
    saveSessionState(persistedState.input || {});
  }
  if (hadSnapshot) setResultState("dirty");
}

function clearReportLinks() {
  htmlReportLink.removeAttribute("href");
  pdfReportLink.removeAttribute("href");
}

function setFormLocked(locked) {
  Array.from(form.elements).forEach((control) => {
    if (locked && !control.disabled) {
      control.disabled = true;
      control.dataset.requestLock = "true";
    } else if (!locked && control.dataset.requestLock === "true") {
      control.disabled = false;
      delete control.dataset.requestLock;
    }
  });
  calculateButton.textContent = locked ? "正在计算并保存…" : "执行计算与校核";
}

function clearErrors() {
  formErrors.hidden = true;
  formErrors.replaceChildren();
  form.querySelectorAll("[aria-invalid='true']").forEach((control) => control.removeAttribute("aria-invalid"));
  form.querySelectorAll("[name]").forEach((control) => control.setCustomValidity(""));
  form.querySelectorAll(".engineering-field-error").forEach((error) => {
    error.hidden = true;
    error.textContent = "";
  });
}

function showApiErrors(error) {
  const details = error?.details || [];
  showFormError(
    error?.message || "输入未通过校验。",
    details,
    {requestId: error?.requestId, retryable: Boolean(error?.retryable)},
  );
  let firstInvalidControl = null;
  details.forEach((detail) => {
    const fieldParts = String(detail.field || "").split(".").filter(Boolean);
    const fieldName = fieldParts[0] === "input" ? fieldParts[1] : fieldParts[0];
    if (!fieldName) return;
    const control = form.elements[fieldName];
    const fieldError = document.querySelector(`#error-${CSS.escape(fieldName)}`);
    if (control) {
      control.setAttribute("aria-invalid", "true");
      if (!firstInvalidControl) firstInvalidControl = control;
    }
    if (fieldError) {
      const suffix = fieldParts.slice(fieldParts[0] === "input" ? 2 : 1).join(".");
      fieldError.textContent = `${suffix ? `${suffix}：` : ""}${detail.message || "输入无效"}`;
      fieldError.hidden = false;
    }
  });
  firstInvalidControl?.focus();
}

function showFormError(message, details = [], {requestId = "", retryable = false} = {}) {
  formErrors.replaceChildren();
  const summary = document.createElement("strong");
  summary.textContent = message;
  formErrors.append(summary);
  if (details.length) {
    const list = document.createElement("ul");
    details.forEach((detail) => {
      const item = document.createElement("li");
      item.textContent = `${detail.field || "输入"}：${detail.message || "输入无效"}`;
      list.append(item);
    });
    formErrors.append(list);
  }
  if (requestId || retryable) {
    const context = document.createElement("p");
    context.className = "engineering-error-context";
    if (retryable) {
      context.append("当前页面未收到可用的新快照。本次逻辑提交保留了幂等键，可安全重试；请保留请求 ID 以便核查。");
    }
    if (requestId) {
      if (retryable) context.append(" ");
      context.append("请求 ID：");
      const code = document.createElement("code");
      code.textContent = requestId;
      context.append(code);
    }
    formErrors.append(context);
  }
  if (retryable) {
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "button button--secondary engineering-error-retry";
    retry.textContent = "安全重试本次计算";
    retry.addEventListener("click", () => {
      if (!pendingSubmission) return;
      retry.disabled = true;
      form.requestSubmit();
    });
    formErrors.append(retry);
  }
  formErrors.tabIndex = -1;
  formErrors.hidden = false;
  if (!details.length) formErrors.focus();
}

function showRequestError(error) {
  showFormError(
    error instanceof Error ? error.message : "无法连接计算服务。",
    [],
    {requestId: error?.requestId, retryable: Boolean(error?.retryable)},
  );
}

function showFatal(message) {
  schemaLoading.replaceChildren();
  const text = document.createElement("p");
  text.textContent = message;
  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "button button--secondary";
  retry.textContent = "重新加载";
  retry.addEventListener("click", () => window.location.reload());
  schemaLoading.append(text, retry);
  schemaLoading.classList.add("engineering-placeholder--error");
}

function validateClientConstraints() {
  form.querySelectorAll("[name]").forEach((control) => {
    control.setCustomValidity("");
    if (control.type !== "number" || control.value === "") return;
    const value = Number(control.value);
    const exclusiveMinimum = Number(control.dataset.exclusiveMinimum);
    const exclusiveMaximum = Number(control.dataset.exclusiveMaximum);
    if (control.dataset.exclusiveMinimum !== undefined && value <= exclusiveMinimum) {
      control.setCustomValidity(`必须大于 ${exclusiveMinimum}`);
    } else if (control.dataset.exclusiveMaximum !== undefined && value >= exclusiveMaximum) {
      control.setCustomValidity(`必须小于 ${exclusiveMaximum}`);
    }
  });
}

function releaseStatusLabel(value) {
  return {
    internal_testing: "内部测试（internal_testing）",
    engineering_review: "工程审核中（engineering_review）",
    released: "工程已放行（released）",
    legacy_unknown: "未记录（按内部测试边界处理）",
  }[value] || String(value || "未记录");
}

function scrollBehavior() {
  return reduceMotion.matches ? "auto" : "smooth";
}

async function fetchJson(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  const clientRequestId = createOpaqueId("request");
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      ...options,
      headers: {...(options.headers || {}), "X-Request-ID": clientRequestId},
      signal: controller.signal,
    });
    const headerRequestId = response.headers.get("x-request-id") || clientRequestId;
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.toLowerCase().includes("application/json")) {
      throw requestError("服务返回了非 JSON 响应，请稍后重试。", {
        requestId: headerRequestId,
        retryable: true,
        status: response.status,
      });
    }
    const responseText = await response.text();
    if (!responseText.trim()) {
      throw requestError("服务返回了空响应，请稍后重试。", {
        requestId: headerRequestId,
        retryable: true,
        status: response.status,
      });
    }
    let data;
    try {
      data = JSON.parse(responseText);
    } catch {
      throw requestError("服务返回了无效 JSON，请稍后重试。", {
        requestId: headerRequestId,
        retryable: true,
        status: response.status,
      });
    }
    if (!response.ok) {
      const apiError = data?.error || {};
      throw requestError(apiError.message || `请求失败（HTTP ${response.status}）。`, {
        details: Array.isArray(apiError.details)
          ? apiError.details.filter((detail) => detail && typeof detail === "object")
          : [],
        requestId: apiError.request_id || headerRequestId,
        retryable: isRetryableHttpStatus(response.status),
        status: response.status,
      });
    }
    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw requestError("请求超时，请检查网络或服务状态后安全重试。", {
        requestId: clientRequestId,
        retryable: true,
      });
    }
    if (error?.isRequestError) throw error;
    throw requestError("无法连接计算服务，请确认应用仍在运行。", {
      requestId: clientRequestId,
      retryable: true,
    });
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function requestError(message, {details = [], requestId = "", retryable = false, status = null} = {}) {
  const error = new Error(message);
  error.details = details;
  error.requestId = requestId;
  error.retryable = retryable;
  error.status = status;
  error.isRequestError = true;
  return error;
}

function isRetryableHttpStatus(status) {
  return status === 408 || status === 425 || status === 429 || status >= 500;
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

function saveSessionState(input, snapshot = null, snapshotInput = null) {
  try {
    window.sessionStorage.setItem(sessionKey, JSON.stringify({
      version: 3,
      calculationModelVersion: currentCalculationModelVersion,
      input,
      snapshot,
      snapshotInput,
    }));
  } catch (error) {
    console.warn("无法保存当前模块会话。", error);
  }
}

function readSessionState() {
  try {
    const raw = window.sessionStorage.getItem(sessionKey);
    if (!raw) return null;
    const state = JSON.parse(raw);
    return [2, 3].includes(state?.version) && state.input && typeof state.input === "object" ? state : null;
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
  const versionMatches = state.version === 3
    && state.calculationModelVersion === currentCalculationModelVersion
    && state.snapshot?.calculation_model_version === currentCalculationModelVersion;
  if (versionMatches && state.snapshot?.module_id === moduleId && sameJson(state.input, state.snapshotInput)) {
    renderSnapshot(state.snapshot, {focus: false});
  } else {
    clearReportLinks();
    if (state.snapshot || state.version !== 3 || state.calculationModelVersion !== currentCalculationModelVersion) {
      saveSessionState(state.input || {});
    }
    setResultState("dirty");
  }
}

function formatControlValue(control, value) {
  return control.dataset.jsonType === "json" ? JSON.stringify(value, null, 2) : String(value);
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function sameJson(left, right) {
  return Boolean(left && right) && JSON.stringify(left) === JSON.stringify(right);
}

function reuseOrCreateSubmission(input) {
  if (pendingSubmission && sameCanonicalJson(pendingSubmission.input, input)) return pendingSubmission;
  pendingSubmission = {
    idempotencyKey: createOpaqueId(moduleId || "engineering"),
    input: canonicalJson(input),
  };
  return pendingSubmission;
}

function clearPendingSubmission() {
  pendingSubmission = null;
}

function createOpaqueId(prefix) {
  if (typeof window.crypto?.randomUUID === "function") return `${prefix}-${window.crypto.randomUUID()}`;
  if (typeof window.crypto?.getRandomValues === "function") {
    const bytes = window.crypto.getRandomValues(new Uint8Array(16));
    return `${prefix}-${Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("")}`;
  }
  throw new Error("当前浏览器无法生成安全请求标识，请升级浏览器后重试。");
}
