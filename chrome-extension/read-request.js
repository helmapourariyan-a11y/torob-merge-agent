globalThis.readTorobMergeRequest = () => {
  if (location.origin !== "https://panel.torob.com" || !/^\/cs\/voting\/w(?:\/|$)/.test(location.pathname)) {
    return null;
  }

  const visible = (element) => element.getClientRects().length > 0 &&
    getComputedStyle(element).visibility === "visible";
  const text = (element) => element.textContent.replace(/\s+/g, " ").trim();
  const directText = (element) => [...element.childNodes]
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => node.textContent).join("").trim();

  const cards = [...document.querySelectorAll('h5[class*="_baseTitle_"]')].filter(visible);
  const pending = [...document.querySelectorAll('[class*="_baseProductStatus_"]')]
    .filter((element) => visible(element) && directText(element) === "در انتظار بررسی");
  if (cards.length !== 2 || pending.length !== 1) return null;

  const titles = cards.map((card) => [...card.children].map(text).join(" ").trim());
  if (titles.some((title) => !title || title.length > 500)) return null;
  return {
    titles,
    category: titles.every((title) => /قاب|کاور/.test(title)) ? "phone_case" : "",
  };
};
globalThis.readTorobMergeRequest();
