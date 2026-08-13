const downloadLink = document.querySelector("[data-pdf-download]");
const downloadStatus = document.querySelector("#pdf-download-status");

if (downloadLink && downloadStatus) {
  let downloadInProgress = false;

  downloadLink.addEventListener("click", async (event) => {
    event.preventDefault();
    if (downloadInProgress) return;

    downloadInProgress = true;
    const requestId = createRequestId();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 45_000);
    setDownloadState("loading", "正在生成或读取同源 PDF，请稍候……");
    downloadLink.setAttribute("aria-disabled", "true");
    downloadLink.textContent = "正在准备 PDF…";

    try {
      const response = await fetch(downloadLink.href, {
        method: "GET",
        headers: {
          Accept: "application/pdf",
          "X-Request-ID": requestId,
        },
        cache: "no-store",
        credentials: "same-origin",
        signal: controller.signal,
      });
      const responseRequestId = response.headers.get("X-Request-ID") || requestId;
      if (!response.ok) throw await readDownloadError(response, responseRequestId);

      const contentType = (response.headers.get("Content-Type") || "").toLowerCase();
      if (!contentType.includes("application/pdf")) {
        throw downloadError("PDF_RESPONSE_INVALID", "服务返回了非 PDF 内容", responseRequestId);
      }
      const blob = await response.blob();
      if (blob.size === 0) throw downloadError("PDF_RESPONSE_EMPTY", "服务返回了空 PDF", responseRequestId);
      if (blob.size < 5 || await blob.slice(0, 5).text() !== "%PDF-") {
        throw downloadError("PDF_RESPONSE_INVALID", "服务返回的文件不是有效 PDF", responseRequestId);
      }

      try {
        saveBlob(blob, downloadLink.dataset.filename || "engineering-report.pdf");
      } catch {
        throw downloadError("PDF_DOWNLOAD_START_FAILED", "浏览器未能启动 PDF 下载", responseRequestId);
      }
      setDownloadState("success", `PDF 下载已开始。请求 ID：${responseRequestId}`);
      downloadLink.textContent = "再次下载 PDF";
    } catch (error) {
      const detail = describeDownloadError(error, requestId);
      setDownloadState("error", detail.message);
      downloadLink.textContent = "重试 PDF 下载";
    } finally {
      window.clearTimeout(timeout);
      downloadLink.removeAttribute("aria-disabled");
      downloadInProgress = false;
    }
  });
}

function setDownloadState(state, message) {
  downloadStatus.hidden = false;
  downloadStatus.dataset.state = state;
  downloadStatus.textContent = message;
}

async function readDownloadError(response, fallbackRequestId) {
  const retryAfter = response.headers.get("Retry-After");
  const contentType = (response.headers.get("Content-Type") || "").toLowerCase();
  let code = `HTTP_${response.status}`;
  let message = `PDF 服务返回 HTTP ${response.status}`;
  let requestId = fallbackRequestId;

  if (contentType.includes("application/json")) {
    try {
      const payload = await response.json();
      if (payload?.error) {
        code = payload.error.code || code;
        message = payload.error.message || message;
        requestId = payload.error.request_id || requestId;
      }
    } catch {
      message = `PDF 服务返回了无法解析的错误响应（HTTP ${response.status}）`;
    }
  }
  return downloadError(code, message, requestId, retryAfter);
}

function describeDownloadError(error, fallbackRequestId) {
  if (error?.name === "AbortError") {
    return {
      message: `PDF 下载等待超时；服务器可能仍在生成同一报告，可安全重试下载。请求 ID：${fallbackRequestId}`,
    };
  }
  if (error?.downloadCode) {
    const retryText = error.retryAfter ? ` 请在 ${error.retryAfter} 秒后重试。` : " 可安全重试下载。";
    return {
      message: `${error.message}（${error.downloadCode}）。${retryText}请求 ID：${error.requestId || fallbackRequestId}`,
    };
  }
  return {
    message: `PDF 下载连接中断；如果服务器已完成生成，重试会读取同一缓存报告。请求 ID：${fallbackRequestId}`,
  };
}

function downloadError(code, message, requestId, retryAfter = null) {
  const error = new Error(message);
  error.downloadCode = code;
  error.requestId = requestId;
  error.retryAfter = retryAfter;
  return error;
}

function saveBlob(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const temporaryLink = document.createElement("a");
  temporaryLink.href = objectUrl;
  temporaryLink.download = filename;
  temporaryLink.hidden = true;
  document.body.append(temporaryLink);
  temporaryLink.click();
  temporaryLink.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1_000);
}

function createRequestId() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (value) => value.toString(16).padStart(2, "0")).join("");
}
