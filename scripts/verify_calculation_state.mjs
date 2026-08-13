import {spawn} from "node:child_process";
import {existsSync} from "node:fs";
import {mkdir, mkdtemp, rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {createServer} from "node:net";

const arguments_ = process.argv.slice(2);
const externalUrl = arguments_.find((value) => !value.startsWith("--"));
if (externalUrl && !arguments_.includes("--allow-persistent-test-data")) {
  throw new Error("External services require --allow-persistent-test-data because this check creates calculation snapshots");
}

const runRoot = await mkdtemp(join(tmpdir(), "design-agent-browser-"));
const profilePath = join(runRoot, "chrome-profile");
let appServer;
let chrome;
let client;
try {
  let baseUrl = externalUrl?.replace(/\/$/, "");
  if (!baseUrl) {
    const appPort = await availablePort();
    const reportsPath = join(runRoot, "reports");
    await mkdir(reportsPath, {recursive: true});
    appServer = startIsolatedApp(appPort, join(runRoot, "browser.sqlite3"), reportsPath);
    baseUrl = `http://127.0.0.1:${appPort}`;
    await waitForApp(baseUrl, appServer);
  }

  const chromePath = findChrome();
  const debugPort = await availablePort();
  chrome = spawn(
    chromePath,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${profilePath}`,
      "about:blank",
    ],
    {stdio: "ignore", windowsHide: true},
  );
  await waitForChrome(debugPort);
  const target = await createTarget(debugPort, `${baseUrl}/modules/winch_drum?sample=golden`);
  client = await connectCdp(target.webSocketDebuggerUrl);
  await client.send("Page.enable");
  await client.send("Runtime.enable");

  await verifyWinchWorkbench(client, baseUrl);
  await verifyWinchMobileSafety(client, baseUrl);
  await navigate(client, `${baseUrl}/modules/transmission_check`);
  await verifyGenericWorkbench(client, baseUrl);
  process.stdout.write("CALCULATION_STATE_BROWSER_CHECK=PASS\n");
} finally {
  client?.close();
  await stopChild(chrome);
  await stopChild(appServer);
  await rm(runRoot, {recursive: true, force: true, maxRetries: 5, retryDelay: 200});
}

async function verifyWinchWorkbench(cdp, baseUrl) {
  await waitFor(cdp, 'document.readyState === "complete" && document.querySelector("#winch-form").elements.rated_line_pull_kn.value === "100"');
  await cdp.evaluate('document.querySelector("#winch-form").requestSubmit(); true');
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "result"');

  await cdp.evaluate(`(() => {
    const field = document.querySelector("#winch-form").elements.rated_line_pull_kn;
    field.value = "101";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    return true;
  })()`);
  await assertPage(
    cdp,
    `document.querySelector("#results").dataset.state === "dirty"
      && document.querySelector("#result-content").hidden
      && !document.querySelector("#report-link").hasAttribute("href")
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch input mutation did not invalidate the saved snapshot",
  );

  await navigate(cdp, `${baseUrl}/modules/winch_drum`);
  await waitFor(cdp, 'document.readyState === "complete" && document.querySelector("#winch-form").elements.rated_line_pull_kn.value === "101"');
  await assertPage(
    cdp,
    'document.querySelector("#results").dataset.state !== "result" && document.querySelector("#result-content").hidden',
    "winch restored a stale result beside edited inputs",
  );

  await cdp.evaluate(`(() => {
    const form = document.querySelector("#winch-form");
    Object.entries({
      minimum_dd_ratio: "21",
      approved_core_ratio: "22",
      actual_groove_pitch_mm: "25",
      actual_usable_groove_count: "12",
      termination_allowance_m: "5",
      brake_installation_shaft: "other",
      transmission_backdrive_type: "worm",
      motor_duty_type: "S5",
      duty_cycle_percent: "50",
      starts_per_hour: "999",
      supply_voltage: "440",
      supply_frequency: "60",
    }).forEach(([name, value]) => { form.elements[name].value = value; });
    Object.entries({
      source_minimum_dd_ratio: "user_input",
      source_motor_duty_type: "user_input",
      source_duty_cycle_percent: "user_input",
      source_starts_per_hour: "user_input",
      source_supply_voltage: "user_input",
      source_supply_frequency: "user_input",
    }).forEach(([name, value]) => { form.elements[name].value = value; });
    document.querySelector("#load-golden-sample").click();
    return true;
  })()`);
  await assertPage(
    cdp,
    `(() => {
      const fields = document.querySelector("#winch-form").elements;
      return fields.minimum_dd_ratio.value === "20"
        && fields.approved_core_ratio.value === ""
        && fields.actual_groove_pitch_mm.value === ""
        && fields.actual_usable_groove_count.value === ""
        && fields.termination_allowance_m.value === "0"
        && fields.brake_installation_shaft.value === "drum_or_low_speed"
        && fields.transmission_backdrive_type.value === "reversible"
        && fields.motor_duty_type.value === "S3"
        && fields.duty_cycle_percent.value === "40"
        && fields.starts_per_hour.value === "60"
        && fields.supply_voltage.value === "380"
        && fields.supply_frequency.value === "50"
        && fields.source_minimum_dd_ratio.value === "project_default"
        && fields.source_motor_duty_type.value === "project_default";
    })()`,
    "winch golden sample inherited fields from the previous form",
  );
  await cdp.evaluate('document.querySelector("#winch-form").requestSubmit(); true');
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "result"');

  await cdp.evaluate(`(() => {
    window.__realFetch = window.fetch;
    window.__calculationGate = new Promise((resolve) => { window.__releaseCalculation = resolve; });
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? window.__calculationGate.then(() => window.__realFetch(...args))
      : window.__realFetch(...args);
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "loading"');
  await assertPage(
    cdp,
    'Array.from(document.querySelector("#winch-form").elements).every((control) => control.disabled)',
    "winch controls were not locked while the request was in flight",
  );
  await cdp.evaluate(`(() => {
    const field = document.querySelector("#winch-form").elements.rated_line_pull_kn;
    field.value = "102";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    window.__releaseCalculation();
    return true;
  })()`);
  await waitFor(
    cdp,
    'document.querySelector("#results").dataset.state !== "loading" && Array.from(document.querySelector("#winch-form").elements).every((control) => !control.disabled)',
  );
  await assertPage(
    cdp,
    `document.querySelector("#results").dataset.state === "dirty"
      && document.querySelector("#result-content").hidden
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch rendered a response whose submitted input no longer matched the form",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "result"');
  await cdp.evaluate(`(async () => {
    const wrongPayload = buildPayload();
    wrongPayload.input.approved_core_ratio = 22;
    wrongPayload.assumption_sources.approved_core_ratio = "user_input";
    const wrongResponse = await window.fetch("/api/v1/modules/winch_drum/calculations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "fixture-winch-" + crypto.randomUUID(),
      },
      body: JSON.stringify(wrongPayload),
    });
    if (!wrongResponse.ok) throw new Error("failed to create mismatched winch fixture");
    const wrongSnapshot = await wrongResponse.json();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response(JSON.stringify(wrongSnapshot), {
          status: 201,
          headers: {"Content-Type": "application/json"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(
    cdp,
    'document.querySelector("#results").dataset.state !== "loading" && Array.from(document.querySelector("#winch-form").elements).every((control) => !control.disabled)',
  );
  await assertPage(
    cdp,
    `document.querySelector("#results").dataset.state === "dirty"
      && document.querySelector("#result-content").hidden
      && !document.querySelector("#report-link").hasAttribute("href")
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch rendered a successful snapshot from another request",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await navigate(cdp, `${baseUrl}/modules/winch_drum`);
  await assertPage(
    cdp,
    'document.querySelector("#results").dataset.state !== "result" && document.querySelector("#result-content").hidden',
    "winch restored a mismatched successful snapshot",
  );
  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "result"');
  await cdp.evaluate(`(() => {
    window.__realFetch = window.fetch;
    window.__calculationFailureGate = new Promise((resolve) => { window.__releaseCalculationFailure = resolve; });
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? window.__calculationFailureGate.then(() => Promise.reject(new TypeError("simulated network failure")))
      : window.__realFetch(...args);
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "loading"');
  await cdp.evaluate(`(() => {
    const field = document.querySelector("#winch-form").elements.rated_line_pull_kn;
    field.value = "104";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    window.__releaseCalculationFailure();
    return true;
  })()`);
  await waitFor(
    cdp,
    'document.querySelector("#results").dataset.state !== "loading" && Array.from(document.querySelector("#winch-form").elements).every((control) => !control.disabled)',
  );
  await assertPage(
    cdp,
    `document.querySelector("#results").dataset.state === "dirty"
      && document.querySelector("#result-content").hidden
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch restored an old result after a failed request and defensive input mutation",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response("<!doctype html><title>proxy error</title>", {
          status: 502,
          headers: {"Content-Type": "text/html", "X-Request-ID": "html-response-fixture"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state !== "loading"');
  await assertPage(
    cdp,
    `document.querySelector("#form-errors").textContent.includes("非 JSON 响应")
      && document.querySelector("#form-errors").textContent.includes("html-response-fixture")
      && Boolean(document.querySelector("#form-errors .error-retry"))
      && document.querySelector("#results").dataset.state === "dirty"
      && Array.from(document.querySelector("#winch-form").elements).every((control) => !control.disabled)
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch did not expose a retryable non-JSON response with its request ID",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response("", {
          status: 200,
          headers: {"Content-Type": "application/json", "X-Request-ID": "empty-response-fixture"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state !== "loading"');
  await assertPage(
    cdp,
    `document.querySelector("#form-errors").textContent.includes("空响应")
      && document.querySelector("#form-errors").textContent.includes("empty-response-fixture")
      && Boolean(document.querySelector("#form-errors .error-retry"))
      && document.querySelector("#results").dataset.state === "dirty"
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch did not reject and identify an empty JSON response",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response(JSON.stringify({
          error: {
            code: "SERVICE_UNAVAILABLE",
            message: "fixture service unavailable",
            request_id: "json-error-fixture",
            details: [],
          },
        }), {
          status: 503,
          headers: {"Content-Type": "application/json", "X-Request-ID": "json-header-fixture"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state !== "loading"');
  await assertPage(
    cdp,
    `document.querySelector("#form-errors").textContent.includes("fixture service unavailable")
      && document.querySelector("#form-errors").textContent.includes("json-error-fixture")
      && !document.querySelector("#form-errors").textContent.includes("json-header-fixture")
      && Boolean(document.querySelector("#form-errors .error-retry"))
      && document.querySelector("#results").dataset.state === "dirty"
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch did not parse the retryable JSON HTTP error or prefer its body request ID",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    window.__realFetch = window.fetch;
    window.__realSetTimeout = window.setTimeout;
    window.setTimeout = (handler, delay, ...args) => window.__realSetTimeout(handler, Math.min(delay, 40), ...args);
    window.fetch = (url, options = {}) => String(url).includes("/calculations")
      ? new Promise((resolve, reject) => {
          if (options.signal?.aborted) {
            reject(new DOMException("aborted", "AbortError"));
            return;
          }
          options.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("aborted", "AbortError")),
            {once: true},
          );
        })
      : window.__realFetch(url, options);
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state !== "loading"');
  await assertPage(
    cdp,
    `document.querySelector("#form-errors").textContent.includes("请求超时")
      && document.querySelector("#form-errors").textContent.includes("本次逻辑提交保留了幂等键")
      && document.querySelector("#form-errors").textContent.includes("可安全重试")
      && document.querySelector("#form-errors .error-context code")?.textContent.length > 0
      && document.querySelector("#form-errors .error-retry")?.textContent === "安全重试本次计算"
      && document.querySelector("#results").dataset.state === "dirty"
      && Array.from(document.querySelector("#winch-form").elements).every((control) => !control.disabled)
      && JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1")).snapshot === null`,
    "winch timeout did not abort, unlock, retain dirty state, and offer a traceable retry",
  );
  await cdp.evaluate(`(() => {
    window.fetch = window.__realFetch;
    window.setTimeout = window.__realSetTimeout;
    return true;
  })()`);
  await cdp.evaluate(`(() => {
    const field = document.querySelector("#winch-form").elements.rated_line_pull_kn;
    field.value = "103";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    return true;
  })()`);
  await assertPage(
    cdp,
    `!document.querySelector("#form-errors .error-retry")
      && !document.querySelector("#form-errors").textContent.includes("本次逻辑提交保留了幂等键")`,
    "winch retained a stale safe-retry action after the form changed",
  );

  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "result"');
  await cdp.evaluate(`(() => {
    const key = "winch_drum.calculator.session.v1";
    const state = JSON.parse(sessionStorage.getItem(key));
    state.version = 2;
    delete state.calculationModelVersion;
    sessionStorage.setItem(key, JSON.stringify(state));
    return true;
  })()`);
  await navigate(cdp, `${baseUrl}/modules/winch_drum`);
  await assertPage(
    cdp,
    `(() => {
      const state = JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1"));
      return document.querySelector("#results").dataset.state === "dirty"
        && document.querySelector("#result-content").hidden
        && !document.querySelector("#report-link").hasAttribute("href")
        && state.version === 3
        && state.calculationModelVersion === document.body.dataset.calculationModelVersion
        && state.snapshot === null;
    })()`,
    "winch restored a v2 snapshot instead of retaining only its inputs as dirty state",
  );

  await cdp.evaluate(`(() => {
    document.querySelector("#load-golden-sample").click();
    window.__realFetch = window.fetch;
    window.__idempotencyAudit = {keys: [], requestIds: [], calculationIds: [], statuses: [], replayed: []};
    window.fetch = async (url, options = {}) => {
      if (!String(url).includes("/calculations")) return window.__realFetch(url, options);
      const headers = new Headers(options.headers || {});
      window.__idempotencyAudit.keys.push(headers.get("Idempotency-Key"));
      window.__idempotencyAudit.requestIds.push(headers.get("X-Request-ID"));
      const response = await window.__realFetch(url, options);
      const data = await response.clone().json();
      window.__idempotencyAudit.calculationIds.push(data.calculation_id || null);
      window.__idempotencyAudit.statuses.push(response.status);
      window.__idempotencyAudit.replayed.push(response.headers.get("Idempotency-Replayed"));
      if (window.__idempotencyAudit.keys.length === 1) {
        throw new TypeError("simulated response loss after persistence");
      }
      return response;
    };
    document.querySelector("#winch-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#form-errors .error-retry")?.textContent === "安全重试本次计算"');
  await cdp.evaluate('document.querySelector("#form-errors .error-retry").click(); true');
  await waitFor(cdp, 'document.querySelector("#results").dataset.state === "result"');
  await assertPage(
    cdp,
    `(() => {
      const audit = window.__idempotencyAudit;
      const state = JSON.parse(sessionStorage.getItem("winch_drum.calculator.session.v1"));
      return audit.keys.length === 2
        && audit.keys[0]?.length > 0
        && audit.keys[0] === audit.keys[1]
        && audit.requestIds[0]?.length > 0
        && audit.requestIds[1]?.length > 0
        && audit.requestIds[0] !== audit.requestIds[1]
        && audit.statuses.every((status) => status === 201)
        && audit.calculationIds[0]?.length > 0
        && audit.calculationIds[0] === audit.calculationIds[1]
        && audit.replayed[1] === "true"
        && state.snapshot?.calculation_id === audit.calculationIds[1];
    })()`,
    "winch safe retry did not reuse the logical idempotency key and persisted calculation",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');
}

async function verifyWinchMobileSafety(cdp, baseUrl) {
  for (const width of [390, 430]) {
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height: 844,
      deviceScaleFactor: 1,
      mobile: true,
    });
    await navigate(cdp, `${baseUrl}/modules/winch_drum`);
    await assertPage(
      cdp,
      `(() => {
        const scopeNote = document.querySelector(".scope-note");
        const headerStatus = document.querySelector(".header-status");
        const statusRect = headerStatus.getBoundingClientRect();
        return getComputedStyle(scopeNote).display !== "none"
          && scopeNote.getBoundingClientRect().height > 0
          && getComputedStyle(headerStatus).display !== "none"
          && statusRect.width > 0
          && statusRect.left >= 0
          && statusRect.right <= window.innerWidth
          && headerStatus.querySelector(".header-status__label").textContent.trim().length > 0
          && getComputedStyle(headerStatus.querySelector(".header-status__model")).display === "none";
      })()`,
      `winch safety boundary or compact release status was not visible at ${width}px`,
    );
  }
  await cdp.send("Emulation.clearDeviceMetricsOverride");
}

async function verifyGenericWorkbench(cdp, baseUrl) {
  await waitFor(cdp, 'document.readyState === "complete" && !document.querySelector("#engineering-form").hidden');
  await cdp.evaluate('document.querySelector("#engineering-load-sample").click(); true');
  await cdp.evaluate('document.querySelector("#engineering-form").requestSubmit(); true');
  await waitFor(cdp, 'document.querySelector("#engineering-results").dataset.state === "result"');

  await cdp.evaluate(`(() => {
    const field = document.querySelector("#engineering-form").elements.basis_reference;
    field.value = field.value + " - edited";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    return true;
  })()`);
  await assertPage(
    cdp,
    `document.querySelector("#engineering-results").dataset.state === "dirty"
      && document.querySelector("#engineering-result-content").hidden
      && !document.querySelector("#engineering-html-report").hasAttribute("href")
      && !document.querySelector("#engineering-pdf-report").hasAttribute("href")
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic workbench input mutation did not invalidate the saved snapshot",
  );

  await navigate(cdp, `${baseUrl}/modules/transmission_check`);
  await waitFor(
    cdp,
    `document.readyState === "complete"
      && !document.querySelector("#engineering-form").hidden
      && document.querySelector("#engineering-form").elements.basis_reference.value.endsWith(" - edited")`,
  );
  await assertPage(
    cdp,
    `document.querySelector("#engineering-results").dataset.state !== "result"
      && document.querySelector("#engineering-result-content").hidden`,
    "generic workbench restored a stale result beside edited inputs",
  );

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    window.__realFetch = window.fetch;
    window.__calculationGate = new Promise((resolve) => { window.__releaseCalculation = resolve; });
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? window.__calculationGate.then(() => window.__realFetch(...args))
      : window.__realFetch(...args);
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-results").dataset.state === "loading"');
  await assertPage(
    cdp,
    'Array.from(document.querySelector("#engineering-form").elements).every((control) => control.disabled)',
    "generic workbench controls were not locked while the request was in flight",
  );
  await cdp.evaluate(`(() => {
    const field = document.querySelector("#engineering-form").elements.basis_reference;
    field.value = field.value + " - race";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    window.__releaseCalculation();
    return true;
  })()`);
  await waitFor(
    cdp,
    'document.querySelector("#engineering-results").dataset.state !== "loading" && Array.from(document.querySelector("#engineering-form").elements).every((control) => !control.disabled)',
  );
  await assertPage(
    cdp,
    `document.querySelector("#engineering-results").dataset.state === "dirty"
      && document.querySelector("#engineering-result-content").hidden
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic workbench rendered a response whose submitted input no longer matched the form",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-results").dataset.state === "result"');
  await cdp.evaluate(`(async () => {
    const wrongInput = readInput();
    wrongInput.candidate_rated_output_torque_nm = 1200;
    const wrongResponse = await window.fetch("/api/v1/modules/transmission_check/calculations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": "fixture-generic-" + crypto.randomUUID(),
      },
      body: JSON.stringify({input: wrongInput}),
    });
    if (!wrongResponse.ok) throw new Error("failed to create mismatched generic fixture");
    const wrongSnapshot = await wrongResponse.json();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response(JSON.stringify(wrongSnapshot), {
          status: 201,
          headers: {"Content-Type": "application/json"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(
    cdp,
    'document.querySelector("#engineering-results").dataset.state !== "loading" && Array.from(document.querySelector("#engineering-form").elements).every((control) => !control.disabled)',
  );
  await assertPage(
    cdp,
    `document.querySelector("#engineering-results").dataset.state === "dirty"
      && document.querySelector("#engineering-result-content").hidden
      && !document.querySelector("#engineering-html-report").hasAttribute("href")
      && !document.querySelector("#engineering-pdf-report").hasAttribute("href")
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic workbench rendered a successful snapshot from another request",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await navigate(cdp, `${baseUrl}/modules/transmission_check`);
  await waitFor(cdp, 'document.readyState === "complete" && !document.querySelector("#engineering-form").hidden');
  await assertPage(
    cdp,
    'document.querySelector("#engineering-results").dataset.state !== "result" && document.querySelector("#engineering-result-content").hidden',
    "generic workbench restored a mismatched successful snapshot",
  );
  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-results").dataset.state === "result"');
  await cdp.evaluate(`(() => {
    window.__realFetch = window.fetch;
    window.__calculationFailureGate = new Promise((resolve) => { window.__releaseCalculationFailure = resolve; });
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? window.__calculationFailureGate.then(() => Promise.reject(new TypeError("simulated network failure")))
      : window.__realFetch(...args);
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-results").dataset.state === "loading"');
  await cdp.evaluate(`(() => {
    const field = document.querySelector("#engineering-form").elements.basis_reference;
    field.value = field.value + " - failed race";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    window.__releaseCalculationFailure();
    return true;
  })()`);
  await waitFor(
    cdp,
    'document.querySelector("#engineering-results").dataset.state !== "loading" && Array.from(document.querySelector("#engineering-form").elements).every((control) => !control.disabled)',
  );
  await assertPage(
    cdp,
    `document.querySelector("#engineering-results").dataset.state === "dirty"
      && document.querySelector("#engineering-result-content").hidden
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic workbench restored an old result after a failed request and defensive input mutation",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-results").dataset.state === "result"');
  await cdp.evaluate(`(() => {
    const key = "engineering.transmission_check.session.v1";
    const state = JSON.parse(sessionStorage.getItem(key));
    state.calculationModelVersion = "legacy-model-version";
    sessionStorage.setItem(key, JSON.stringify(state));
    return true;
  })()`);
  await navigate(cdp, `${baseUrl}/modules/transmission_check`);
  await waitFor(cdp, 'document.readyState === "complete" && !document.querySelector("#engineering-form").hidden');
  await assertPage(
    cdp,
    `(() => {
      const state = JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1"));
      return document.querySelector("#engineering-form").elements.basis_reference.value === state.input.basis_reference
        && document.querySelector("#engineering-results").dataset.state === "dirty"
        && document.querySelector("#engineering-result-content").hidden
        && !document.querySelector("#engineering-html-report").hasAttribute("href")
        && !document.querySelector("#engineering-pdf-report").hasAttribute("href")
        && state.version === 3
        && state.calculationModelVersion === document.body.dataset.calculationModelVersion
        && state.snapshot === null;
    })()`,
    "generic workbench restored a snapshot from another calculation model version",
  );

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    window.__realFetch = window.fetch;
    window.__idempotencyAudit = {keys: [], requestIds: [], calculationIds: [], statuses: [], replayed: []};
    window.fetch = async (url, options = {}) => {
      if (!String(url).includes("/calculations")) return window.__realFetch(url, options);
      const headers = new Headers(options.headers || {});
      window.__idempotencyAudit.keys.push(headers.get("Idempotency-Key"));
      window.__idempotencyAudit.requestIds.push(headers.get("X-Request-ID"));
      const response = await window.__realFetch(url, options);
      const data = await response.clone().json();
      window.__idempotencyAudit.calculationIds.push(data.calculation_id || null);
      window.__idempotencyAudit.statuses.push(response.status);
      window.__idempotencyAudit.replayed.push(response.headers.get("Idempotency-Replayed"));
      if (window.__idempotencyAudit.keys.length === 1) {
        throw new TypeError("simulated response loss after persistence");
      }
      return response;
    };
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-form-errors .engineering-error-retry")?.textContent === "安全重试本次计算"');
  await cdp.evaluate('document.querySelector("#engineering-form-errors .engineering-error-retry").click(); true');
  await waitFor(cdp, 'document.querySelector("#engineering-results").dataset.state === "result"');
  await assertPage(
    cdp,
    `(() => {
      const audit = window.__idempotencyAudit;
      const state = JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1"));
      return audit.keys.length === 2
        && audit.keys[0]?.length > 0
        && audit.keys[0] === audit.keys[1]
        && audit.requestIds[0]?.length > 0
        && audit.requestIds[1]?.length > 0
        && audit.requestIds[0] !== audit.requestIds[1]
        && audit.statuses.every((status) => status === 201)
        && audit.calculationIds[0]?.length > 0
        && audit.calculationIds[0] === audit.calculationIds[1]
        && audit.replayed[1] === "true"
        && state.snapshot?.calculation_id === audit.calculationIds[1];
    })()`,
    "generic safe retry did not reuse the logical idempotency key and persisted calculation",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response("<!doctype html><title>proxy error</title>", {
          status: 502,
          headers: {"Content-Type": "text/html", "X-Request-ID": "generic-html-fixture"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-form-errors").textContent.includes("generic-html-fixture")');
  await assertPage(
    cdp,
    `document.querySelector("#engineering-form-errors").textContent.includes("非 JSON 响应")
      && document.querySelector("#engineering-form-errors").textContent.includes("generic-html-fixture")
      && document.querySelector("#engineering-form-errors .engineering-error-retry")?.textContent === "安全重试本次计算"
      && document.querySelector("#engineering-results").dataset.state === "dirty"
      && Array.from(document.querySelector("#engineering-form").elements).every((control) => !control.disabled)
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic workbench did not expose and unlock after a retryable non-JSON response",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response("", {
          status: 200,
          headers: {"Content-Type": "application/json", "X-Request-ID": "generic-empty-fixture"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-form-errors").textContent.includes("generic-empty-fixture")');
  await assertPage(
    cdp,
    `document.querySelector("#engineering-form-errors").textContent.includes("空响应")
      && document.querySelector("#engineering-form-errors").textContent.includes("generic-empty-fixture")
      && Boolean(document.querySelector("#engineering-form-errors .engineering-error-retry"))
      && document.querySelector("#engineering-results").dataset.state === "dirty"
      && Array.from(document.querySelector("#engineering-form").elements).every((control) => !control.disabled)
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic workbench did not reject and identify an empty JSON response",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    window.__realFetch = window.fetch;
    window.fetch = (...args) => String(args[0]).includes("/calculations")
      ? Promise.resolve(new Response(JSON.stringify({
          error: {
            code: "SERVICE_UNAVAILABLE",
            message: "generic fixture service unavailable",
            request_id: "generic-json-error-fixture",
            details: [],
          },
        }), {
          status: 503,
          headers: {"Content-Type": "application/json", "X-Request-ID": "generic-json-header-fixture"},
        }))
      : window.__realFetch(...args);
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-form-errors").textContent.includes("generic-json-error-fixture")');
  await assertPage(
    cdp,
    `document.querySelector("#engineering-form-errors").textContent.includes("generic fixture service unavailable")
      && document.querySelector("#engineering-form-errors").textContent.includes("generic-json-error-fixture")
      && !document.querySelector("#engineering-form-errors").textContent.includes("generic-json-header-fixture")
      && Boolean(document.querySelector("#engineering-form-errors .engineering-error-retry"))
      && document.querySelector("#engineering-results").dataset.state === "dirty"
      && Array.from(document.querySelector("#engineering-form").elements).every((control) => !control.disabled)
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic workbench did not parse a retryable JSON HTTP error with its request ID",
  );
  await cdp.evaluate('window.fetch = window.__realFetch; true');

  await cdp.evaluate(`(() => {
    document.querySelector("#engineering-load-sample").click();
    window.__realFetch = window.fetch;
    window.__realSetTimeout = window.setTimeout;
    window.setTimeout = (handler, delay, ...args) => window.__realSetTimeout(handler, Math.min(delay, 40), ...args);
    window.fetch = (url, options = {}) => String(url).includes("/calculations")
      ? new Promise((resolve, reject) => {
          if (options.signal?.aborted) {
            reject(new DOMException("aborted", "AbortError"));
            return;
          }
          options.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("aborted", "AbortError")),
            {once: true},
          );
        })
      : window.__realFetch(url, options);
    document.querySelector("#engineering-form").requestSubmit();
    return true;
  })()`);
  await waitFor(cdp, 'document.querySelector("#engineering-form-errors").textContent.includes("请求超时")');
  await assertPage(
    cdp,
    `document.querySelector("#engineering-form-errors").textContent.includes("请求超时")
      && document.querySelector("#engineering-form-errors").textContent.includes("本次逻辑提交保留了幂等键")
      && document.querySelector("#engineering-form-errors .engineering-error-context code")?.textContent.length > 0
      && document.querySelector("#engineering-form-errors .engineering-error-retry")?.textContent === "安全重试本次计算"
      && document.querySelector("#engineering-results").dataset.state === "dirty"
      && Array.from(document.querySelector("#engineering-form").elements).every((control) => !control.disabled)
      && JSON.parse(sessionStorage.getItem("engineering.transmission_check.session.v1")).snapshot === null`,
    "generic timeout did not abort, unlock, retain dirty state, and offer a traceable safe retry",
  );
  await cdp.evaluate(`(() => {
    window.fetch = window.__realFetch;
    window.setTimeout = window.__realSetTimeout;
    return true;
  })()`);
  await cdp.evaluate(`(() => {
    const field = document.querySelector("#engineering-form").elements.basis_reference;
    field.value = field.value + " changed";
    field.dispatchEvent(new Event("input", {bubbles: true}));
    return true;
  })()`);
  await assertPage(
    cdp,
    `!document.querySelector("#engineering-form-errors .engineering-error-retry")
      && !document.querySelector("#engineering-form-errors").textContent.includes("本次逻辑提交保留了幂等键")`,
    "generic workbench retained a stale safe-retry action after the form changed",
  );
}

async function navigate(cdp, url) {
  await cdp.send("Page.navigate", {url});
  await waitFor(cdp, 'document.readyState === "complete"');
}

async function waitFor(cdp, expression, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if (await cdp.evaluate(expression)) return;
    } catch {
      // Navigation can briefly invalidate the JavaScript execution context.
    }
    await delay(50);
  }
  throw new Error(`Timed out waiting for browser condition: ${expression}`);
}

async function assertPage(cdp, expression, message) {
  if (!(await cdp.evaluate(expression))) throw new Error(message);
}

async function createTarget(port, url) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`, {method: "PUT"});
  if (!response.ok) throw new Error(`Chrome target creation failed: ${response.status}`);
  return response.json();
}

async function connectCdp(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, {once: true});
    socket.addEventListener("error", reject, {once: true});
  });
  let nextId = 1;
  const pending = new Map();
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(String(event.data));
    if (!message.id || !pending.has(message.id)) return;
    const {resolve, reject} = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(message.error.message));
    else resolve(message.result);
  });
  return {
    close: () => socket.close(),
    send(method, params = {}) {
      const id = nextId++;
      socket.send(JSON.stringify({id, method, params}));
      return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
    },
    async evaluate(expression) {
      const response = await this.send("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (response.exceptionDetails) throw new Error(response.exceptionDetails.text || "Browser evaluation failed");
      return response.result.value;
    },
  };
}

function findPython() {
  if (process.env.DESIGN_AGENT_PYTHON) return process.env.DESIGN_AGENT_PYTHON;
  const virtualEnvironmentPython = process.platform === "win32"
    ? join(process.cwd(), ".venv", "Scripts", "python.exe")
    : join(process.cwd(), ".venv", "bin", "python");
  return existsSync(virtualEnvironmentPython)
    ? virtualEnvironmentPython
    : process.platform === "win32" ? "python.exe" : "python3";
}

function startIsolatedApp(port, databasePath, reportsPath) {
  const child = spawn(
    findPython(),
    ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port), "--log-level", "warning"],
    {
      cwd: process.cwd(),
      env: {
        ...process.env,
        DESIGN_AGENT_DB_PATH: databasePath,
        DESIGN_AGENT_REPORTS_DIR: reportsPath,
        DESIGN_AGENT_AUTO_MIGRATE: "true",
        PYTHONUNBUFFERED: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    },
  );
  let output = "";
  const capture = (chunk) => {
    output = `${output}${String(chunk)}`.slice(-6000);
  };
  child.stdout.on("data", capture);
  child.stderr.on("data", capture);
  child.on("error", (error) => { child.spawnError = error; });
  child.capturedOutput = () => output;
  return child;
}

async function waitForApp(baseUrl, child) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (child.spawnError) throw child.spawnError;
    if (child.exitCode !== null) {
      throw new Error(`Isolated app exited before readiness (${child.exitCode}): ${child.capturedOutput()}`);
    }
    try {
      const response = await fetch(`${baseUrl}/health/ready`);
      if (response.ok) return;
    } catch {
      // Uvicorn is still starting.
    }
    await delay(100);
  }
  throw new Error(`Isolated app did not become ready: ${child.capturedOutput()}`);
}

async function stopChild(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  let exited = new Promise((resolve) => child.once("exit", resolve));
  child.kill();
  await Promise.race([exited, delay(5000)]);
  if (child.exitCode === null && child.signalCode === null) {
    exited = new Promise((resolve) => child.once("exit", resolve));
    child.kill("SIGKILL");
    await Promise.race([exited, delay(2000)]);
  }
}

function findChrome() {
  const candidates = [
    process.env.CHROME_PATH,
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ].filter(Boolean);
  const selected = candidates.find((candidate) => existsSync(candidate));
  if (!selected) throw new Error("Chrome was not found; set CHROME_PATH to run the browser state check");
  return selected;
}

async function availablePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

async function waitForChrome(port) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return;
    } catch {
      // Chrome has not opened the debugging endpoint yet.
    }
    await delay(100);
  }
  throw new Error("Chrome debugging endpoint did not become ready");
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}
