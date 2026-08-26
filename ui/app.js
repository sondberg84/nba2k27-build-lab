const state = { meta: null, height: 75, values: [], focus: "ball_handle" };

const $ = (id) => document.getElementById(id);
const ft = (inches) => `${Math.floor(inches / 12)}-${inches % 12}`;

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error((await response.json()).error);
  return response.json();
}

function buildSliders() {
  const host = $("sliders");
  host.innerHTML = "";
  state.meta.attributes.forEach((name, index) => {
    const row = document.createElement("div");
    row.className = "row";
    row.id = `row-${name}`;

    const label = document.createElement("button");
    label.textContent = name;
    label.onclick = () => { state.focus = name; refreshLadder(); markFocus(); };

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = state.meta.floor;
    slider.max = 99;
    slider.value = state.values[index];
    slider.oninput = () => {
      state.values[index] = Number(slider.value);
      row.querySelector(".num").textContent = slider.value;
      refreshEvaluate();
    };

    const num = document.createElement("span");
    num.className = "num";
    num.textContent = state.values[index];

    row.append(label, slider, num);
    host.append(row);
  });
  markFocus();
}

function markFocus() {
  document.querySelectorAll(".row button").forEach((b) => {
    b.classList.toggle("on", b.textContent === state.focus);
  });
  $("ladderAttr").textContent = state.focus;
}

async function refreshEvaluate() {
  let data;
  try {
    data = await post("/api/evaluate", { height: state.height, values: state.values });
  } catch (error) {
    $("warn").hidden = false;
    $("warn").textContent = error.message;
    return;
  }
  $("overall").textContent = data.overall;
  $("archetype").textContent = data.archetype;
  $("badges").textContent = data.badge_count;
  $("animations").textContent = data.animation_count;
  $("points").textContent = data.points;
  $("tokens").textContent = data.tokens.available ? data.tokens.total : "n/a";

  state.meta.attributes.forEach((name) => {
    const row = $(`row-${name}`);
    if (row) row.classList.remove("over");
  });
  data.illegal.forEach((entry) => {
    const row = $(`row-${entry.attribute}`);
    if (row) row.classList.add("over");
  });

  const messages = [];
  if (data.illegal.length) {
    messages.push(
      data.illegal
        .map((e) => `${e.attribute} ${e.value} is above its ceiling of ${e.ceiling}`)
        .join("; ")
    );
  }
  if (!data.tokens.available) messages.push(data.tokens.reason);
  $("warn").hidden = messages.length === 0;
  $("warn").textContent = messages.join("  ·  ");
}

async function refreshLadder() {
  const data = await post("/api/ladder", {
    height: state.height,
    attribute: state.focus,
  });
  const list = $("ladderSteps");
  list.innerHTML = "";
  let previous = null;
  data.steps.forEach((step) => {
    if (previous !== null && step.rating - previous > 1) {
      const gap = document.createElement("li");
      gap.className = "gap";
      const n = step.rating - previous - 1;
      gap.textContent = `${n} point${n > 1 ? "s" : ""} buying nothing`;
      list.append(gap);
    }
    const unlocks = step.badges.concat(step.animations);
    const item = document.createElement("li");
    const rating = document.createElement("span");
    rating.className = "r";
    rating.textContent = step.rating;
    const text = document.createElement("span");
    text.className = "u";
    text.textContent =
      unlocks.length > 3 ? `${unlocks[0]} (+${unlocks.length - 1} more)` : unlocks.join(", ");
    item.append(rating, text);
    list.append(item);
    previous = step.rating;
  });
}

async function start() {
  state.meta = await (await fetch("/api/meta")).json();
  state.values = new Array(state.meta.attributes.length).fill(state.meta.floor);
  $("commit").textContent = state.meta.commit.slice(0, 12);

  const height = $("height");
  height.min = state.meta.min_height;
  height.max = state.meta.max_height;
  height.value = state.height;
  $("heightOut").textContent = ft(state.height);
  height.oninput = () => {
    state.height = Number(height.value);
    $("heightOut").textContent = ft(state.height);
    refreshEvaluate();
    refreshLadder();
  };

  buildSliders();
  await refreshEvaluate();
  await refreshLadder();
}

start();
