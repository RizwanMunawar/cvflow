/* CVFlow dashboard behavior.
   Charts are Chart.js (vendored and inlined: no network, no build step), with
   the same defaults, entry animation and sweep reveal as the Ultralytics social
   dashboard this design system comes from. Everything else is plain DOM. */

(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("cvflow-data").textContent);
  var Chart = window.Chart;

  var SEVERITIES = ["ERROR", "WARNING", "INFO"];
  var SEV = {
    ERROR: { varName: "--sev-error", tint: "var(--tint-error)", icon: "!" },
    WARNING: { varName: "--sev-warning", tint: "var(--tint-warning)", icon: "!" },
    INFO: { varName: "--sev-info", tint: "var(--tint-info)", icon: "i" }
  };
  var PAGE = 60;
  var charts = {};          // id -> Chart instance, destroyed on theme change
  var api = { enabled: false, writable: false, classes: {} };

  /* -------------------------------------------------------------- helpers */

  function el(tag, attrs, text) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        if (key === "style") node.style.cssText = attrs[key];
        else if (key === "class") node.className = attrs[key];
        else node.setAttribute(key, attrs[key]);
      });
    }
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function byId(id) { return document.getElementById(id); }
  function fileName(path) { return String(path).split(/[\\/]/).pop(); }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }
  function hide(id) { var n = byId(id); if (n) n.hidden = true; }
  function fmt(n) { return Number(n).toLocaleString(); }
  function pct(share, digits) { return (share * 100).toFixed(digits === undefined ? 1 : digits) + "%"; }
  function plural(n, word, many) { return fmt(n) + " " + (n === 1 ? word : (many || word + "s")); }

  /* Chart.js does not ellipsize category labels, it just lets them run into
     the plot. Trim here instead; the full text stays in the tooltip title. */
  function shorten(text, max, keepTail) {
    var value = String(text);
    if (value.length <= max) return value;
    return keepTail ? "…" + value.slice(-(max - 1)) : value.slice(0, max - 1) + "…";
  }

  function round(value) {
    if (!isFinite(value)) return String(value);
    var size = Math.abs(value);
    if (size >= 100) return String(Math.round(value));
    if (size >= 1) return String(Math.round(value * 100) / 100);
    return String(Math.round(value * 1000) / 1000);
  }

  function describe(value) {
    if (value === null || value === undefined) return "-";
    if (typeof value === "number") return round(value);
    if (Array.isArray(value)) return value.map(describe).join(", ");
    if (typeof value === "object") {
      return Object.keys(value).map(function (k) { return k + " " + describe(value[k]); }).join(", ");
    }
    return String(value);
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function sevColor(key) { return cssVar(SEV[key].varName); }

  function theme() {
    return {
      surface: cssVar("--surface-1"),
      text: cssVar("--text-primary"),
      textSecondary: cssVar("--text-secondary"),
      muted: cssVar("--text-muted"),
      grid: cssVar("--grid"),
      baseline: cssVar("--baseline"),
      accent: cssVar("--accent")
    };
  }

  function alpha(hex, a) {
    var h = hex.replace("#", "");
    var full = h.length === 3 ? h.split("").map(function (c) { return c + c; }).join("") : h;
    return "rgba(" + parseInt(full.slice(0, 2), 16) + ", " + parseInt(full.slice(2, 4), 16) +
      ", " + parseInt(full.slice(4, 6), 16) + ", " + a + ")";
  }

  /* ---------------------------------------------------------------- motion */

  function reducedMotion() {
    return window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)").matches : false;
  }

  /* Marks arrive staggered along the axis, so a chart reads as being drawn
     rather than pasted in. Only the first render animates. */
  function entryAnim(stepMs, duration) {
    if (reducedMotion()) return { duration: 0 };
    var first = true;
    return {
      duration: duration || 650,
      easing: "easeOutQuart",
      delay: function (ctx) {
        return first && ctx.type === "data" ? Math.min(ctx.dataIndex * stepMs, 800) : 0;
      },
      onComplete: function () { first = false; }
    };
  }

  /* Reveals a plot left to right by clipping it to a widening rectangle: the
     wipe is what reads as "being drawn". */
  function sweepReveal(totalMs) {
    var start = 0;
    var done = reducedMotion();
    var clipped = false;
    return {
      id: "sweepReveal",
      beforeDatasetsDraw: function (chart) {
        if (done) return;
        var a = chart.chartArea;
        if (!a || a.right <= a.left) return;
        var now = performance.now();
        if (!start) start = now;
        var p = Math.min((now - start) / (totalMs || 850), 1);
        var eased = 1 - Math.pow(1 - p, 3);
        chart.ctx.save();
        clipped = true;
        chart.ctx.beginPath();
        chart.ctx.rect(a.left, a.top, (a.right - a.left) * eased, a.bottom - a.top);
        chart.ctx.clip();
        if (p >= 1) done = true;
        else requestAnimationFrame(function () { try { chart.draw(); } catch (e) { /* gone */ } });
      },
      afterDatasetsDraw: function (chart) {
        if (clipped) { chart.ctx.restore(); clipped = false; }
      }
    };
  }

  var crosshair = {
    id: "crosshair",
    afterDraw: function (chart) {
      var active = chart.tooltip && chart.tooltip.getActiveElements ? chart.tooltip.getActiveElements() : [];
      if (!active.length) return;
      var x = active[0].element.x;
      var ctx = chart.ctx;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x, chart.chartArea.top);
      ctx.lineTo(x, chart.chartArea.bottom);
      ctx.lineWidth = 1;
      ctx.strokeStyle = theme().baseline;
      ctx.stroke();
      ctx.restore();
    }
  };

  function applyChartDefaults() {
    var t = theme();
    var dark = currentTheme() === "dark";
    Chart.defaults.font.family = '"Archivo", system-ui, -apple-system, "Segoe UI", sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.color = t.textSecondary;
    Chart.defaults.borderColor = t.grid;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.animation = reducedMotion() ? false : { duration: 500, easing: "easeOutQuart" };
    Chart.defaults.transitions.active.animation.duration = 0;
    var colorAnim = Chart.defaults.animations.colors;
    if (colorAnim) colorAnim.properties = ["color", "borderColor"];
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.backgroundColor = dark ? "#000000" : "#ffffff";
    Chart.defaults.plugins.tooltip.titleColor = t.text;
    Chart.defaults.plugins.tooltip.bodyColor = t.textSecondary;
    Chart.defaults.plugins.tooltip.borderColor = t.baseline;
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.boxPadding = 4;
    Chart.defaults.plugins.tooltip.usePointStyle = true;
    Chart.defaults.plugins.tooltip.titleFont = { weight: "bold", size: 12 };
  }

  /* ---------------------------------------------------------- chart makers */

  function baseScales(t, horizontal) {
    // No gridlines anywhere: the value labels and the baseline carry the scale.
    var value = {
      beginAtZero: true,
      grid: { display: false },
      border: { display: false },
      ticks: { color: t.muted, padding: 6, font: { size: 11 }, callback: function (v) { return fmt(v); } }
    };
    var category = {
      grid: { display: false },
      border: { color: t.baseline },
      ticks: { color: t.muted, maxRotation: 0, autoSkip: true, font: { size: 11 } }
    };
    return horizontal ? { x: value, y: category } : { x: category, y: value };
  }

  function bars(id, opts) {
    var canvas = byId(id);
    if (!canvas) return null;
    var t = theme();
    var horizontal = !!opts.horizontal;
    var scales = baseScales(t, horizontal);
    if (horizontal) {
      // crossAlign "far" pins category labels to the axis, so a long one grows
      // leftwards into the padding instead of being clipped by the canvas.
      scales.y.ticks = {
        color: t.textSecondary, font: { size: 11.5 }, autoSkip: false, crossAlign: "far", padding: 6
      };
    }
    if (opts.stacked) { scales.x.stacked = true; scales.y.stacked = true; }

    charts[id] = new Chart(canvas, {
      type: "bar",
      data: {
        labels: opts.labels,
        datasets: (opts.datasets || [{ data: opts.data, backgroundColor: opts.colors }]).map(function (set) {
          return {
            label: set.label || "",
            data: set.data,
            backgroundColor: set.backgroundColor,
            borderRadius: 4,
            borderSkipped: false,
            maxBarThickness: 26,
            categoryPercentage: 0.72,
            barPercentage: 0.92
          };
        })
      },
      options: {
        animation: entryAnim(35, 550),
        indexAxis: horizontal ? "y" : "x",
        onClick: opts.onSelect ? function (event, els) {
          if (els.length) opts.onSelect(els[0].index);
        } : undefined,
        onHover: opts.onSelect ? function (event, els) {
          event.native.target.style.cursor = els.length ? "pointer" : "default";
        } : undefined,
        scales: scales,
        plugins: {
          tooltip: {
            callbacks: {
              title: function (items) { return opts.titles ? opts.titles[items[0].dataIndex] : String(items[0].label); },
              label: function (c) {
                var v = horizontal ? c.parsed.x : c.parsed.y;
                var name = c.dataset.label ? c.dataset.label + ": " : "";
                return "  " + name + fmt(v) + (opts.unit ? " " + opts.unit : "");
              },
              footer: opts.footers ? function (items) { return opts.footers[items[0].dataIndex]; } : undefined
            }
          }
        }
      }
    });
    return charts[id];
  }

  function areaLine(id, opts) {
    var canvas = byId(id);
    if (!canvas) return null;
    var t = theme();
    var color = opts.color || t.accent;
    charts[id] = new Chart(canvas, {
      type: "line",
      plugins: [crosshair, sweepReveal()],
      data: {
        labels: opts.labels,
        datasets: [{
          label: opts.name || "",
          data: opts.data,
          borderColor: color,
          backgroundColor: function (ctx) {
            var area = ctx.chart.chartArea;
            if (!area) return alpha(color, 0.3);
            var g = ctx.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
            g.addColorStop(0, alpha(color, 0.3));
            g.addColorStop(1, alpha(color, 0));
            return g;
          },
          fill: true,
          borderWidth: 2,
          tension: 0.32,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBorderColor: t.surface,
          pointHoverBorderWidth: 2,
          pointHoverBackgroundColor: color
        }]
      },
      options: {
        animation: entryAnim(0, 420),
        interaction: { mode: "index", intersect: false },
        scales: {
          x: {
            grid: { display: false },
            border: { color: t.baseline },
            ticks: { color: t.muted, maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 11 } }
          },
          y: {
            beginAtZero: true, min: 0, max: opts.max,
            grid: { display: false },
            border: { display: false },
            ticks: { color: t.muted, padding: 8, font: { size: 11 }, callback: opts.yFmt || fmt }
          }
        },
        plugins: {
          tooltip: {
            callbacks: {
              title: function (items) { return opts.titles ? opts.titles[items[0].dataIndex] : String(items[0].label); },
              label: function (c) { return "  " + (opts.valueFmt ? opts.valueFmt(c.parsed.y) : fmt(c.parsed.y)); }
            }
          }
        }
      }
    });
    return charts[id];
  }

  function table(node, columns, rows) {
    clear(node);
    var head = el("tr");
    columns.forEach(function (c) { head.appendChild(el("th", { class: c.num ? "num" : "" }, c.label)); });
    node.appendChild(el("thead")).appendChild(head);
    var body = el("tbody");
    rows.forEach(function (row) {
      var tr = el("tr");
      columns.forEach(function (c) { tr.appendChild(el("td", { class: c.num ? "num" : "" }, c.get(row))); });
      body.appendChild(tr);
    });
    node.appendChild(body);
  }

  /* ------------------------------------------------------------- sections */

  function renderChrome() {
    var ds = data.dataset;
    document.title = ds.name + " · CVFlow";
    byId("crumb-dataset").textContent = ds.name;
    byId("ds-generated").textContent = data.generatedLabel;
    byId("tab-count").textContent = fmt(data.issuesTotal);
    byId("page-title").textContent = ds.name;

    var root = byId("ds-root");
    root.textContent = ds.root;
    root.title = ds.root;

    byId("page-lede").textContent =
      ds.format + " · " + plural(ds.images, "image") + " · " + plural(ds.annotations, "annotation") +
      " · " + plural(ds.classes, "class", "classes") +
      (ds.splits.length ? " · splits: " + ds.splits.join(", ") : " · no splits") +
      ". " + plural(data.issuesTotal, "finding") + " worth a look.";

    byId("foot-meta").textContent = "CVFlow " + (data.version ? "v" + data.version : "") + " · " + data.generatedLabel;
    byId("foot-version").textContent = "CVFlow " + (data.version ? "v" + data.version : "");
  }

  function seriesColor(index) {
    return cssVar("--s" + ((index % 8) + 1));
  }

  /* Sidebar: the dataset's facts as brand-coloured pills, then grouped
     navigation: views, severities and checks: in the same indented list the
     rest of the design system uses. */
  function renderSideGroups() {
    var ds = data.dataset;
    var host = clear(byId("side-groups"));

    function group(label) {
      var section = el("div", { class: "side-group" });
      section.appendChild(el("p", { class: "side-cap" }, label));
      host.appendChild(section);
      return section;
    }

    function navButton(section, opts) {
      var node = el("button", { class: "side-btn" + (opts.active ? " active" : ""), type: "button" });
      if (opts.color) {
        node.style.setProperty("--c", opts.color);
        node.appendChild(el("span", { class: "dot" }));
      }
      node.appendChild(el("span", { class: "name", title: opts.label }, opts.label));
      if (opts.count !== null && opts.count !== undefined) {
        node.appendChild(el("span", { class: "n" }, fmt(opts.count)));
      }
      if (opts.tip) node.dataset.tip = opts.tip;
      node.addEventListener("click", opts.onSelect);
      section.appendChild(node);
      return node;
    }

    // Dataset facts: one pill per fact, each in its own brand hue.
    var facts = group("Dataset");
    var pills = el("div", { class: "tags" });
    var values = [
      { label: ds.format.toLowerCase(), count: null },
      { label: ds.taskLabel.toLowerCase(), count: null },
      { label: "images", count: ds.images },
      { label: "annotations", count: ds.annotations },
      { label: "classes", count: ds.classes }
    ];
    if (ds.emptyImages) values.push({ label: "empty", count: ds.emptyImages });
    ds.splits.forEach(function (name) {
      var split = data.splits.filter(function (s) { return s.name === name; })[0];
      values.push({ label: name, count: split ? split.images : null });
    });
    values.forEach(function (item, index) {
      var pill = el("span", { class: "tag", style: "--c:" + seriesColor(index) });
      pill.appendChild(el("span", { class: "dot" }));
      pill.appendChild(el("span", null, item.label));
      if (item.count !== null) pill.appendChild(el("span", { class: "n" }, fmt(item.count)));
      pills.appendChild(pill);
    });
    facts.appendChild(pills);

    var severity = group("Severity");
    SEVERITIES.forEach(function (key) {
      navButton(severity, {
        label: key.charAt(0) + key.slice(1).toLowerCase(),
        count: data.severityCounts[key] || 0,
        color: sevColor(key),
        tip: "Show only " + key.toLowerCase() + " findings",
        onSelect: function () {
          SEVERITIES.forEach(function (other) { state.severities[other] = other === key; });
          state.type = "";
          byId("type-filter").value = "";
          syncSeverityChips();
          focusFindings();
        }
      });
    });

    if (data.issueTypes.length) {
      var checks = group("Checks that fired");
      data.issueTypes.slice(0, 8).forEach(function (row) {
        navButton(checks, {
          label: row.code,
          count: row.count,
          color: sevColor(row.severity),
          tip: "Filter findings to " + row.code,
          onSelect: function () {
            state.type = row.code;
            byId("type-filter").value = row.code;
            focusFindings();
          }
        });
      });
    }
  }

  function kpis(hostId, entries) {
    var host = clear(byId(hostId));
    entries.forEach(function (entry) {
      var node = el("div", { class: "kpi" });
      var label = el("div", { class: "label" });
      label.appendChild(el("span", { class: "dot", style: "--c:" + (entry.color || cssVar("--s1")) }));
      label.appendChild(el("span", null, entry.key));
      node.appendChild(label);

      var value = el("div", { class: "value" }, entry.value);
      if (entry.unit) value.appendChild(el("span", { class: "unit" }, entry.unit));
      node.appendChild(value);

      var foot = el("div", { class: "foot" });
      if (entry.pills) {
        entry.pills.forEach(function (pill) {
          var chip = el("span", { class: "pill", style: "--c:" + pill.color });
          chip.appendChild(el("i"));
          chip.appendChild(el("span", null, pill.text));
          foot.appendChild(chip);
        });
      } else {
        foot.textContent = entry.note || " ";
      }
      node.appendChild(foot);
      host.appendChild(node);
    });
  }

  function renderKpis() {
    var ds = data.dataset;
    var stats = data.stats;
    var counts = data.severityCounts;
    var classes = data.classes;
    var coverage = data.classCoverage;
    var s = [cssVar("--s1"), cssVar("--s2"), cssVar("--s3"), cssVar("--s4")];

    kpis("kpi-overview", [
      { key: "Images", value: fmt(ds.images), color: s[0], note: ds.emptyImages ? fmt(ds.emptyImages) + " with no annotations" : "all annotated" },
      { key: "Annotations", value: fmt(ds.annotations), color: s[1], note: stats && stats.objectsPerImage.count ? "median " + round(stats.objectsPerImage.median) + " per image" : "" },
      { key: "Classes", value: fmt(ds.classes), color: s[2], note: classes.length ? "top: " + classes[0].name + " (" + pct(classes[0].share) + ")" : "" },
      {
        key: "Findings", value: fmt(data.issuesTotal), color: sevColor("ERROR"),
        pills: SEVERITIES.map(function (key) {
          var n = counts[key] || 0;
          return { color: sevColor(key), text: key === "INFO" ? fmt(n) + " info" : plural(n, key.toLowerCase()) };
        })
      }
    ]);

    var rare = classes.filter(function (item) { return item.share < 0.01; }).length;
    kpis("kpi-classes", [
      { key: "Classes", value: fmt(ds.classes), color: s[0], note: fmt(classes.length) + " with annotations" },
      { key: "Largest class", value: classes.length ? pct(classes[0].share) : "-", color: s[1], note: classes.length ? classes[0].name + " · " + plural(classes[0].annotations, "annotation") : "" },
      { key: "80% coverage", value: coverage && coverage.milestones["80"] ? fmt(coverage.milestones["80"]) : "-", unit: "classes", color: s[2], note: "hold 80% of annotations" },
      { key: "Under 1%", value: fmt(rare), unit: "classes", color: s[3], note: "below 1% of annotations" }
    ]);

    var opi = stats && stats.objectsPerImage.count ? stats.objectsPerImage : null;
    var area = stats && stats.boxArea.count ? stats.boxArea : null;
    var heat = data.boxCenters;
    kpis("kpi-geometry", [
      { key: "Objects / image", value: opi ? round(opi.median) : "-", color: s[0], note: opi ? "median · mean " + round(opi.mean) + " · max " + round(opi.max) : "" },
      { key: "Median box", value: area ? pct(area.median) : "-", color: s[1], note: area ? "of image area · mean " + pct(area.mean) : "" },
      { key: "Empty images", value: fmt(ds.emptyImages), color: s[2], note: ds.images ? pct(ds.emptyImages / ds.images) + " of the dataset" : "" },
      { key: "Busiest cell", value: heat ? fmt(heat.max) : "-", unit: "boxes", color: s[3], note: heat ? "in one " + heat.grid + "x" + heat.grid + " cell" : "" }
    ]);

    var affected = data.issues.filter(function (issue) { return issue.where; }).length;
    kpis("kpi-findings", [
      { key: "Errors", value: fmt(counts.ERROR || 0), color: sevColor("ERROR"), note: "objectively broken" },
      { key: "Warnings", value: fmt(counts.WARNING || 0), color: sevColor("WARNING"), note: "worth reviewing" },
      { key: "Info", value: fmt(counts.INFO || 0), color: sevColor("INFO"), note: "observations" },
      { key: "Checks fired", value: fmt(data.issueTypes.length), color: cssVar("--s3"), note: affected ? fmt(affected) + " findings point at a file" : "" }
    ]);
  }

  function renderHero() {
    var counts = data.severityCounts;
    byId("hero-count").textContent = fmt(data.issuesTotal);
    byId("hero-label").textContent = data.issuesTotal === 1 ? "finding" : "findings";

    var meter = clear(byId("severity-meter"));
    var legend = clear(byId("severity-legend"));
    var sum = SEVERITIES.reduce(function (acc, key) { return acc + (counts[key] || 0); }, 0);

    SEVERITIES.forEach(function (key) {
      var count = counts[key] || 0;
      if (sum > 0 && count > 0) {
        meter.appendChild(el("span", { class: "seg", style: "width:" + (count / sum) * 100 + "%;background:" + sevColor(key) }));
      }
      var item = el("li");
      item.appendChild(el("span", { class: "dot", style: "--c:" + sevColor(key) }));
      item.appendChild(el("span", { class: "n" }, fmt(count)));
      item.appendChild(el("span", { class: "k" }, key.charAt(0) + key.slice(1).toLowerCase()));
      legend.appendChild(item);
    });
    if (sum === 0) meter.appendChild(el("span", { class: "seg", style: "width:100%;background:var(--grid)" }));

    var host = clear(byId("top-problems"));
    var ranked = data.issues.filter(function (i) { return i.severity !== "INFO"; }).slice(0, 4);
    if (!ranked.length) {
      host.appendChild(el("li", { class: "clean" },
        data.issuesTotal ? "Nothing blocking: only observations." : "No findings. This dataset looks clean."));
      return;
    }
    ranked.forEach(function (issue) {
      var item = el("li");
      var button = el("button", { type: "button", style: "--c:" + sevColor(issue.severity) });
      button.appendChild(el("span", { class: "ic", "aria-hidden": "true" }, SEV[issue.severity].icon));
      button.appendChild(el("span", { class: "msg", title: issue.message }, issue.message));
      button.appendChild(el("span", { class: "go" }, "→"));
      button.addEventListener("click", function () {
        state.type = issue.code;
        byId("type-filter").value = issue.code;
        focusFindings();
      });
      item.appendChild(button);
      host.appendChild(item);
    });
  }

  function renderImpact() {
    var impact = data.impact;
    if (!impact || !impact.items.length) { hide("card-impact"); return; }

    var fixed = {};
    var list = clear(byId("impact-list"));
    var value = byId("impact-value");
    var bar = byId("impact-bar");
    var note = byId("impact-note");

    function squash(raw) { return impact.cap * (1 - Math.exp(-raw / impact.cap)); }

    function update() {
      var remainingRaw = 0;
      var fixedRaw = 0;
      impact.items.forEach(function (item) {
        if (fixed[item.code]) fixedRaw += item.gain; else remainingRaw += item.gain;
      });
      var total = squash(remainingRaw + fixedRaw) || 0;
      var captured = total - squash(remainingRaw);
      value.textContent = "+" + squash(remainingRaw).toFixed(1) + "%";
      bar.style.width = (total ? (captured / total) * 100 : 0) + "%";
      bar.style.background = cssVar("--good");
      note.textContent = total
        ? "+" + captured.toFixed(1) + "% of an estimated +" + total.toFixed(1) + "% captured"
        : "Nothing to recover: no findings.";
    }

    impact.items.forEach(function (item) {
      var row = el("li", { class: "impact-row", style: "--c:" + sevColor(item.severity) });
      row.dataset.tip = item.code + "\n" + plural(item.count, "finding") + " · touching " +
        pct(item.share) + " of " + item.scale + "\nweight " + item.weight +
        " → estimated +" + item.gain.toFixed(1) + "%";

      var box = el("input", { type: "checkbox" });
      box.addEventListener("change", function () {
        fixed[item.code] = box.checked;
        row.className = "impact-row" + (box.checked ? " done" : "");
        update();
      });
      var what = el("span", { class: "what" });
      what.appendChild(el("span", { class: "dot" }));
      what.appendChild(el("span", { class: "code", title: item.code }, item.code));

      row.appendChild(box);
      row.appendChild(what);
      row.appendChild(el("span", { class: "gain" }, "+" + item.gain.toFixed(1) + "%"));
      row.addEventListener("click", function (event) {
        if (event.target !== box) { box.checked = !box.checked; box.dispatchEvent(new Event("change")); }
      });
      list.appendChild(row);
    });

    byId("impact-formula").textContent =
      "Estimate only: " + impact.formula + ". CVFlow has no model to measure; treat it as a priority hint.";
    update();
  }

  /* --------------------------------------------------------------- charts */

  function drawCharts() {
    var classes = data.classes;
    var accent = cssVar("--s1");

    // Findings by type: one bar per check, colored by its worst severity.
    if (data.issueTypes.length) {
      var types = data.issueTypes;
      bars("chart-types", {
        horizontal: true,
        labels: types.map(function (r) { return shorten(r.code, 20); }),
        titles: types.map(function (r) { return r.code; }),
        data: types.map(function (r) { return r.count; }),
        colors: types.map(function (r) { return sevColor(r.severity); }),
        unit: "findings",
        footers: types.map(function (r) { return r.severity.toLowerCase() + " · select to filter"; }),
        onSelect: function (index) {
          state.type = types[index].code;
          byId("type-filter").value = state.type;
          focusFindings();
        }
      });
    } else { hide("card-types"); }

    // Images with the most findings: stacked by severity, click to open.
    if (data.topImages.length) {
      var rows = data.topImages;
      bars("chart-images", {
        horizontal: true,
        stacked: true,
        labels: rows.map(function (r) { return shorten(r.name, 16, true); }),
        datasets: SEVERITIES.map(function (key) {
          return {
            label: key.charAt(0) + key.slice(1).toLowerCase(),
            data: rows.map(function (r) { return r.counts[key] || 0; }),
            backgroundColor: sevColor(key)
          };
        }),
        titles: rows.map(function (r) { return r.path; }),
        footers: rows.map(function () { return "select to open the image"; }),
        onSelect: function (index) { openEditor(rows[index].path); }
      });
    } else { hide("card-images"); }

    // Splits
    if (data.splits.length > 1) {
      bars("chart-splits", {
        labels: data.splits.map(function (r) { return r.name; }),
        data: data.splits.map(function (r) { return r.images; }),
        colors: accent,
        unit: "images",
        footers: data.splits.map(function (r) { return plural(r.annotations, "annotation"); })
      });
    } else { hide("card-splits"); }

    // Class distribution
    if (classes.length) {
      var limit = 20;
      var expanded = false;
      var toggle = byId("classes-toggle");
      byId("classes-sub").textContent = "Annotations per class · " + plural(classes.length, "class", "classes");

      var draw = function () {
        var shown = expanded ? classes : classes.slice(0, limit);
        byId("classes-wrap").style.height = Math.max(210, shown.length * 22 + 40) + "px";
        if (charts["chart-classes"]) charts["chart-classes"].destroy();
        bars("chart-classes", {
          horizontal: true,
          labels: shown.map(function (c) { return shorten(c.name, 22); }),
          titles: shown.map(function (c) { return c.name; }),
          data: shown.map(function (c) { return c.annotations; }),
          colors: accent,
          unit: "annotations",
          footers: shown.map(function (c) { return pct(c.share) + " of annotations · in " + plural(c.images, "image"); })
        });
        toggle.textContent = expanded ? "Show top " + limit : "Show all " + fmt(classes.length);
      };
      if (classes.length > limit) {
        toggle.hidden = false;
        toggle.onclick = function () { expanded = !expanded; draw(); };
      }
      draw();

      table(byId("classes-table"), [
        { label: "Class", get: function (r) { return r.name; } },
        { label: "Id", num: true, get: function (r) { return r.id; } },
        { label: "Annotations", num: true, get: function (r) { return fmt(r.annotations); } },
        { label: "Share", num: true, get: function (r) { return pct(r.share); } },
        { label: "Images", num: true, get: function (r) { return fmt(r.images); } }
      ], classes);
    } else { hide("card-classes"); }

    // Class coverage curve
    var coverage = data.classCoverage;
    if (coverage && coverage.points.length >= 3) {
      areaLine("chart-coverage", {
        labels: coverage.points.map(function (p) { return p.classes; }),
        data: coverage.points.map(function (p) { return p.share * 100; }),
        max: 100,
        yFmt: function (v) { return v + "%"; },
        valueFmt: function (v) { return v.toFixed(1) + "% of annotations"; },
        titles: coverage.points.map(function (p) { return "Top " + plural(p.classes, "class", "classes"); })
      });
      var parts = ["50", "80", "95"].filter(function (k) { return coverage.milestones[k]; }).map(function (k) {
        return k + "% in " + plural(coverage.milestones[k], "class", "classes");
      });
      byId("coverage-caption").textContent = parts.length ? "Annotations covered: " + parts.join(" · ") : "";
    } else { hide("card-coverage"); }

    // Objects per image
    if (data.objectsPerImage.length) {
      var stats = data.stats;
      bars("chart-opi", {
        labels: data.objectsPerImage.map(function (b) { return b.label; }),
        data: data.objectsPerImage.map(function (b) { return b.count; }),
        colors: accent,
        unit: "images",
        titles: data.objectsPerImage.map(function (b) { return b.range + " objects"; })
      });
      if (stats && stats.objectsPerImage.count) {
        var opi = stats.objectsPerImage;
        byId("opi-sub").textContent = "min " + round(opi.min) + " · median " + round(opi.median) +
          " · mean " + round(opi.mean) + " · max " + round(opi.max);
      }
      table(byId("opi-table"), [
        { label: "Objects", get: function (r) { return r.range; } },
        { label: "Images", num: true, get: function (r) { return fmt(r.count); } }
      ], data.objectsPerImage);
    } else { hide("card-opi"); }

    // Box size
    if (data.boxAreas.length) {
      bars("chart-area", {
        labels: data.boxAreas.map(function (b) { return b.label; }),
        data: data.boxAreas.map(function (b) { return b.count; }),
        colors: accent,
        unit: "boxes",
        titles: data.boxAreas.map(function (b) { return b.range + " of image area"; })
      });
      if (data.stats && data.stats.boxArea.count) {
        byId("area-sub").textContent = "median " + pct(data.stats.boxArea.median) +
          " · mean " + pct(data.stats.boxArea.mean) + " · axis in % of image area";
      }
      table(byId("area-table"), [
        { label: "Box area", get: function (r) { return r.range; } },
        { label: "Boxes", num: true, get: function (r) { return fmt(r.count); } }
      ], data.boxAreas);
    } else { hide("card-area"); }

    // Box shape
    if (data.boxShapes) {
      bars("chart-shape", {
        labels: data.boxShapes.bins.map(function (b) { return b.label; }),
        data: data.boxShapes.bins.map(function (b) { return b.count; }),
        colors: accent,
        unit: "boxes",
        titles: data.boxShapes.bins.map(function (b) { return b.range; })
      });
      byId("shape-sub").textContent = data.boxShapes.basis === "pixels"
        ? "Width ÷ height in pixels: tall left, wide right"
        : "Width ÷ height relative to the frame (image dimensions unknown)";
      table(byId("shape-table"), [
        { label: "Shape", get: function (r) { return r.range; } },
        { label: "Boxes", num: true, get: function (r) { return fmt(r.count); } }
      ], data.boxShapes.bins);
    } else { hide("card-shape"); }

    renderHeatmap();
  }

  function renderHeatmap() {
    var heat = data.boxCenters;
    if (!heat) { hide("card-heat"); return; }
    var grid = heat.grid;
    var host = clear(byId("heat-grid"));
    host.style.setProperty("--grid-size", grid);
    var cell = 100 / grid;

    heat.cells.forEach(function (count, index) {
      var row = Math.floor(index / grid);
      var column = index % grid;
      // sqrt so the middle of the ramp carries typical counts: a linear map
      // against a busy outlier cell leaves everything else in the palest step.
      var step = count === 0 ? 0 : Math.min(7, Math.ceil(Math.sqrt(count / heat.max) * 7));
      var node = el("span", {
        class: "heat-cell",
        tabindex: "0",
        style: (step ? "background:var(--seq-" + step + ");" : "") +
          "animation-delay:" + Math.min(index * 2, 220) + "ms"
      });
      node.dataset.tip =
        "x " + Math.round(column * cell) + "-" + Math.round((column + 1) * cell) + "% · " +
        "y " + Math.round(row * cell) + "-" + Math.round((row + 1) * cell) + "%\n" +
        plural(count, "box", "boxes") + (heat.total ? " (" + pct(count / heat.total) + ")" : "");
      host.appendChild(node);
    });

    var legend = clear(byId("heat-legend"));
    legend.appendChild(el("span", null, "0"));
    var swatches = el("span", { class: "swatches" });
    for (var step = 1; step <= 7; step++) swatches.appendChild(el("i", { style: "background:var(--seq-" + step + ")" }));
    legend.appendChild(swatches);
    legend.appendChild(el("span", null, fmt(heat.max) + " boxes per cell"));
    byId("heat-sub").textContent = "Box centers across the frame · " + grid + "x" + grid +
      " cells · " + plural(heat.total, "box", "boxes");
  }

  /* -------------------------------------------------------------- findings */

  var state = {
    severities: {}, type: "", split: "", query: "", sort: "severity", desc: true, limit: PAGE
  };
  SEVERITIES.forEach(function (key) { state.severities[key] = true; });

  function matches(issue) {
    if (!state.severities[issue.severity]) return false;
    if (state.type && issue.code !== state.type) return false;
    if (state.split && issue.split !== state.split) return false;
    if (state.query) {
      var hay = (issue.message + " " + issue.code + " " + issue.where + " " + issue.why).toLowerCase();
      if (hay.indexOf(state.query) === -1) return false;
    }
    return true;
  }

  var SEV_RANK = { ERROR: 2, WARNING: 1, INFO: 0 };

  function sortFindings(list) {
    var key = state.sort;
    var sorted = list.slice().sort(function (a, b) {
      if (key === "code") return a.code.localeCompare(b.code) || SEV_RANK[b.severity] - SEV_RANK[a.severity];
      if (key === "path") return String(a.where).localeCompare(String(b.where));
      return SEV_RANK[b.severity] - SEV_RANK[a.severity] || a.code.localeCompare(b.code);
    });
    return state.desc ? sorted : sorted.reverse();
  }

  function focusFindings() {
    state.limit = PAGE;
    renderFindings();
    showTab("findings");
    byId("findings").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  /* One finding, one block: severity, the headline, why it was flagged, a
     thumbnail of the image it points at, and where it is. */
  function findingCard(issue) {
    var hasImages = issue.images && issue.images.length;
    var openable = Boolean(issue.path || hasImages) && api.enabled;
    var card = el(openable ? "button" : "div", {
      class: "finding-card",
      style: "--c:" + sevColor(issue.severity)
    });
    if (openable) card.setAttribute("type", "button");

    var head = el("div", { class: "fc-head" });
    var sev = el("span", { class: "sev", style: "--c:" + sevColor(issue.severity) + ";--tint:" + SEV[issue.severity].tint });
    sev.appendChild(el("span", { class: "ic", "aria-hidden": "true" }, SEV[issue.severity].icon));
    sev.appendChild(el("span", null, issue.severity));
    head.appendChild(sev);
    if (issue.split) head.appendChild(el("span", { class: "fc-code" }, issue.split));
    head.appendChild(el("span", { class: "fc-code" }, issue.code));
    card.appendChild(head);

    var body = el("div", { class: "fc-body" });
    var thumbPath = issue.path || (hasImages ? issue.images[0] : null);
    if (thumbPath && api.enabled) {
      var thumb = el("img", {
        class: "fc-thumb", loading: "lazy", alt: "",
        src: "api/image?path=" + encodeURIComponent(thumbPath)
      });
      thumb.addEventListener("error", function () { thumb.remove(); });
      body.appendChild(thumb);
    }
    var text = el("div", { class: "fc-text" });
    text.appendChild(el("div", { class: "fc-msg", title: issue.message }, issue.message));
    if (issue.why) text.appendChild(el("div", { class: "fc-why" }, issue.why));
    body.appendChild(text);
    card.appendChild(body);

    if (issue.suggestion) card.appendChild(el("div", { class: "fc-next" }, "Next: " + issue.suggestion));

    var foot = el("div", { class: "fc-foot" });
    foot.appendChild(el("span", { class: "fc-where", title: issue.where },
      issue.where || (hasImages ? plural(issue.images.length, "image") + " affected" : "dataset-wide")));
    if (openable) {
      foot.appendChild(el("span", { class: "fc-open" },
        issue.path ? "Open image" : "See " + plural(issue.images.length, "image")));
    }
    card.appendChild(foot);

    if (openable) {
      card.addEventListener("click", function () {
        if (issue.path) openEditor(issue.path, issue);
        else openGallery(issue);
      });
    }
    return card;
  }

  function renderFindings() {
    var host = clear(byId("finding-list"));
    var filtered = sortFindings(data.issues.filter(matches));
    var shown = filtered.slice(0, state.limit);

    if (!filtered.length) {
      host.appendChild(el("p", { class: "empty" },
        data.issuesTotal ? "No findings match these filters." : "No findings. This dataset looks clean."));
    } else {
      shown.forEach(function (issue) { host.appendChild(findingCard(issue)); });
    }
    byId("show-more").hidden = shown.length >= filtered.length;
    byId("list-count").textContent = filtered.length
      ? "Showing " + fmt(shown.length) + " of " + fmt(filtered.length) + " findings" : "";
  }

  function syncSeverityChips() {
    Array.prototype.forEach.call(byId("severity-filters").children, function (chip) {
      chip.setAttribute("aria-pressed", state.severities[chip.dataset.severity] ? "true" : "false");
    });
  }

  function wireFilters() {
    var chips = clear(byId("severity-filters"));
    SEVERITIES.forEach(function (key) {
      var chip = el("button", {
        class: "chip", type: "button", "aria-pressed": "true", "data-severity": key,
        style: "--c:" + sevColor(key)
      });
      chip.appendChild(el("span", { class: "dot" }));
      chip.appendChild(el("span", null, key.charAt(0) + key.slice(1).toLowerCase()));
      chip.appendChild(el("span", { class: "n" }, fmt(data.severityCounts[key] || 0)));
      chip.addEventListener("click", function () {
        state.severities[key] = !state.severities[key];
        chip.setAttribute("aria-pressed", state.severities[key] ? "true" : "false");
        state.limit = PAGE;
        renderFindings();
      });
      chips.appendChild(chip);
    });

    var select = byId("type-filter");
    clear(select).appendChild(el("option", { value: "" }, "All checks"));
    data.issueTypes.forEach(function (row) {
      select.appendChild(el("option", { value: row.code }, row.code + " (" + fmt(row.count) + ")"));
    });
    select.addEventListener("change", function (e) { state.type = e.target.value; state.limit = PAGE; renderFindings(); });

    var splits = byId("split-filter");
    clear(splits).appendChild(el("option", { value: "" }, "All splits"));
    data.dataset.splits.forEach(function (name) {
      splits.appendChild(el("option", { value: name }, name));
    });
    splits.parentNode.hidden = !data.dataset.splits.length;
    splits.addEventListener("change", function (e) { state.split = e.target.value; state.limit = PAGE; renderFindings(); });

    byId("sort-by").addEventListener("change", function (e) { state.sort = e.target.value; renderFindings(); });
    byId("sort-dir").addEventListener("click", function (event) {
      state.desc = !state.desc;
      event.currentTarget.textContent = state.desc ? "↓" : "↑";
      renderFindings();
    });

    byId("search").addEventListener("input", function (e) {
      state.query = e.target.value.trim().toLowerCase();
      state.limit = PAGE;
      renderFindings();
    });
    byId("show-more").addEventListener("click", function () { state.limit += PAGE; renderFindings(); });
    byId("reset-filters").addEventListener("click", function () {
      SEVERITIES.forEach(function (key) { state.severities[key] = true; });
      state.type = ""; state.split = ""; state.query = ""; state.sort = "severity"; state.desc = true;
      state.limit = PAGE;
      select.value = ""; splits.value = ""; byId("search").value = ""; byId("sort-by").value = "severity";
      byId("sort-dir").textContent = "↓";
      syncSeverityChips();
      renderFindings();
    });

    byId("findings-sub").textContent = data.issuesTruncated
      ? "Most severe first. " + fmt(data.issuesTruncated) + " further findings omitted."
      : "Most severe first";
  }

  /* ---------------------------------------------------- cards: tips + zoom */

  function wireCards() {
    var layer = byId("zoom-layer");
    var slot = byId("zoom-slot");
    var placeholder = el("div");
    var open = null;

    function close() {
      if (!open) return;
      placeholder.parentNode.replaceChild(open, placeholder);
      layer.hidden = true;
      open.querySelector("[data-zoom]").textContent = "⤢";
      resizeCharts();
      open = null;
    }

    function expand(card) {
      if (open === card) { close(); return; }
      close();
      card.parentNode.replaceChild(placeholder, card);
      clear(slot).appendChild(card);
      layer.hidden = false;
      card.querySelector("[data-zoom]").textContent = "✕";
      card.querySelector("[data-zoom]").focus();
      open = card;
      resizeCharts();
    }

    Array.prototype.forEach.call(document.querySelectorAll(".card[data-title]"), function (card) {
      card.dataset.tip = card.dataset.title + "\n" + card.dataset.desc;
      var tools = card.querySelector(".card-tools");
      if (!tools) {
        tools = el("div", { class: "card-tools" });
        var head = card.querySelector(".card-head");
        if (head) head.appendChild(tools);
        else { tools.style.cssText = "position:absolute;top:12px;right:12px"; card.appendChild(tools); }
      }
      var chartId = card.querySelector("canvas") ? card.querySelector("canvas").id : null;
      var download = el("button", {
        class: "icon-btn", type: "button",
        "aria-label": "Download " + card.dataset.title
      }, "↓");
      download.dataset.tip = "Download as PNG or JSON";
      download.addEventListener("click", function (event) {
        event.stopPropagation();
        byId("tip").hidden = true;
        offerDownload(card, chartId);
      });
      tools.appendChild(download);

      var zoom = el("button", {
        class: "icon-btn", type: "button", "data-zoom": "",
        "aria-label": "Expand " + card.dataset.title
      }, "⤢");
      zoom.dataset.tip = "Expand to full screen";
      zoom.addEventListener("click", function (event) {
        event.stopPropagation();
        byId("tip").hidden = true;
        expand(card);
      });
      tools.appendChild(zoom);
    });

    byId("zoom-backdrop").addEventListener("click", close);
    byId("zoom-close").addEventListener("click", close);
    document.addEventListener("keydown", function (event) { if (event.key === "Escape") close(); });
  }

  function saveBlob(blob, filename) {
    var url = URL.createObjectURL(blob);
    var link = el("a", { href: url, download: filename });
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function slug(text) {
    return String(text).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  }

  /* Both halves of a chart: the picture, and the numbers behind it. The PNG is
     drawn onto the card's surface colour so it is not transparent-on-white. */
  function offerDownload(card, chartId) {
    var name = slug(data.dataset.name + "-" + card.dataset.title);
    var menu = el("div", { class: "dl-menu" });
    var chart = chartId ? charts[chartId] : null;

    function option(label, run) {
      var button = el("button", { class: "dl-opt", type: "button" }, label);
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        run();
        menu.remove();
      });
      menu.appendChild(button);
    }

    option("Download PNG", function () {
      var canvas = card.querySelector("canvas");
      if (canvas) {
        var out = document.createElement("canvas");
        out.width = canvas.width;
        out.height = canvas.height;
        var ctx = out.getContext("2d");
        ctx.fillStyle = cssVar("--surface-1");
        ctx.fillRect(0, 0, out.width, out.height);
        ctx.drawImage(canvas, 0, 0);
        out.toBlob(function (blob) { if (blob) saveBlob(blob, name + ".png"); });
        return;
      }
      window.alert("This card has no chart canvas to export.");
    });

    option("Download JSON", function () {
      var payload = { chart: card.dataset.title, dataset: data.dataset.name };
      if (chart) {
        payload.labels = chart.data.labels;
        payload.datasets = chart.data.datasets.map(function (set) {
          return { label: set.label || null, data: set.data };
        });
      } else if (card.id === "card-heat") {
        payload.heatmap = data.boxCenters;
      } else if (card.id === "card-impact") {
        payload.impact = data.impact;
      }
      saveBlob(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }), name + ".json");
    });

    card.appendChild(menu);
    setTimeout(function () {
      document.addEventListener("click", function once() {
        menu.remove();
        document.removeEventListener("click", once);
      });
    }, 0);
  }

  function resizeCharts() {
    Object.keys(charts).forEach(function (id) {
      if (charts[id]) { try { charts[id].resize(); } catch (e) { /* detached */ } }
    });
  }

  /* ---------------------------------------------------------- the roller */

  var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-tab]"));

  function showTab(name) {
    var found = false;
    tabs.forEach(function (tab) {
      var active = tab.dataset.tab === name;
      found = found || active;
      tab.setAttribute("aria-selected", active ? "true" : "false");
      var panel = byId(tab.dataset.tab);
      if (panel) panel.hidden = !active;
      if (active) byId("crumb-view").textContent = tab.textContent.trim().replace(/\s+\d[\d,]*$/, "");
    });
    if (!found) return showTab("overview");
    if (window.history && window.history.replaceState) window.history.replaceState(null, "", "#" + name);
    resizeCharts();
    return undefined;
  }

  function wireRoller() {
    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () { showTab(tab.dataset.tab); });
      tab.addEventListener("keydown", function (event) {
        var step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
        if (!step) return;
        event.preventDefault();
        var next = tabs[(index + step + tabs.length) % tabs.length];
        next.focus();
        showTab(next.dataset.tab);
      });
    });
    window.addEventListener("hashchange", function () {
      showTab((window.location.hash || "#overview").slice(1));
    });
    showTab((window.location.hash || "#overview").slice(1));
  }

  /* Auto-hide sidebar: the choice sticks, because someone who collapses it
     wants it collapsed next time too. */
  function wireRail() {
    var app = document.querySelector(".app");
    var button = byId("rail-toggle");

    function paint(railed) {
      app.className = "app" + (railed ? " rail" : "");
      // Only the state changes: writing textContent here would replace the
      // panel glyph in the markup with a character.
      button.classList.toggle("is-railed", railed);
      button.dataset.tip = railed ? "Show the sidebar" : "Collapse the sidebar";
      button.setAttribute("aria-label", button.dataset.tip);
      resizeCharts();
    }

    var saved = null;
    try { saved = localStorage.getItem("cvflow-rail"); } catch (e) { /* file:// */ }
    paint(saved === "1");

    button.addEventListener("click", function () {
      var railed = app.className.indexOf("rail") === -1;
      paint(railed);
      try { localStorage.setItem("cvflow-rail", railed ? "1" : "0"); } catch (e) { /* file:// */ }
    });
  }

  /* --------------------------------------------------------------- tooltip */

  function wireTooltip() {
    var tip = byId("tip");

    function show(target, event) {
      var text = target.dataset.tip;
      if (!text) return;
      tip.textContent = text;
      tip.hidden = false;
      var box = target.getBoundingClientRect();
      var size = tip.getBoundingClientRect();
      var left, top;
      if (event && event.clientX !== undefined && (box.height > 180 || box.width > 420)) {
        left = event.clientX + 16;
        top = event.clientY + 18;
      } else {
        left = box.left + box.width / 2 - size.width / 2;
        top = box.top - size.height - 10;
        if (top < 8) top = box.bottom + 10;
      }
      tip.style.left = Math.min(Math.max(8, left), window.innerWidth - size.width - 8) + "px";
      tip.style.top = Math.min(Math.max(8, top), window.innerHeight - size.height - 8) + "px";
    }
    function hideTip() { tip.hidden = true; }

    document.addEventListener("mouseover", function (event) {
      var target = event.target.closest ? event.target.closest("[data-tip]") : null;
      if (target) show(target, event); else hideTip();
    });
    document.addEventListener("mousemove", function (event) {
      if (tip.hidden) return;
      var target = event.target.closest ? event.target.closest("[data-tip]") : null;
      if (target) show(target, event);
    });
    document.addEventListener("focusin", function (event) {
      var target = event.target.closest ? event.target.closest("[data-tip]") : null;
      if (target) show(target); else hideTip();
    });
    document.addEventListener("focusout", hideTip);
    window.addEventListener("scroll", hideTip, true);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideTip(); });
  }

  /* ----------------------------------------------------------------- theme */

  function currentTheme() {
    var root = document.documentElement;
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function wireTheme() {
    var root = document.documentElement;
    var button = byId("theme-toggle");
    var icon = button.querySelector("[data-theme-icon]");

    function stored(value) {
      try {
        if (value === undefined) return localStorage.getItem("cvflow-theme");
        localStorage.setItem("cvflow-theme", value);
      } catch (e) { /* file:// without storage: theme just won't persist */ }
      return null;
    }
    function paint() {
      var dark = currentTheme() === "dark";
      icon.textContent = dark ? "☀️" : "🌙";
      button.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
      button.dataset.tip = dark ? "Switch to light theme" : "Switch to dark theme";
    }

    var saved = stored();
    if (saved === "dark" || saved === "light") root.dataset.theme = saved;
    paint();

    button.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      stored(next);
      paint();
      // Charts bake their colours in, so they are rebuilt against the new theme.
      Object.keys(charts).forEach(function (id) { if (charts[id]) charts[id].destroy(); });
      charts = {};
      applyChartDefaults();
      drawCharts();
      renderHero();
      renderKpis();
      renderSideGroups();
      renderFindings();
      wireFilters();
      syncSeverityChips();
    });
  }

  /* ------------------------------------------------- image + box editor */

  var editor = {
    path: null, boxes: [], original: [], selected: -1, image: null,
    drag: null, writable: false, issue: null, flagged: [], token: 0
  };

  function editorStatus(text, kind) {
    var node = byId("editor-status");
    node.textContent = text || "";
    node.className = "editor-status" + (kind ? " " + kind : "");
  }

  /* Class hues deliberately exclude the red and orange slots: red means
     "this is the box the finding is about", and nothing else may look like it. */
  function boxColor(classId) {
    var slots = ["--s1", "--s2", "--s3", "--s5", "--s7", "--s8"];
    return cssVar(slots[Math.abs(classId) % slots.length]);
  }

  /* Datasets without a class list get inferred names like {0: "0"}, which read
     as a value on a box label: spell those out, same as the charts do. */
  function className(classId) {
    var name = api.classes ? api.classes[classId] : null;
    return name && name !== String(classId) ? name : "class " + classId;
  }

  function drawEditor() {
    var canvas = byId("editor-canvas");
    var ctx = canvas.getContext("2d");
    if (!editor.image) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(editor.image, 0, 0, canvas.width, canvas.height);

    editor.boxes.forEach(function (box, index) {
      var x = box.x_min * canvas.width;
      var y = box.y_min * canvas.height;
      var w = (box.x_max - box.x_min) * canvas.width;
      var h = (box.y_max - box.y_min) * canvas.height;
      var shape = box.points && box.points.length > 2 ? box.points : null;
      // The box a finding points at is drawn in the critical red; every other
      // class keeps its own hue, so "what is wrong" reads before "what is it".
      var flagged = editor.flagged.indexOf(index) !== -1;
      var color = flagged ? cssVar("--critical") : boxColor(box.class_id);
      var active = index === editor.selected;

      ctx.lineWidth = active || flagged ? 3 : 2;
      ctx.strokeStyle = color;

      if (shape) {
        // A mask or an oriented box is drawn as itself. Its extent stays as a
        // faint dashed guide, because that is what the box-level checks read.
        ctx.beginPath();
        shape.forEach(function (point, at) {
          var px = point[0] * canvas.width;
          var py = point[1] * canvas.height;
          if (at === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        });
        ctx.closePath();
        ctx.stroke();
        ctx.save();
        ctx.globalAlpha = flagged ? 0.2 : 0.12;
        ctx.fillStyle = color;
        ctx.fill();
        ctx.restore();

        ctx.save();
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1;
        ctx.globalAlpha = 0.55;
        ctx.strokeRect(x, y, w, h);
        ctx.restore();
      } else {
        ctx.strokeRect(x, y, w, h);
        if (flagged) {
          ctx.save();
          ctx.globalAlpha = 0.14;
          ctx.fillStyle = color;
          ctx.fillRect(x, y, w, h);
          ctx.restore();
        }
      }
      if (active) {
        ctx.fillStyle = color.replace(")", ", 0.16)").replace("rgb", "rgba");
        ctx.globalAlpha = 0.18;
        ctx.fillRect(x, y, w, h);
        ctx.globalAlpha = 1;
        // corner handles
        [[x, y], [x + w, y], [x, y + h], [x + w, y + h]].forEach(function (p) {
          ctx.fillStyle = color;
          ctx.fillRect(p[0] - 4, p[1] - 4, 8, 8);
        });
      }
      var label = (flagged ? "! " : "") + className(box.class_id);
      ctx.font = "600 12px Archivo, system-ui, sans-serif";
      var pad = 4;
      var width = ctx.measureText(label).width + pad * 2;
      ctx.fillStyle = color;
      ctx.fillRect(x, Math.max(0, y - 17), width, 17);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, x + pad, Math.max(11, y - 5));
    });
  }

  /* Box size in the units an annotator thinks in: pixels of the actual image,
     with a plain word for how big that is relative to the frame. */
  function shapeWord(box) {
    if (!box.points || box.points.length < 3) return "box";
    return box.points.length === 4 && api.task === "obb" ? "oriented box" : "mask";
  }

  function boxSize(box) {
    var w = box.x_max - box.x_min;
    var h = box.y_max - box.y_min;
    if (editor.image) {
      var px = Math.round(w * editor.image.naturalWidth);
      var py = Math.round(h * editor.image.naturalHeight);
      return px + " x " + py + " px";
    }
    return Math.round(w * 100) + " x " + Math.round(h * 100) + " of 100";
  }

  function sizeWord(box) {
    var area = (box.x_max - box.x_min) * (box.y_max - box.y_min);
    if (area < 0.001) return "tiny";
    if (area < 0.01) return "small";
    if (area < 0.1) return "medium";
    if (area < 0.5) return "large";
    return "fills the frame";
  }

  function renderBoxList() {
    var host = clear(byId("box-list"));
    if (!editor.boxes.length) {
      host.appendChild(el("li", { class: "editor-hint" }, "No boxes on this image."));
    }
    editor.boxes.forEach(function (box, index) {
      var row = el("li", { class: "box-row" + (index === editor.selected ? " active" : ""), style: "--c:" + boxColor(box.class_id) });
      row.dataset.tip = className(box.class_id) + "\n" + boxSize(box) + " (" + sizeWord(box) + ")";
      row.appendChild(el("span", { class: "swatch" }));
      row.appendChild(el("span", { class: "name" }, className(box.class_id)));
      row.appendChild(el("span", { class: "dims" }, boxSize(box)));
      row.addEventListener("click", function () { selectBox(index); });
      host.appendChild(row);
    });

    var select = byId("box-class");
    if (!select.options.length) {
      var ids = Object.keys(api.classes);
      if (!ids.length) ids = data.classes.map(function (c) { return String(c.id); });
      ids.forEach(function (id) { select.appendChild(el("option", { value: id }, className(Number(id)))); });
    }
    if (editor.selected >= 0) select.value = String(editor.boxes[editor.selected].class_id);
  }

  function selectBox(index) {
    editor.selected = index;
    renderBoxList();
    drawEditor();
  }

  function markDirty() {
    editorStatus(editor.writable ? "Unsaved changes" : "Read-only: start CVFlow with --serve to save");
  }

  /* Fixes CVFlow can actually apply here, per check. Anything not listed can
     only be fixed by hand or outside the app, and says so. */
  function fixesFor(issue) {
    var index = issue.annotationIndex;
    var hasBox = index !== null && index !== undefined && editor.boxes[index];
    var fixes = [];

    if (hasBox) {
      fixes.push({ label: "Select box", ghost: true, run: function () { selectBox(index); } });
    }
    if (hasBox && (issue.code === "box-out-of-bounds" || issue.code === "negative-coordinates")) {
      fixes.push({
        label: "Clamp into frame",
        run: function () {
          var box = editor.boxes[index];
          box.x_min = Math.min(Math.max(box.x_min, 0), 1);
          box.y_min = Math.min(Math.max(box.y_min, 0), 1);
          box.x_max = Math.min(Math.max(box.x_max, 0), 1);
          box.y_max = Math.min(Math.max(box.y_max, 0), 1);
          selectBox(index);
          markDirty();
        }
      });
    }
    if (hasBox && ["tiny-box", "huge-box", "degenerate-box", "duplicate-annotation"].indexOf(issue.code) !== -1) {
      fixes.push({
        label: "Delete this box",
        run: function () {
          editor.boxes.splice(index, 1);
          editor.selected = -1;
          renderBoxList();
          drawEditor();
          markDirty();
        }
      });
    }
    if (hasBox && issue.code === "invalid-class-id") {
      fixes.push({
        label: "Reassign class",
        run: function () { selectBox(index); byId("box-class").focus(); }
      });
    }
    if (issue.code === "empty-image") {
      fixes.push({ label: "Add a box", run: function () { byId("box-add").click(); } });
    }
    return fixes;
  }

  function renderEditorIssues() {
    var host = clear(byId("editor-issues"));
    var mine = editor.path
      ? data.issues.filter(function (issue) { return issue.path === editor.path; })
      : (editor.issue ? [editor.issue] : []);

    if (!mine.length) {
      host.appendChild(el("li", { class: "issue-empty" }, "Nothing was flagged on this image."));
      return;
    }

    mine.forEach(function (issue) {
      var card = el("li", {
        class: "issue-card" + (issue === editor.issue ? " active" : ""),
        style: "--c:" + sevColor(issue.severity)
      });
      var top = el("div", { class: "top" });
      var sev = el("span", { class: "sev", style: "--c:" + sevColor(issue.severity) + ";--tint:" + SEV[issue.severity].tint });
      sev.appendChild(el("span", { class: "ic", "aria-hidden": "true" }, SEV[issue.severity].icon));
      sev.appendChild(el("span", null, issue.severity));
      top.appendChild(sev);
      top.appendChild(el("span", { class: "code" }, issue.code));
      card.appendChild(top);
      card.appendChild(el("div", { class: "msg" }, issue.message));
      if (issue.why) card.appendChild(el("div", { class: "why" }, issue.why));
      if (issue.suggestion) card.appendChild(el("div", { class: "next" }, "Suggested: " + issue.suggestion));

      var fixes = fixesFor(issue);
      if (fixes.length) {
        var row = el("div", { class: "fixes" });
        fixes.forEach(function (fix) {
          var button = el("button", { class: "fix-btn" + (fix.ghost ? " ghost" : ""), type: "button" }, fix.label);
          button.addEventListener("click", function (event) {
            event.stopPropagation();
            fix.run();
            renderEditorIssues();
          });
          row.appendChild(button);
        });
        card.appendChild(row);
      } else {
        card.appendChild(el("div", { class: "next" }, "No in-app fix for this one: it needs the file itself."));
      }

      card.addEventListener("click", function () {
        editor.issue = issue;
        if (issue.annotationIndex !== null && issue.annotationIndex !== undefined) {
          selectBox(issue.annotationIndex);
        }
        renderEditorIssues();
      });
      host.appendChild(card);
    });
  }

  /* A finding that is not about one box (empty images, duplicates, leakage, a
     rare class) still concerns real files. This shows them, so every finding
     can be looked at rather than just read. */
  function openGallery(issue) {
    if (!api.enabled) {
      window.alert("Viewing images needs the local server: cvflow inspect <dataset> --serve");
      return;
    }
    byId("editor-layer").hidden = false;
    byId("editor-title").textContent = issue.message;
    byId("editor-path").textContent = plural(issue.images.length, "image") + " this finding covers";
    editor.issue = issue;

    resetEditor();
    editor.token++;
    byId("flag-note").hidden = true;
    var stage = byId("editor-stage");
    stage.classList.add("gallery");
    var grid = clear(byId("editor-gallery"));
    issue.images.forEach(function (path) {
      var tile = el("button", { class: "gal-tile", type: "button", title: path });
      var img = el("img", { loading: "lazy", alt: "", src: "api/image?path=" + encodeURIComponent(path) });
      img.addEventListener("error", function () { tile.classList.add("missing"); img.remove(); });
      tile.appendChild(img);
      tile.appendChild(el("span", { class: "gal-name" }, fileName(path)));
      tile.addEventListener("click", function () { openEditor(path, issue); });
      grid.appendChild(tile);
    });

    clear(byId("box-list")).appendChild(el("li", { class: "editor-hint" },
      "Select an image above to open it with its boxes."));
    renderEditorIssues();
  }

  /* Wipe whatever the last open left behind. Without this, a gallery (or a
     slow or failed load) stays on screen and opening a second finding looks
     like it reopened the first one. */
  function resetEditor() {
    editor.path = null;
    editor.issue = null;
    editor.boxes = [];
    editor.original = [];
    editor.flagged = [];
    editor.selected = -1;
    editor.image = null;
    editor.drag = null;

    var canvas = byId("editor-canvas");
    canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = 0;
    canvas.height = 0;

    clear(byId("box-list"));
    clear(byId("editor-issues"));
    clear(byId("editor-gallery"));
    clear(byId("box-class"));
    byId("editor-stage").classList.remove("gallery");
    byId("editor-save").disabled = true;
    editorStatus("");
  }

  function openEditor(path, issue) {
    if (!api.enabled) {
      window.alert("Viewing images needs the local server: cvflow inspect <dataset> --serve");
      return;
    }
    resetEditor();
    // Every open takes a token; a response carrying an older one is dropped,
    // so a slow load can never paint over the image opened after it.
    var token = ++editor.token;

    byId("editor-layer").hidden = false;
    byId("flag-note").hidden = false;
    byId("editor-title").textContent = fileName(path);
    byId("editor-path").textContent = path;
    editorStatus("Loading...");
    editor.path = path;
    editor.issue = issue || null;

    fetch("api/annotations?path=" + encodeURIComponent(path))
      .then(function (r) { return r.ok ? r.json() : r.json().then(function (e) { throw new Error(e.error || "failed"); }); })
      .then(function (payload) {
        if (token !== editor.token) return;
        editor.boxes = payload.boxes.map(function (b) { return Object.assign({}, b); });
        editor.original = payload.boxes.map(function (b) { return Object.assign({}, b); });
        editor.flagged = data.issues.filter(function (i) {
          return i.path === path && i.annotationIndex !== null && i.annotationIndex !== undefined;
        }).map(function (i) { return i.annotationIndex; });
        editor.writable = payload.writable;
        byId("editor-save").disabled = !payload.writable;
        var img = new Image();
        img.onload = function () {
          if (token !== editor.token) return;
          var canvas = byId("editor-canvas");
          var maxW = Math.min(img.naturalWidth, 900);
          var scale = maxW / img.naturalWidth;
          canvas.width = Math.round(img.naturalWidth * scale);
          canvas.height = Math.round(img.naturalHeight * scale);
          editor.image = img;
          if (editor.issue && editor.issue.annotationIndex !== null &&
              editor.issue.annotationIndex !== undefined) {
            editor.selected = editor.issue.annotationIndex;
          }
          renderBoxList();
          renderEditorIssues();
          drawEditor();
          editorStatus(payload.writable ? "" : "Read-only (" + payload.format + " labels are not written back)");
        };
        img.onerror = function () {
          if (token === editor.token) editorStatus("Could not load the image file", "failed");
        };
        img.src = "api/image?path=" + encodeURIComponent(path);
      })
      .catch(function (error) {
        if (token === editor.token) editorStatus(String(error.message || error), "failed");
      });
  }

  function closeEditor() {
    byId("editor-layer").hidden = true;
    editor.image = null;
  }

  function canvasPoint(event) {
    var canvas = byId("editor-canvas");
    var rect = canvas.getBoundingClientRect();
    return {
      x: Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1),
      y: Math.min(Math.max((event.clientY - rect.top) / rect.height, 0), 1)
    };
  }

  function hitTest(point) {
    var handle = 0.012;
    for (var i = editor.boxes.length - 1; i >= 0; i--) {
      var b = editor.boxes[i];
      var near = Math.abs(point.x - b.x_max) < handle && Math.abs(point.y - b.y_max) < handle;
      if (near) return { index: i, mode: "resize" };
      if (point.x >= b.x_min && point.x <= b.x_max && point.y >= b.y_min && point.y <= b.y_max) {
        return { index: i, mode: "move" };
      }
    }
    return null;
  }

  function wireEditor() {
    var canvas = byId("editor-canvas");

    canvas.addEventListener("pointerdown", function (event) {
      if (!editor.image) return;
      if (!editor.writable) {
        editorStatus(api.task && api.task !== "detect"
          ? "Read-only: " + api.task + " annotations are shown as drawn, not edited here."
          : "Read-only dataset.");
        return;
      }
      canvas.setPointerCapture(event.pointerId);
      var point = canvasPoint(event);
      var hit = hitTest(point);
      if (hit) {
        selectBox(hit.index);
        editor.drag = { mode: hit.mode, start: point, box: Object.assign({}, editor.boxes[hit.index]) };
      } else {
        // Drag on empty canvas draws a new box.
        var classId = editor.boxes.length ? editor.boxes[editor.boxes.length - 1].class_id : 0;
        editor.boxes.push({ class_id: classId, x_min: point.x, y_min: point.y, x_max: point.x, y_max: point.y });
        selectBox(editor.boxes.length - 1);
        editor.drag = { mode: "draw", start: point };
      }
    });

    canvas.addEventListener("pointermove", function (event) {
      if (!editor.drag || editor.selected < 0) return;
      var point = canvasPoint(event);
      var box = editor.boxes[editor.selected];
      if (editor.drag.mode === "move") {
        var dx = point.x - editor.drag.start.x;
        var dy = point.y - editor.drag.start.y;
        var base = editor.drag.box;
        var w = base.x_max - base.x_min;
        var h = base.y_max - base.y_min;
        box.x_min = Math.min(Math.max(base.x_min + dx, 0), 1 - w);
        box.y_min = Math.min(Math.max(base.y_min + dy, 0), 1 - h);
        box.x_max = box.x_min + w;
        box.y_max = box.y_min + h;
      } else {
        box.x_max = Math.max(point.x, box.x_min + 0.002);
        box.y_max = Math.max(point.y, box.y_min + 0.002);
      }
      drawEditor();
    });

    canvas.addEventListener("pointerup", function () {
      if (!editor.drag) return;
      editor.drag = null;
      renderBoxList();
      markDirty();
    });

    byId("box-class").addEventListener("change", function (event) {
      if (editor.selected < 0) return;
      editor.boxes[editor.selected].class_id = Number(event.target.value);
      renderBoxList();
      drawEditor();
      markDirty();
    });

    byId("box-delete").addEventListener("click", function () {
      if (editor.selected < 0) return;
      editor.boxes.splice(editor.selected, 1);
      editor.selected = -1;
      renderBoxList();
      drawEditor();
      markDirty();
    });

    byId("box-add").addEventListener("click", function () {
      editor.boxes.push({ class_id: 0, x_min: 0.4, y_min: 0.4, x_max: 0.6, y_max: 0.6 });
      selectBox(editor.boxes.length - 1);
      markDirty();
    });

    byId("editor-revert").addEventListener("click", function () {
      editor.boxes = editor.original.map(function (b) { return Object.assign({}, b); });
      editor.selected = -1;
      renderBoxList();
      drawEditor();
      editorStatus("Reverted to the file on disk");
    });

    byId("editor-save").addEventListener("click", function () {
      editorStatus("Saving…");
      fetch("api/annotations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: editor.path, boxes: editor.boxes })
      })
        .then(function (r) { return r.json().then(function (body) { if (!r.ok) throw new Error(body.error || "failed"); return body; }); })
        .then(function (body) {
          editor.original = editor.boxes.map(function (b) { return Object.assign({}, b); });
          editorStatus("Saved to " + body.written, "saved");
        })
        .catch(function (error) { editorStatus("Save failed: " + (error.message || error), "failed"); });
    });

    byId("editor-close").addEventListener("click", closeEditor);
    byId("editor-backdrop").addEventListener("click", closeEditor);
    document.addEventListener("keydown", function (event) {
      if (byId("editor-layer").hidden) return;
      if (event.key === "Escape") closeEditor();
      if (event.key === "Delete" || event.key === "Backspace") byId("box-delete").click();
    });
  }

  /* Only the served dashboard can read image bytes or write labels; the
     standalone HTML file has no backend, so the editor stays closed. */
  function detectApi() {
    if (!/^https?:$/.test(window.location.protocol) || !window.fetch) return Promise.resolve();
    return fetch("api/editor")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (payload) {
        if (payload) api = payload;
        // Findings render before this resolves; redraw so the rows that can
        // open an image say so.
        renderFindings();
        // ?open=<path> deep-links straight to one image, so a URL can point a
        // teammate at the exact file that needs fixing.
        var match = /[?&]open=([^&]+)/.exec(window.location.search);
        if (match && api.enabled) openEditor(decodeURIComponent(match[1]));
      })
      .catch(function () { /* static page */ });
  }

  /* ------------------------------------------------------------------ boot */

  applyChartDefaults();
  renderChrome();
  renderKpis();
  renderHero();
  renderImpact();
  wireFilters();
  renderSideGroups();
  renderFindings();
  drawCharts();
  wireCards();
  wireRoller();
  wireRail();
  wireTooltip();
  wireTheme();
  wireEditor();
  detectApi();
  window.addEventListener("resize", resizeCharts);
})();
