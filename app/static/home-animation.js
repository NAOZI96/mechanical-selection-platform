"use strict";

(() => {
  const finder = document.querySelector("[data-module-finder]");
  if (!finder) return;

  const search = finder.querySelector("[data-module-search]");
  const filters = [...finder.querySelectorAll("[data-module-filter]")];
  const cards = [...document.querySelectorAll("[data-module-card]")];
  const count = finder.querySelector("[data-module-count]");
  const empty = document.querySelector("[data-module-empty]");
  let activeCategory = "all";

  const normalize = (value) =>
    String(value || "")
      .normalize("NFKC")
      .trim()
      .toLocaleLowerCase("zh-CN");

  const applyFilter = () => {
    const query = normalize(search?.value);
    let visibleCount = 0;

    cards.forEach((card) => {
      const matchesCategory =
        activeCategory === "all" || card.dataset.category === activeCategory;
      const matchesQuery = !query || normalize(card.dataset.search).includes(query);
      const visible = matchesCategory && matchesQuery;
      card.hidden = !visible;
      if (visible) visibleCount += 1;
    });

    if (count) count.textContent = String(visibleCount);
    if (empty) empty.hidden = visibleCount !== 0;
  };

  search?.addEventListener("input", applyFilter);

  filters.forEach((button) => {
    button.addEventListener("click", () => {
      activeCategory = button.dataset.moduleFilter || "all";
      filters.forEach((item) =>
        item.setAttribute("aria-pressed", String(item === button)),
      );
      applyFilter();
    });
  });
})();
