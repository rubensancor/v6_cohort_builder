(function () {
  "use strict";

  const root = document.documentElement;
  const themeButton = document.getElementById("theme-toggle");
  const savedTheme = localStorage.getItem("cohort-guide-theme");
  const preferredTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";

  root.dataset.theme = savedTheme || preferredTheme;

  themeButton?.addEventListener("click", function () {
    const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = nextTheme;
    localStorage.setItem("cohort-guide-theme", nextTheme);
  });

  const stages = {
    1: {
      file: "cohort.py",
      title: "Reject ambiguous or invalid cohort definitions",
      description: "The request must contain a non-empty name and exactly one of SQL or ATLAS JSON. The cohort ID must be positive; if absent, the helper creates one. The overwrite value must be a real boolean.",
      input: "name, SQL/JSON, ID, overwrite",
      output: "an immutable <code>CohortRequest</code>",
      error: "<code>CohortInputError</code> before any federated work starts"
    },
    2: {
      file: "central.py + cohort.py",
      title: "Normalize both input formats into CohortGenerator SQL",
      description: "SQL is forwarded unchanged. ATLAS JSON is normalized, converted to an OHDSI cohort expression, and built into SQL through the Circe wrapper. All nodes therefore receive the same SQL and cohort ID.",
      input: "validated SQL or normalized ATLAS JSON",
      output: "one CohortGenerator SQL string",
      error: "invalid JSON or conversion failure stops central dispatch"
    },
    3: {
      file: "central.py",
      title: "Create one federated subtask for every organization",
      description: "The central client lists organizations, collects their IDs, and creates a task whose method is generate_cohort_count. SQL, name, ID, and overwrite are sent as arguments to all selected organizations.",
      input: "cohort SQL plus organization IDs",
      output: "a vantage6 task targeting every organization",
      error: "client/task failure occurs before node execution"
    },
    4: {
      file: "federated.py + cohort.py",
      title: "Turn node environment variables into an OMOP configuration",
      description: "Each node reads the database URI, DBMS, credentials, CDM schema, and results schema. Organization and node IDs are optional integers used to make responses attributable.",
      input: "DATABASE_* and DB_PARAM_* environment values",
      output: "an immutable <code>OmopConfig</code>",
      error: "<code>NodeConfigError</code> becomes a structured node error payload"
    },
    5: {
      file: "cohort.py",
      title: "Create tables, generate the cohort, and obtain its count",
      description: "The OHDSI wrappers connect to OMOP, create cohort tables, detect an existing cohort ID, optionally delete its rows, convert a pandas definition set to R, generate the cohort, convert counts back to Python, and disconnect in a finally block.",
      input: "OMOP config, SQL, name, ID, overwrite",
      output: "database/schema metadata and an exact subject count",
      error: "duplicate ID, JDBC, R, OHDSI, or SQL failure is raised to the node adapter"
    },
    6: {
      file: "federated.py",
      title: "Return a stable success or error contract",
      description: "A successful result includes identity, cohort metadata, database/schema names, and count. Any exception is caught and returned with status error and its message, preserving identity when configuration was already available.",
      input: "cohort execution result or exception",
      output: "a serializable node payload",
      error: "errors are data here; they do not escape the federated action"
    },
    7: {
      file: "central.py + cohort.py",
      title: "Aggregate without hiding incomplete federation",
      description: "Successful nodes are retained, explicit failures are listed, and missing organizations become synthetic errors. The exact total is computed only when the errors list is empty.",
      input: "raw results and expected organization IDs",
      output: "nodes, errors, and total_count",
      error: "any error or missing organization forces <code>total_count: null</code>"
    }
  };

  const stageFields = {
    number: document.getElementById("stage-number"),
    file: document.getElementById("stage-file"),
    title: document.getElementById("stage-title"),
    description: document.getElementById("stage-description"),
    input: document.getElementById("stage-in"),
    output: document.getElementById("stage-out"),
    error: document.getElementById("stage-error")
  };

  document.querySelectorAll("[data-stage]").forEach(function (button) {
    button.addEventListener("click", function () {
      const stageId = button.dataset.stage;
      const stage = stages[stageId];
      if (!stage) return;

      document.querySelectorAll("[data-stage]").forEach(function (item) {
        item.classList.toggle("active", item === button);
      });
      stageFields.number.textContent = "STEP " + String(stageId).padStart(2, "0");
      stageFields.file.textContent = stage.file;
      stageFields.title.textContent = stage.title;
      stageFields.description.textContent = stage.description;
      stageFields.input.innerHTML = stage.input;
      stageFields.output.innerHTML = stage.output;
      stageFields.error.innerHTML = stage.error;
    });
  });

  document.querySelectorAll("[data-filter]").forEach(function (button) {
    button.addEventListener("click", function () {
      const filter = button.dataset.filter;
      document.querySelectorAll("[data-filter]").forEach(function (item) {
        item.classList.toggle("active", item === button);
      });
      document.querySelectorAll("[data-category]").forEach(function (card) {
        card.hidden = filter !== "all" && card.dataset.category !== filter;
      });
    });
  });

  document.querySelectorAll("[data-test-tab]").forEach(function (button) {
    button.addEventListener("click", function () {
      const selected = button.dataset.testTab;
      document.querySelectorAll("[data-test-tab]").forEach(function (tab) {
        const active = tab === button;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-selected", String(active));
      });
      document.querySelectorAll("[data-test-panel]").forEach(function (panel) {
        const active = panel.dataset.testPanel === selected;
        panel.classList.toggle("active", active);
        panel.hidden = !active;
      });
    });
  });

  document.querySelectorAll("[data-copy-target]").forEach(function (button) {
    button.addEventListener("click", async function () {
      const target = document.getElementById(button.dataset.copyTarget);
      if (!target) return;
      const previous = button.textContent;
      try {
        await navigator.clipboard.writeText(target.innerText);
        button.textContent = "Copied";
      } catch (error) {
        button.textContent = "Select text";
        window.getSelection()?.selectAllChildren(target);
      }
      window.setTimeout(function () { button.textContent = previous; }, 1600);
    });
  });

  const toc = document.getElementById("toc");
  const tocLinks = Array.from(toc?.querySelectorAll("a") || []);
  const sections = tocLinks.map(function (link) {
    return { link: link, element: document.querySelector(link.getAttribute("href")) };
  }).filter(function (item) { return item.element; });

  const observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (!entry.isIntersecting) return;
      sections.forEach(function (item) { item.link.classList.remove("active"); });
      const current = sections.find(function (item) { return item.element === entry.target; });
      if (current) {
        current.link.classList.add("active");
        if (window.innerWidth <= 1000) {
          current.link.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
        }
      }
    });
  }, { rootMargin: "-12% 0px -76% 0px" });

  sections.forEach(function (item) { observer.observe(item.element); });
  tocLinks.forEach(function (link) {
    link.addEventListener("click", function (event) {
      const target = document.querySelector(link.getAttribute("href"));
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      history.replaceState(null, "", link.getAttribute("href"));
    });
  });
})();
