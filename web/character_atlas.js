import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const KINDS = ["portrait", "costume", "pose"];
const LABELS = { portrait: "人像", costume: "服装", pose: "姿势" };
const WIDGETS = { portrait: "portrait_id", costume: "costume_id", pose: "pose_id" };
const LABEL_WIDGETS = {
    portrait_id: "人像 ID", costume_id: "服装 ID", pose_id: "姿势 ID",
    style: "画风预设", randomize_on_run: "随机模式", seed: "随机种子", resize_mode: "尺寸处理",
    width: "宽度", height: "高度", flip_pose: "姿势翻转",
};
const previews = new Set();
const stylesheet = document.createElement("link");
stylesheet.rel = "stylesheet";
stylesheet.href = new URL("./character_atlas.css", import.meta.url).href;
document.head.append(stylesheet);

function widget(node, name) { return node.widgets?.find(item => item.name === name); }
function imageURL(kind, id, variant = "thumb") {
    return api.apiURL("/character_atlas/image?" + new URLSearchParams({ kind, id, variant }));
}
async function request(path) {
    const response = await api.fetchApi(path);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "图库请求失败。");
    return result;
}
function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
}
function button(text, className = "ca-button") { return element("button", className, text); }

function openAtlas(node) {
    const dialog = element("dialog", "ca-dialog");
    dialog.setAttribute("aria-label", "角色三合一图库");
    const header = element("header", "ca-header");
    const heading = element("div", "ca-heading");
    heading.append(element("h2", "", "角色三合一图库"), element("span", "ca-muted", "人像 + 服装 + 姿势 · 本地离线素材"));
    const randomAll = button("🎲 随机整套", "ca-button ca-accent");
    const done = button("完成并返回工作流", "ca-button");
    header.append(heading, randomAll, done);
    const recipe = element("div", "ca-recipe");
    const tabs = element("nav", "ca-tabs");
    const toolbar = element("div", "ca-toolbar");
    const search = element("input", "ca-search");
    search.type = "search";
    search.placeholder = "搜索名称、分类、ID、服装关键词…";
    const group = element("select", "ca-select");
    const category = element("select", "ca-select");
    const angle = element("select", "ca-select");
    const randomCurrent = button("随机当前库", "ca-button");
    const reset = button("重置筛选", "ca-button");
    toolbar.append(search, group, category, angle, randomCurrent, reset);
    const status = element("div", "ca-status");
    const grid = element("div", "ca-grid");
    const more = button("加载更多", "ca-button ca-more");
    const error = element("div", "ca-error");
    dialog.append(header, recipe, tabs, toolbar, status, grid, more, error);
    document.body.append(dialog);

    const state = { kind: "portrait", shown: 60, data: {}, filters: {}, selected: {} };
    const loading = {};
    for (const kind of KINDS) {
        state.filters[kind] = { query: "", group: "", category: "", angle: "" };
        state.selected[kind] = String(widget(node, WIDGETS[kind])?.value || "");
    }
    const tabButtons = {};
    for (const kind of KINDS) {
        const tab = button(LABELS[kind], "ca-tab");
        tab.addEventListener("click", () => { state.kind = kind; state.shown = 60; render(); load(kind); });
        tabButtons[kind] = tab;
        tabs.append(tab);
    }

    function setSelected(kind, id) {
        state.selected[kind] = id;
        const target = widget(node, WIDGETS[kind]);
        if (target) { target.value = id; target.callback?.(id); }
        app.canvas?.setDirty(true, true);
        renderRecipe();
        renderCards();
        node.__characterAtlasRefresh?.();
    }
    function filtered(kind) {
        const data = state.data[kind];
        if (!data) return [];
        const filter = state.filters[kind];
        const terms = filter.query.toLowerCase().trim().split(/\s+/).filter(Boolean);
        return data.items.filter(item => {
            if (filter.group && item.group !== filter.group) return false;
            if (filter.category && item.category !== filter.category) return false;
            if (filter.angle && item.angle !== filter.angle) return false;
            const haystack = [item.id, item.title, item.prompt, item.category, item.group, item.angle, ...(item.tags || [])].join(" ").toLowerCase();
            return terms.every(term => haystack.includes(term));
        });
    }
    function fillSelect(select, values, placeholder, selected) {
        select.replaceChildren();
        const first = element("option", "", placeholder); first.value = ""; select.append(first);
        for (const value of values) { const option = element("option", "", value); option.value = value; select.append(option); }
        select.value = selected;
        select.hidden = !values.length;
    }
    function renderRecipe() {
        recipe.replaceChildren();
        for (const kind of KINDS) {
            const slot = element("button", "ca-slot" + (state.kind === kind ? " active" : ""));
            slot.type = "button";
            const image = element("img", "ca-slot-image");
            image.alt = LABELS[kind];
            if (state.selected[kind]) image.src = imageURL(kind, state.selected[kind]);
            const text = element("span", "ca-slot-text");
            const item = state.data[kind]?.items.find(value => value.id === state.selected[kind]);
            text.append(element("strong", "", LABELS[kind]), element("span", "", item?.title || state.selected[kind] || "未选择"));
            slot.append(image, text);
            slot.addEventListener("click", () => { state.kind = kind; state.shown = 60; render(); load(kind); });
            recipe.append(slot);
        }
    }
    function renderCards() {
        const items = filtered(state.kind);
        grid.replaceChildren();
        for (const item of items.slice(0, state.shown)) {
            const card = element("button", "ca-card" + (state.selected[state.kind] === item.id ? " selected" : ""));
            card.type = "button";
            card.title = item.description || item.title;
            const image = element("img", "ca-card-image");
            image.loading = "lazy";
            image.alt = item.title;
            image.src = imageURL(state.kind, item.id);
            const body = element("span", "ca-card-body");
            body.append(element("strong", "ca-card-title", item.title), element("span", "ca-card-meta", [item.group, item.category, item.angle].filter(Boolean).join(" · ")), element("code", "ca-card-id", item.id));
            card.append(image, body);
            card.addEventListener("click", () => setSelected(state.kind, item.id));
            grid.append(card);
        }
        status.textContent = state.data[state.kind] ? `${LABELS[state.kind]} · 筛选出 ${items.length} 条 · 已选 ${state.selected[state.kind] || "无"}` : `正在读取${LABELS[state.kind]}图库…`;
        more.hidden = items.length <= state.shown;
        more.textContent = `加载更多（剩余 ${Math.max(0, items.length - state.shown)}）`;
        for (const kind of KINDS) {
            tabButtons[kind].classList.toggle("active", kind === state.kind);
            tabButtons[kind].textContent = LABELS[kind] + (state.data[kind] ? ` (${state.data[kind].count})` : "");
        }
    }
    function render() {
        const data = state.data[state.kind];
        const filter = state.filters[state.kind];
        search.value = filter.query;
        fillSelect(group, data?.facets.groups || [], "全部分组/体系", filter.group);
        fillSelect(category, data?.facets.categories || [], "全部分类", filter.category);
        fillSelect(angle, data?.facets.angles || [], state.kind === "portrait" ? "人像暂无视角" : "全部视角", filter.angle);
        renderRecipe();
        renderCards();
    }
    async function load(kind) {
        if (state.data[kind]) return;
        if (loading[kind]) return loading[kind];
        state.data[kind] = null;
        error.textContent = "";
        loading[kind] = (async () => {
            try {
                state.data[kind] = await request("/character_atlas/catalogue?kind=" + kind);
                if (!state.selected[kind] && state.data[kind].items[0]) state.selected[kind] = state.data[kind].items[0].id;
            } catch (exc) {
                delete state.data[kind];
                error.textContent = exc.message;
            } finally {
                delete loading[kind];
            }
            if (state.kind === kind) render(); else renderRecipe();
        })();
        return loading[kind];
    }
    function chooseRandom(kind, pool) {
        if (!pool?.length) return;
        setSelected(kind, pool[Math.floor(Math.random() * pool.length)].id);
    }
    search.addEventListener("input", () => { state.filters[state.kind].query = search.value; state.shown = 60; renderCards(); });
    for (const [select, key] of [[group, "group"], [category, "category"], [angle, "angle"]]) {
        select.addEventListener("change", () => { state.filters[state.kind][key] = select.value; state.shown = 60; renderCards(); });
    }
    randomCurrent.addEventListener("click", () => chooseRandom(state.kind, filtered(state.kind)));
    randomAll.addEventListener("click", async () => {
        randomAll.disabled = true;
        try {
            await Promise.all(KINDS.map(kind => load(kind)));
            for (const kind of KINDS) if (state.data[kind]) chooseRandom(kind, state.data[kind].items);
        } finally { randomAll.disabled = false; }
    });
    reset.addEventListener("click", () => { state.filters[state.kind] = { query: "", group: "", category: "", angle: "" }; state.shown = 60; render(); });
    more.addEventListener("click", () => { state.shown += 60; renderCards(); });
    done.addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => dialog.remove(), { once: true });
    dialog.addEventListener("cancel", event => { event.preventDefault(); dialog.close(); });
    dialog.showModal();
    render();
    load("portrait");
}

