const form = document.querySelector("#review");
const first = document.querySelector("#first");
const second = document.querySelector("#second");
const category = document.querySelector("#category");
const result = document.querySelector("#result");
const submit = document.querySelector("#submit");
const draftKey = "torob-review-draft";
const labels = {
  approve: "پیشنهاد تأیید",
  reject: "پیشنهاد رد",
  split: "پیشنهاد جداسازی",
  review: "نیاز به بررسی انسانی",
};

chrome.storage.session.get(draftKey).then((values) => {
  const draft = values[draftKey] || {};
  if (!first.value) first.value = draft.first || "";
  if (!second.value) second.value = draft.second || "";
  if (!category.value) category.value = draft.category || "";
}).catch(() => {});

function saveDraft() {
  chrome.storage.session.set({
    [draftKey]: { first: first.value, second: second.value, category: category.value },
  }).catch(() => {});
}
form.addEventListener("input", saveDraft);

const readButton = document.querySelector("#read-request");
const autoButton = document.querySelector("#auto-vote");

async function readOpenRequest() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = new URL(tab?.url);
  if (url.origin !== "https://panel.torob.com" || !/^\/cs\/voting\/w(?:\/|$)/.test(url.pathname)) {
    return null;
  }
  const [{ result: request, documentId }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["read-request.js"],
  });
  if (!request) return null;
  return { request, tabId: tab.id, documentId };
}

readButton.addEventListener("click", async () => {
  try {
    const open = await readOpenRequest();
    if (!open) {
      result.textContent = "درخواست در انتظار بررسی پیدا نشد. عنوان‌ها را دستی وارد کنید.";
      return;
    }
    [first.value, second.value] = open.request.titles;
    category.value = open.request.category;
    saveDraft();
    form.requestSubmit(submit);
  } catch {
    result.textContent = "خواندن درخواست ممکن نشد. صفحهٔ پنل را دوباره باز کنید.";
  }
});

async function submitModelRejection(expected, labelToClick) {
  const snapshot = () => globalThis.readTorobMergeRequest?.();
  const signature = (request) => JSON.stringify([...request.titles].sort());
  const current = snapshot();
  if (!current || signature(current) !== signature(expected) ||
      current.category !== expected.category || document.visibilityState !== "visible") {
    return "changed";
  }

  const key = signature(current);
  const attempted = globalThis.torobAttemptedVotes ??= new Set();
  if (attempted.has(key)) return "duplicate";

  const choices = [...document.querySelectorAll('button.btn-outline-danger[type="button"]')]
    .filter((button) => {
      const label = [...button.childNodes].filter((node) => node.nodeType === Node.TEXT_NODE)
        .map((node) => node.textContent).join("").replace(/\s+/g, " ").trim();
      return label === labelToClick && !button.disabled &&
        button.getClientRects().length > 0 && getComputedStyle(button).visibility === "visible";
    });
  if (choices.length !== 1) return "unavailable";

  attempted.add(key);
  choices[0].click();
  const deadline = Date.now() + 6000;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 200));
    const next = snapshot();
    if (next && signature(next) !== key) return "advanced";
  }
  return "uncertain";
}

autoButton.addEventListener("click", async () => {
  autoButton.disabled = true;
  result.textContent = "در حال بررسی درخواست باز…";
  try {
    const open = await readOpenRequest();
    if (!open?.documentId) {
      result.textContent = "درخواست در انتظار بررسی پیدا نشد.";
      return;
    }
    const verdict = await getVerdict(open.request.titles, open.request.category);
    const labelToClick = new Map([
      ["multiple_phone_models_in_title", "عدم ذکر مدل در عنوان"],
      ["different_phone_models", "تفاوت در مدل"],
    ]).get(verdict.reason_code);
    if (verdict.decision !== "reject" || !labelToClick) {
      result.textContent = "این درخواست به بررسی دستی نیاز دارد.";
      return;
    }
    const [{ result: status }] = await chrome.scripting.executeScript({
      target: { tabId: open.tabId, documentIds: [open.documentId] },
      func: submitModelRejection,
      args: [open.request, labelToClick],
    });
    result.textContent = {
      advanced: "گزینهٔ رد ارسال شد و پنل به درخواست بعدی رفت.",
      changed: "درخواست عوض شد. رأیی ارسال نشد.",
      duplicate: "برای این عنوان‌ها قبلاً یک بار اقدام شده است. وضعیت را در پنل بررسی کنید.",
      unavailable: "دکمهٔ مناسب پیدا نشد. رأیی ارسال نشد.",
      uncertain: "دکمهٔ رد زده شد، اما درخواست بعدی دیده نشد. وضعیت را در پنل بررسی کنید.",
    }[status];
  } catch {
    result.textContent = "نتیجهٔ عملیات مشخص نیست. وضعیت را در پنل بررسی کنید.";
  } finally {
    autoButton.disabled = false;
  }
});

async function getVerdict(titles, productCategory, useModel = false) {
  const response = await fetch("http://127.0.0.1:8765/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      kind: "merge", category: productCategory, use_model: useModel,
      left: { title: titles[0] }, right: { title: titles[1] },
    }),
    signal: AbortSignal.timeout(useModel ? 20000 : 5000),
  });
  if (!response.ok) throw new Error("Local review failed");
  return response.json();
}

document.querySelector("#capture").addEventListener("click", async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = new URL(tab?.url);
    if (url.origin !== "https://panel.torob.com" || !/^\/cs\/voting\/w(?:\/|$)/.test(url.pathname)) {
      result.textContent = "صفحهٔ بررسی درخواست‌های ترب را باز کنید.";
      return;
    }
    if (first.value.trim() && second.value.trim()) {
      result.textContent = "برای جایگزینی عنوان، اول فیلد مربوط را خالی کنید.";
      return;
    }
    const [{ result: selection }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection()?.toString().trim(),
    });
    if (!selection || selection.length > 500) {
      result.textContent = "متن یک عنوان را در پنل انتخاب کنید یا در این فرم بچسبانید.";
      return;
    }
    const target = first.value.trim() ? second : first;
    target.value = selection;
    saveDraft();
    result.textContent = "عنوان خوانده شد.";
  } catch {
    result.textContent = "خواندن عنوان ممکن نشد. می‌توانید عنوان را دستی وارد کنید.";
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submit.disabled = true;
  result.textContent = "در حال بررسی…";
  try {
    const { decision, reason, source } = await getVerdict(
      [first.value.trim(), second.value.trim()], category.value,
      document.querySelector("#use-model").checked,
    );
    result.textContent = [source === "openai" ? "پیشنهاد OpenAI" : "", labels[decision], reason].filter(Boolean).join(" — ");
  } catch {
    result.textContent = "پیشنهاد دریافت نشد. مطمئن شوید ایجنت محلی در حال اجراست.";
  } finally {
    submit.disabled = false;
  }
});
