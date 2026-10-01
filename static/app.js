"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const W = 1534,
    H = 1025;
  const RANKS = [
    { name: "Bronze", min: 0 },
    { name: "Silver", min: 750 },
    { name: "Gold", min: 1500 },
    { name: "Diamond", min: 3000 },
    { name: "Mythic", min: 4500 },
    { name: "Legendary", min: 6000 },
    { name: "Masters", min: 8500 },
    { name: "Pro", min: 11250 },
  ];
  const TIERS = [
    ["Bronze I", 0],
    ["Bronze II", 250],
    ["Bronze III", 500],
    ["Silver I", 750],
    ["Silver II", 1000],
    ["Silver III", 1250],
    ["Gold I", 1500],
    ["Gold II", 2000],
    ["Gold III", 2500],
    ["Diamond I", 3000],
    ["Diamond II", 3500],
    ["Diamond III", 4000],
    ["Mythic I", 4500],
    ["Mythic II", 5000],
    ["Mythic III", 5500],
    ["Legendary I", 6000],
    ["Legendary II", 6750],
    ["Legendary III", 7500],
    ["Masters I", 8500],
    ["Masters II", 9500],
    ["Masters III", 10500],
    ["Pro", 11250],
  ];
  // Measured on the original 2048 × 1367 screenshot, scaled to the 1534 × 1025 clean plate.
  const defaults = {
    score: { x: 217, y: 219, size: 35 },
    gained: { x: 214, y: 253, size: 34 },
    left: { x: 92, y: 195, size: 101 },
    right: { x: 344, y: 195, size: 101 },
    lower: { x: 89, y: 264, size: 23 },
    upper: { x: 340, y: 264, size: 23 },
  };
  const canvas = $("canvas"),
    ctx = canvas.getContext("2d");
  const plate = document.createElement("canvas");
  plate.width = W;
  plate.height = H;
  const pc = plate.getContext("2d");
  let positions = JSON.parse(JSON.stringify(defaults)),
    selected = 0,
    busy = false,
    previewToken = 0,
    controller = null;
  let templateData = null,
    fontData = null,
    fontFamily = "Game",
    icons = {},
    musicFile = null,
    finalFile = null;
  const image = new Image();
  const ranksFor = (score) => {
    let i = 0;
    for (let j = 0; j < RANKS.length; j++) if (score >= RANKS[j].min) i = j;
    return [RANKS[i], RANKS[Math.min(i + 1, RANKS.length - 1)]];
  };
  const tierFor = (score) => {
    let i = 0;
    for (let j = 0; j < TIERS.length; j++) if (score >= TIERS[j][1]) i = j;
    return [TIERS[i][0], TIERS[Math.min(i + 1, TIERS.length - 1)][0]];
  };
  const rangeFor = (score) => {
    let i = 0;
    for (let j = 0; j < TIERS.length; j++) if (score >= TIERS[j][1]) i = j;
    return [TIERS[i][1], TIERS[i + 1]?.[1] ?? null];
  };
  const makeScene = (score, gained = 100) => {
    const [lower, upper] = rangeFor(score);
    return {
      score,
      gained,
      lower,
      upper,
      seconds: 2,
      leftIcon: "auto",
      rightIcon: "auto",
      thresholds: true,
      showGain: true,
      imageData: null,
      img: null,
      imageName: "",
    };
  };
  let scenes = Array.from({ length: 5 }, (_, i) =>
    makeScene(2683 + i * 100, i ? 100 : 116),
  );
  const fields = [
    "score",
    "gained",
    "lower",
    "upper",
    "seconds",
    "leftIcon",
    "rightIcon",
    "thresholds",
    "showGain",
  ];
  const status = (s) => ($("status").textContent = s);
  const dims = () => {
    const q = Number($("quality").value);
    return $("format").value === "vertical"
      ? [q, Math.round((q * 16) / 9)]
      : [Math.round(q * 1.5), q];
  };
  const duration = () =>
    scenes.reduce((v, s) => v + s.seconds, 0) +
    ($("celebration").value === "none"
      ? 0
      : $("celebration").value === "custom"
        ? "your ending"
        : 3);
  function caption(c, v, x, y, size, color = "#fff") {
    if (!String(v).trim()) return;
    c.save();
    c.font = `${size}px ${fontFamily}, Impact, sans-serif`;
    c.textAlign = "center";
    c.textBaseline = "middle";
    c.lineJoin = "round";
    c.lineWidth = Math.max(3, size * 0.16);
    c.strokeStyle = "#10131c";
    c.strokeText(String(v), x, y);
    c.fillStyle = color;
    c.fillText(String(v), x, y);
    c.restore();
  }
  function imageFit(c, source, cover = false) {
    const w = c.canvas.width,
      h = c.canvas.height,
      iw = source.naturalWidth || source.width,
      ih = source.naturalHeight || source.height;
    if (!iw || !ih) return;
    const k = cover ? Math.max(w / iw, h / ih) : Math.min(w / iw, h / ih);
    c.drawImage(source, (w - iw * k) / 2, (h - ih * k) / 2, iw * k, ih * k);
  }
  function rankIcon(scene, side) {
    const choice = scene[side + "Icon"];
    if (!choice) return null;
    if (choice === "auto") {
      const [current, next] = tierFor(scene.score);
      if (side === "right" && current === next) return null;
      const tier = side === "left" ? current : next,
        rank = tier.replace(/ (?:I|II|III)$/, "");
      const matches = Object.values(icons).filter((item) => item.rank === rank);
      return (
        (
          matches.find((item) => item.tier === tier) ||
          matches.find((item) => !item.tier)
        )?.img || null
      );
    }
    return icons[choice]?.img || null;
  }
  function paintPlate(scene) {
    const source = scene.img || image;
    pc.clearRect(0, 0, W, H);
    pc.drawImage(source, 0, 0, W, H);
    caption(
      pc,
      scene.score,
      positions.score.x,
      positions.score.y,
      positions.score.size,
    );
    if (scene.showGain)
      caption(
        pc,
        "+" + scene.gained,
        positions.gained.x,
        positions.gained.y,
        positions.gained.size,
        "#89f342",
      );
    for (const side of ["left", "right"]) {
      const im = rankIcon(scene, side);
      if (!im) continue;
      const p = positions[side],
        k = Math.min(p.size / im.width, p.size / im.height),
        w = im.width * k,
        h = im.height * k;
      pc.drawImage(im, p.x - w / 2, p.y - h / 2, w, h);
    }
    if (scene.thresholds) {
      caption(
        pc,
        scene.lower,
        positions.lower.x,
        positions.lower.y,
        positions.lower.size,
        "#d2e5ff",
      );
      if (scene.upper !== null)
        caption(
          pc,
          scene.upper,
          positions.upper.x,
          positions.upper.y,
          positions.upper.size,
          "#d2e5ff",
        );
    }
  }
  function compose(c, scene, celebration = false) {
    const w = c.canvas.width,
      h = c.canvas.height;
    c.clearRect(0, 0, w, h);
    c.fillStyle = "#000";
    c.fillRect(0, 0, w, h);
    if (celebration) {
      const pro = $("celebration").value === "pro";
      let g = c.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.65);
      g.addColorStop(0, pro ? "#563210" : "#291559");
      g.addColorStop(1, "#05030c");
      c.fillStyle = g;
      c.fillRect(0, 0, w, h);
      caption(c, "✦", w / 2, h * 0.43, w * 0.28, pro ? "#ffdc66" : "#e9d2ff");
      caption(
        c,
        pro ? "PRO" : "MASTERS",
        w / 2,
        h * 0.59,
        w * 0.13,
        pro ? "#fff0b1" : "#f7e5ff",
      );
      caption(c, "NEW RANK", w / 2, h * 0.69, w * 0.047);
      return;
    }
    paintPlate(scene);
    if (h > w) {
      if ($("backdrop").value === "blur") {
        c.save();
        c.filter = "blur(26px)";
        imageFit(c, scene.img || image, true);
        c.restore();
        c.fillStyle = "#080d1a88";
        c.fillRect(0, 0, w, h);
      }
    }
    imageFit(c, plate);
    const message = $("caption").value.trim();
    if (message) {
      caption(c, message, w / 2, h * 0.84, w * 0.048);
      if (h > w) caption(c, message, w / 2, h * 0.1, w * 0.048);
    }
  }
  function resize() {
    const [w, h] = dims();
    canvas.width = w;
    canvas.height = h;
  }
  function showFrame(scene = scenes[selected]) {
    if (!image.naturalWidth) return;
    resize();
    compose(ctx, scene);
    $("frameLabel").textContent =
      `Scene ${selected + 1} · ${canvas.width} × ${canvas.height}`;
    updateDuration();
  }
  function updateDuration() {
    const d = duration();
    $("durationLabel").textContent =
      `${scenes.length} scenes · ${typeof d === "string" ? scenes.reduce((v, s) => v + s.seconds, 0) + "s + ending" : d + "s"}`;
  }
  function refreshIcons() {
    for (const side of ["leftIcon", "rightIcon"]) {
      const el = $(side);
      el.replaceChildren(
        new Option("Auto (uploaded icons)", "auto"),
        new Option("No icon", ""),
      );
      Object.entries(icons).forEach(([id, item]) =>
        el.add(new Option(item.name, id)),
      );
    }
  }
  function selectScene(index) {
    selected = index;
    const s = scenes[index];
    for (const key of fields)
      $(key)[typeof s[key] === "boolean" ? "checked" : "value"] = s[key];
    $("sceneTitle").textContent = `Scene ${index + 1}`;
    const [rank, next] = tierFor(s.score);
    $("rankName").textContent = rank + (rank === next ? "" : " → " + next);
    $("sceneImageName").textContent =
      s.imageName || "Uses the approved template";
    timeline();
    showFrame();
  }
  function timeline() {
    const host = $("timeline");
    host.replaceChildren();
    scenes.forEach((s, i) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "scene" + (i === selected ? " active" : "");
      item.innerHTML = `<small>SCENE ${i + 1} · ${s.seconds}s</small><strong>${s.score}</strong><span>+${s.gained} points</span><div style="width: 100%; height: 3px; background: ${i === selected ? 'var(--accent)' : '#475569'}; margin-top: 8px; border-radius: 4px;"></div>`;
      item.disabled = busy;
      item.onclick = () => selectScene(i);
      host.append(item);
    });
    $("add").disabled = busy || scenes.length >= 12;
    $("delete").disabled = busy || scenes.length <= 1;
    updateDuration();
  }
  function lock(on) {
    busy = on;
    document
      .querySelectorAll(
        "aside input,aside select,aside button,.timeline-actions button,#play",
      )
      .forEach((el) => (el.disabled = on));
    $("cancel").hidden = !on;
    $("cancel").disabled = false;
    $("progress").hidden = !on;
    timeline();
  }
  function invalidate() {
    if (!busy) $("downloads").hidden = true;
  }
  const fileData = (file) =>
    new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result);
      r.onerror = () => reject(Error("Could not read the file."));
      r.readAsDataURL(file);
    });
  const loadImage = (src) =>
    new Promise((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(Error("Invalid image file."));
      im.src = src;
    });
  function download(blob, name) {
    const url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  function renderPreview() {
    if (busy || !image.naturalWidth) return;
    const token = ++previewToken,
      begin = performance.now(),
      length = scenes.reduce((v, s) => v + s.seconds, 0);
    status("Previewing zoom sequence…");
    function frame(time) {
      if (token !== previewToken) return;
      let t = Math.min(length, (time - begin) / 1000),
        i = 0;
      for (; i < scenes.length - 1 && t >= scenes[i].seconds; i++)
        t -= scenes[i].seconds;
      showFrame(scenes[i]);
      const w = canvas.width,
        h = canvas.height,
        z = 1 + Math.min(1, t / scenes[i].seconds) * 0.11;
      const snapshot = document.createElement("canvas");
      snapshot.width = w;
      snapshot.height = h;
      snapshot.getContext("2d").drawImage(canvas, 0, 0);
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.scale(z, z);
      ctx.drawImage(snapshot, -w / 2, -h / 2);
      ctx.restore();
      $("frameLabel").textContent =
        `Scene ${i + 1} · zoom ${(z * 100).toFixed(0)}%`;
      if ((time - begin) / 1000 < length) requestAnimationFrame(frame);
      else {
        showFrame();
        status("Preview complete.");
      }
    }
    requestAnimationFrame(frame);
  }
  async function exportVideo() {
    if (busy || !image.naturalWidth) return;
    if ($("celebration").value === "custom" && !finalFile) {
      status("Upload your own ending video first.");
      return;
    }
    lock(true);
    $("downloads").hidden = true;
    $("progress").value = 0;
    controller = new AbortController();
    const requestBody = new FormData();
    try {
      const size = dims(),
        manifest = {
          durations: scenes.map((s) => s.seconds),
          size,
          celebration: $("celebration").value,
        };
      const scratch = document.createElement("canvas");
      scratch.width = size[0];
      scratch.height = size[1];
      const sc = scratch.getContext("2d");
      for (let i = 0; i < scenes.length; i++) {
        compose(sc, scenes[i]);
        const png = await new Promise((resolve) =>
          scratch.toBlob(resolve, "image/png"),
        );
        if (!png) throw Error("Could not prepare scene image.");
        requestBody.append("scene" + i, png, `scene${i}.png`);
        $("progress").value = ((i + 1) / (scenes.length + 2)) * 0.4;
        status(`Preparing scene ${i + 1} of ${scenes.length}…`);
      }
      if (["masters", "pro"].includes(manifest.celebration)) {
        compose(sc, scenes[scenes.length - 1], true);
        const png = await new Promise((resolve) =>
          scratch.toBlob(resolve, "image/png"),
        );
        requestBody.append("endcard", png, "endcard.png");
      }
      if (manifest.celebration === "custom")
        requestBody.append("final", finalFile, finalFile.name);
      if (musicFile) requestBody.append("music", musicFile, musicFile.name);
      requestBody.append("manifest", JSON.stringify(manifest));
      status("Rendering zoom shots and joining the ending video…");
      $("progress").value = 0.6;
      const response = await fetch("/api/render", {
        method: "POST",
        body: requestBody,
        signal: controller.signal,
      });
      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({ error: "Rendering failed." }));
        throw Error(error.error || "Rendering failed.");
      }
      const output = await response.blob();
      const a = $("download");
      if (a.dataset.url) URL.revokeObjectURL(a.dataset.url);
      a.href = URL.createObjectURL(output);
      a.dataset.url = a.href;
      a.download = "rank-clip.mp4";
      $("downloads").hidden = false;
      $("progress").value = 1;
      status(
        `MP4 ready 🍿 · ${(output.size / 1048576).toFixed(1)} MB · ${scenes.length} zoom shots${finalFile && manifest.celebration === "custom" ? " + your ending" : ""}.`,
      );
    } catch (e) {
      status(e.name === "AbortError" ? "Export cancelled." : e.message);
    } finally {
      lock(false);
      controller = null;
      showFrame();
    }
  }
  for (const key of fields)
    $(key).addEventListener("input", () => {
      const s = scenes[selected];
      s[key] =
        typeof s[key] === "boolean"
          ? $(key).checked
          : ["leftIcon", "rightIcon"].includes(key)
            ? $(key).value
            : Math.max(0, Math.min(999999, Number($(key).value) || 0));
      if (key === "score") {
        s.gained = Math.min(s.gained, s.score);
        [s.lower, s.upper] = rangeFor(s.score);
        $("gained").value = s.gained;
        $("lower").value = s.lower;
        $("upper").value = s.upper;
      }
      if (key === "gained") s.gained = Math.min(s.gained, s.score);
      timeline();
      const [rank, next] = tierFor(s.score);
      $("rankName").textContent = rank + (next !== rank ? " → " + next : "");
      showFrame();
      invalidate();
    });
  $("generate").onclick = () => {
    const first = Math.max(0, Number($("startScore").value) || 0),
      gain = Math.max(
        1,
        Math.min(9999, Number($("suggestedGain").value) || 100),
      );
    scenes = Array.from({ length: 5 }, (_, i) =>
      makeScene(first + i * gain, gain),
    );
    selectScene(0);
    invalidate();
  };
  $("add").onclick = () => {
    if (scenes.length >= 12) return;
    scenes.push(
      makeScene(
        scenes[scenes.length - 1].score + scenes[scenes.length - 1].gained,
        scenes[scenes.length - 1].gained,
      ),
    );
    selectScene(scenes.length - 1);
    invalidate();
  };
  $("duplicate").onclick = () => {
    if (scenes.length >= 12) return;
    scenes.splice(selected + 1, 0, { ...scenes[selected] });
    selectScene(selected + 1);
    invalidate();
  };
  $("delete").onclick = () => {
    if (scenes.length <= 1) return;
    scenes.splice(selected, 1);
    selectScene(Math.min(selected, scenes.length - 1));
    invalidate();
  };
  for (const key of ["celebration", "format", "quality", "caption", "backdrop"])
    $(key).addEventListener("input", () => {
      showFrame();
      invalidate();
    });
  $("play").onclick = renderPreview;
  $("export").onclick = exportVideo;
  $("cancel").onclick = () => controller?.abort();
  $("png").onclick = () => {
    showFrame();
    canvas.toBlob((b) => download(b, "rank-frame.png"), "image/png");
  };
  $("icons").onchange = async (e) => {
    try {
      for (const file of e.target.files) {
        const data = await fileData(file),
          img = await loadImage(data),
          id = "icon-" + Date.now() + "-" + Object.keys(icons).length;
        const name = file.name.replace(/\.[^.]+$/, "");
        const normal = name.replace(/[_-]+/g, " ");
        const rank =
          RANKS.find((r) => normal.toLowerCase().includes(r.name.toLowerCase()))
            ?.name || null;
        const tier =
          TIERS.find(
            ([label]) => label.toLowerCase() === normal.toLowerCase(),
          )?.[0] || null;
        icons[id] = { name, rank, tier, data, img };
      }
      refreshIcons();
      selectScene(selected);
      status(
        "Rank icons uploaded. Auto uses icon filenames that match rank names.",
      );
    } catch (e) {
      status(e.message);
    }
  };
  $("templateFile").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const data = await fileData(f);
      await loadImage(data);
      templateData = data;
      image.src = data;
      $("templateName").textContent = f.name;
      invalidate();
    } catch (err) {
      status(err.message);
    }
  };
  $("sceneFile").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const data = await fileData(f);
      const img = await loadImage(data);
      scenes[selected].imageData = data;
      scenes[selected].img = img;
      scenes[selected].imageName = f.name;
      $("sceneImageName").textContent = f.name;
      showFrame();
      invalidate();
      status(`Scene ${selected + 1} image uploaded.`);
    } catch (err) {
      status(err.message);
    }
  };
  $("musicFile").onchange = (e) => {
    musicFile = e.target.files[0] || null;
    $("musicName").textContent = musicFile?.name || "Optional background audio";
    invalidate();
  };
  $("finalFile").onchange = (e) => {
    finalFile = e.target.files[0] || null;
    $("finalName").textContent =
      finalFile?.name || "MP4 / WebM · up to 60 seconds";
    if (finalFile) $("celebration").value = "custom";
    updateDuration();
    invalidate();
  };
  async function useFont(data) {
    const face = new FontFace("UserGame", `url(${data})`);
    await face.load();
    document.fonts.add(face);
    fontFamily = "UserGame";
    showFrame();
  }
  $("fontFile").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      fontData = await fileData(f);
      await useFont(fontData);
      $("fontName").textContent = f.name;
    } catch {
      status("Could not load that font.");
    }
  };
  function positionsUI() {
    const host = $("positions");
    host.replaceChildren();
    for (const [key, p] of Object.entries(positions)) {
      const title = document.createElement("p");
      title.className = "hint";
      title.textContent = key;
      host.append(title);
      const row = document.createElement("div");
      row.className = "row";
      for (const axis of ["x", "y", "size"]) {
        const label = document.createElement("label");
        label.textContent = axis;
        const input = document.createElement("input");
        input.type = "number";
        input.value = p[axis];
        input.min = axis === "size" ? 1 : 0;
        input.max = axis === "size" ? 300 : axis === "x" ? W : H;
        input.oninput = () => {
          p[axis] = Math.max(
            Number(input.min),
            Math.min(Number(input.max), Number(input.value) || 0),
          );
          showFrame();
          invalidate();
        };
        label.append(input);
        row.append(label);
      }
      host.append(row);
    }
  }
  $("resetPositions").onclick = () => {
    positions = JSON.parse(JSON.stringify(defaults));
    positionsUI();
    showFrame();
  };
  $("save").onclick = () => {
    const data = {
      version: 3,
      scenes: scenes.map(({ img, ...s }) => s),
      positions,
      icons: Object.fromEntries(
        Object.entries(icons).map(([id, { img, ...item }]) => [id, item]),
      ),
      templateData,
      fontData,
      settings: Object.fromEntries(
        ["celebration", "format", "quality", "caption", "backdrop"].map((k) => [
          k,
          $(k).value,
        ]),
      ),
    };
    download(
      new Blob([JSON.stringify(data)], { type: "application/json" }),
      "rank-project.json",
    );
    status(
      "Project saved. Re-upload the music and ending video after reopening.",
    );
  };
  $("projectFile").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (
        ![1, 2, 3].includes(data.version) ||
        !Array.isArray(data.scenes) ||
        data.scenes.length < 1 ||
        data.scenes.length > 12
      )
        throw Error("Invalid project.");
      const imported = [];
      for (const item of data.scenes) {
        const s = {
          ...makeScene(
            Math.max(0, Number(item.score) || 0),
            Math.max(0, Number(item.gained) || 0),
          ),
          ...item,
          img: null,
        };
        [s.lower, s.upper] = rangeFor(s.score);
        if (data.version < 3) {
          s.thresholds = true;
          s.showGain = true;
        }
        if (s.imageData) s.img = await loadImage(s.imageData);
        imported.push(s);
      }
      const importedIcons = {};
      for (const [id, item] of Object.entries(data.icons || {}))
        importedIcons[id] = { ...item, img: await loadImage(item.data) };
      if (data.templateData) await loadImage(data.templateData);
      scenes = imported;
      icons = importedIcons;
      positions = JSON.parse(JSON.stringify(defaults));
      for (const key of Object.keys(defaults))
        for (const axis of ["x", "y", "size"]) {
          const v = Number(data.positions?.[key]?.[axis]);
          if (data.version >= 3 && Number.isFinite(v)) positions[key][axis] = v;
        }
      for (const k of [
        "celebration",
        "format",
        "quality",
        "caption",
        "backdrop",
      ])
        if (data.settings?.[k] !== undefined) $(k).value = data.settings[k];
      templateData = data.templateData || null;
      image.src = templateData || "/template.png";
      if (data.fontData) {
        fontData = data.fontData;
        await useFont(fontData);
      }
      refreshIcons();
      positionsUI();
      selectScene(0);
      status("Project loaded. Re-upload music and the ending video if needed.");
    } catch (err) {
      status("Could not open project: " + err.message);
    }
  };
  image.onload = () => {
    showFrame();
    if ($("status").textContent === "Loading template…")
      status("Ready. Set each scene, then create the MP4.");
  };
  image.onerror = () => status("Could not load the template.");
  image.src = "/template.png";
  positionsUI();
  refreshIcons();
  selectScene(0);
  document.fonts.ready.then(showFrame);
  const healthTimer = setTimeout(() => {
    $("engine").textContent = "OFFLINE";
  }, 8000);
  fetch("/api/health")
    .then((r) => {
      if (!r.ok) throw Error("Health check failed");
      return r.json();
    })
    .then((d) => {
      $("engine").textContent = d.mp4 ? "MP4 READY" : "FFMPEG REQUIRED";
    })
    .catch(() => {
      $("engine").textContent = "OFFLINE";
    })
    .finally(() => clearTimeout(healthTimer));
})();
