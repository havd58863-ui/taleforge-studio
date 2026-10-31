document.addEventListener("DOMContentLoaded", () => {
  // Live vector search (if a search field is rendered later)
  const searchField = document.querySelector("[data-search]");
  if (searchField) {
    let timer;
    searchField.addEventListener("input", (event) => {
      const q = event.target.value.trim();
      clearTimeout(timer);
      if (!q) return;
      timer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          console.log("Search results:", data.items);
        } catch (err) {
          console.warn("Search failed", err);
        }
      }, 250);
    });
  }

  // Run the full demo pipeline from the dashboard
  const pipelineBtn = document.querySelector("[data-pipeline]");
  const output = document.querySelector("[data-output]");
  if (pipelineBtn && output) {
    pipelineBtn.addEventListener("click", async () => {
      pipelineBtn.disabled = true;
      output.textContent = "Running pipeline…";
      try {
        const res = await fetch("/api/pipeline/demo", { method: "POST" });
        const data = await res.json();
        output.textContent = JSON.stringify(
          {
            story: data.story && data.story.title,
            cover_pdf: data.cover_pdf,
            interior_pdf: data.interior_pdf,
            zip: data.zip,
            bundle_dir: data.bundle_dir,
          },
          null,
          2
        );
      } catch (err) {
        output.textContent = `Pipeline failed: ${err}`;
      } finally {
        pipelineBtn.disabled = false;
      }
    });
  }
});
