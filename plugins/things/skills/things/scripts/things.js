// JXA uses Things' public scripting dictionary. No database or cloud access.
function run(argv) {
    const r = JSON.parse(argv[0]);
    const app = Application("com.culturedcode.ThingsMac");
    let writeStarted = false;
    let changedID = null;
    let projectIDs = null;
    const has = (key) => Object.prototype.hasOwnProperty.call(r, key);
    const pad = (n) => String(n).padStart(2, "0");
    function day(d) {
        if (!d) return null;
        return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
    }
    function date(s) {
        const p = s.split("-").map(Number);
        const d = new Date(0);
        d.setFullYear(p[0], p[1] - 1, p[2]);
        d.setHours(12, 0, 0, 0);
        return d;
    }
    function byID(collection, id) {
        const item = collection.byId(id);
        if (!item.exists()) throw new Error("No Things item with id " + id);
        return item;
    }
    function link(object) {
        if (!object) return null;
        return object.id();
    }
    function kind(item) {
        if (projectIDs === null) projectIDs = app.projects.id();
        return projectIDs.indexOf(item.id()) >= 0 ? "project" : "todo";
    }
    function serialize(item, notes) {
        const modified = item.modificationDate();
        const result = {
            id: item.id(), type: kind(item), title: item.name(), status: item.status(),
            tags: item.tags.name(), when: day(item.activationDate()), deadline: day(item.dueDate()),
            project_id: link(item.project()), area_id: link(item.area()),
            modified: modified ? modified.toISOString() : null
        };
        if (notes) result.notes = item.notes();
        return result;
    }
    function page(items, serializeItem) {
        const start = r.offset || 0, end = start + (r.limit || 30);
        return {items: items.slice(start, end).map(serializeItem), total: items.length,
            offset: start, next_offset: end < items.length ? end : null};
    }
    function readItems() {
        let items;
        if (r.op === "projects") items = app.projects();
        else if (r.list) {
            const list = app.lists.byName(r.list);
            if (!list.exists()) throw new Error("List not found. Run lists and use its exact localized name.");
            items = list.toDos();
        } else if (r.project_id) items = byID(app.projects, r.project_id).toDos();
        else if (r.area_id) items = byID(app.areas, r.area_id).toDos();
        else items = app.toDos();
        // Return Things' own list membership and order, not an inferred approximation.
        if (r.status && r.status !== "all") items = items.filter(t => t.status() === r.status);
        if (r.op === "projects" && r.area_id) items = items.filter(t => link(t.area()) === r.area_id);
        if (r.tag) items = items.filter(t => t.tags.name().indexOf(r.tag) >= 0);
        if (r.query) {
            const query = r.query.toLocaleLowerCase();
            items = items.filter(t => t.name().toLocaleLowerCase().indexOf(query) >= 0);
        }
        return page(items, t => serialize(t, r.include_notes));
    }
    function plan(item) {
        const changes = {};
        ["title", "notes", "tags", "when", "deadline", "project_id", "area_id"].forEach(key => {
            if (has(key)) changes[key] = r[key];
        });
        const status = {complete: "completed", cancel: "canceled", reopen: "open"}[r.op];
        if (status) changes.status = status;
        return {op: r.op, id: item ? item.id() : null, changes: changes};
    }
    function write() {
        let item = has("id") ? byID(app.toDos, r.id) : null;
        const before = item ? serialize(item, true) : null;
        if (r.expected_modified && before.modified !== r.expected_modified) {
            throw new Error("Item changed since it was read. Read it again before applying this edit.");
        }
        // Resolve every target before making any change.
        const project = r.project_id ? byID(app.projects, r.project_id) : null;
        const area = r.area_id ? byID(app.areas, r.area_id) : null;
        if (project && item && kind(item) === "project") throw new Error("A project cannot be nested inside another project.");
        if (r.tags) {
            const existing = app.tags.name();
            const unknown = r.tags.filter(tag => existing.indexOf(tag) < 0);
            if (unknown.length) throw new Error("Unknown tags: " + unknown.join(", ") + ". Create new tags through Things explicitly first.");
        }
        let destination = null;
        if (r.when === "anytime" || r.when === "someday") {
            destination = app.lists.byName(r.when === "anytime" ? "Anytime" : "Someday");
            if (!destination.exists()) throw new Error("This app uses localized list names; use a documented script with the correct list name.");
        }
        const preview = plan(item);
        if (!r.apply) return {preview: true, before: before, plan: preview};
        writeStarted = true;
        if (!item) {
            const properties = {name: r.title};
            if (has("notes")) properties.notes = r.notes;
            if (has("tags")) properties.tagNames = r.tags.join(", ");
            if (r.deadline) properties.dueDate = date(r.deadline);
            const draft = r.op === "create-project" ? app.Project(properties) : app.ToDo(properties);
            if (project) project.toDos.push(draft);
            else if (area) area.toDos.push(draft);
            else if (r.op === "create-project") app.projects.push(draft);
            else app.toDos.push(draft);
            changedID = draft.id();
            projectIDs = null;
            item = byID(app.toDos, changedID);
        } else {
            changedID = item.id();
            if (has("title")) item.name = r.title;
            if (has("notes")) item.notes = r.notes;
            if (has("tags")) item.tagNames = r.tags.join(", ");
            if (has("deadline")) {
                if (r.deadline === null) app.delete(item.dueDate);
                else item.dueDate = date(r.deadline);
            }
            if (project) item.project = project;
            if (area) item.area = area;
        }
        if (destination) app.move(item, {to: destination});
        else if (r.when) app.schedule(item, {for: date(r.when)});
        if (preview.changes.status) item.status = preview.changes.status;
        const after = serialize(byID(app.toDos, changedID), true);
        const mismatches = [];
        ["title", "notes", "deadline", "project_id", "area_id", "status"].forEach(key => {
            if (Object.prototype.hasOwnProperty.call(preview.changes, key) && after[key] !== preview.changes[key]) mismatches.push(key);
        });
        if (r.tags && JSON.stringify(after.tags.slice().sort()) !== JSON.stringify(r.tags.slice().sort())) mismatches.push("tags");
        if (r.when && !destination && after.when !== r.when) mismatches.push("when");
        if (destination && destination.toDos.id().indexOf(changedID) < 0) mismatches.push("when");
        return {applied: true, verified: mismatches.length === 0, mismatches: mismatches,
            before: before, item: after};
    }
    try {
        let result;
        if (r.op === "status") {
            // Query a protected property, since version alone doesn't prove access.
            result = {version: app.version(), connected: true, list_count: app.lists().length};
        } else if (r.op === "lists") {
            result = {items: app.lists().map(l => ({id: l.id(), title: l.name(), count: l.toDos.length}))};
        } else if (r.op === "areas" || r.op === "tags") {
            const items = r.op === "areas" ? app.areas() : app.tags();
            result = page(items, t => ({id: t.id(), title: t.name()}));
        } else if (["list", "search", "projects"].indexOf(r.op) >= 0) {
            result = readItems();
        } else if (r.op === "get") {
            result = {item: serialize(byID(app.toDos, r.id), r.include_notes)};
        } else if (["create", "create-project", "update", "complete", "cancel", "reopen"].indexOf(r.op) >= 0) {
            result = write();
        } else throw new Error("Unsupported operation.");
        result.ok = !result.mismatches || result.mismatches.length === 0;
        return JSON.stringify(result);
    } catch (error) {
        let message = String(error);
        if (message.indexOf("-1743") >= 0 || /not author/i.test(message)) {
            message = "macOS Automation access is denied. Enable Things under Codex in System Settings > Privacy & Security > Automation.";
        }
        return JSON.stringify({ok: false, error: message, write_may_have_applied: writeStarted, item_id: changedID});
    }
}
