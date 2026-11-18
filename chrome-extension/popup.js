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

document.querySelector("#read-request").addEventListener("click", async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = new URL(tab?.url);
    if (url.origin !== "https://panel.torob.com" || !/^\/cs\/voting\/w(?:\/|$)/.test(url.pathname)) {
      result.textContent = "صفحهٔ بررسی درخواست‌های ترب را باز کنید.";
      return;
    }
    const [{ result: request }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["read-request.js"],
    });
    if (!request) {
      result.textContent = "دو عنوان و وضعیت در انتظار بررسی پیدا نشد. عنوان‌ها را دستی وارد کنید.";
      return;
    }
    [first.value, second.value] = request.titles;
    category.value = request.category;
    saveDraft();
    form.requestSubmit(submit);
  } catch {
    result.textContent = "خواندن درخواست ممکن نشد. صفحهٔ پنل را دوباره باز کنید.";
  }
});

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
    const response = await fetch("http://127.0.0.1:8765/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "merge", category: category.value,
        left: { title: first.value.trim() }, right: { title: second.value.trim() },
      }),
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error("Local review failed");
    const { decision, reason } = await response.json();
    result.textContent = [labels[decision], reason].filter(Boolean).join(" — ");
  } catch {
    result.textContent = "پیشنهاد دریافت نشد. مطمئن شوید ایجنت محلی در حال اجراست.";
  } finally {
    submit.disabled = false;
  }
});