app.registerExtension({
    name: "ComfyUI_Character-Atlas_ZH.Gallery",
    nodeCreated(node) {
        if ((node.comfyClass || node.type) !== "CharacterAtlas") return;
        for (const input of node.widgets || []) if (LABEL_WIDGETS[input.name]) input.label = LABEL_WIDGETS[input.name];
        const open = node.addWidget("button", "打开三合一图库", null, () => openAtlas(node), { serialize: false });
        open.options = { ...open.options, serialize: false };
        open.serialize = false;
        const host = element("div", "ca-node-preview");
        const images = {};
        for (const kind of KINDS) {
            const cell = element("div", "ca-node-cell");
            const image = element("img", "ca-node-image");
            image.alt = LABELS[kind];
            const caption = element("span", "ca-node-caption", LABELS[kind]);
            cell.append(image, caption); host.append(cell); images[kind] = { image, caption };
        }
        const preview = node.addDOMWidget("character_atlas_preview", "image", host, { serialize: false, hideOnZoom: false });
        preview.computeSize = () => [380, 180];
        preview.options = { ...preview.options, serialize: false, getMinHeight: () => 180, getMaxHeight: () => 180 };
        preview.serialize = false;
        let timer;
        const refresh = () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                for (const kind of KINDS) {
                    const id = String(widget(node, WIDGETS[kind])?.value || "");
                    images[kind].image.src = id ? imageURL(kind, id) : "";
                    images[kind].caption.textContent = `${LABELS[kind]} · ${id || "未选择"}`;
                }
            }, 50);
        };
        node.__characterAtlasRefresh = refresh;
        previews.add(refresh);
        for (const input of node.widgets || []) {
            if (!LABEL_WIDGETS[input.name]) continue;
            const previous = input.callback;
            input.callback = function (...args) { const result = previous?.apply(this, args); refresh(); return result; };
        }
        const removed = node.onRemoved;
        node.onRemoved = function (...args) { clearTimeout(timer); previews.delete(refresh); delete node.__characterAtlasRefresh; return removed?.apply(this, args); };
        node.setSize([Math.max(node.size[0], 400), Math.max(node.size[1], node.computeSize()[1])]);
        refresh();
    },
    afterConfigureGraph() { for (const refresh of previews) refresh(); },
});
