// Run the actual JXA source against synthetic application objects, never Things.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../scripts/things.js'), 'utf8');
const modified = '2026-10-04T12:00:00.000Z';

function fixture(options = {}) {
  const writes = [];
  const states = [];
  function item(id, title) {
    const state = {
      id, name: title, notes: 'Synthetic notes', status: 'open', tagNames: 'Work',
      activationDate: null, dueDate: new Date(2027, 0, 15, 12), project: null, area: null,
    };
    states.push(state);
    const value = {
      id: () => id,
      exists: () => true,
      modificationDate: () => new Date(modified),
      tags: { name: () => state.tagNames ? state.tagNames.split(', ') : [] },
    };
    for (const key of Object.keys(state).filter(key => key !== 'id')) {
      Object.defineProperty(value, key, {
        get: () => () => state[key],
        set: next => {
          writes.push({ id, key, value: next });
          if (options.failOn === key) throw new Error('Synthetic automation failure');
          if (options.ignoreField !== key) state[key] = next;
        },
      });
    }
    return value;
  }
  function collection(items) {
    const value = () => items.slice();
    value.byId = id => items.find(entry => entry.id() === id) || { exists: () => false };
    value.id = () => items.map(entry => entry.id());
    value.push = draft => { writes.push({ key: 'push' }); items.push(draft); };
    return value;
  }
  const items = [item('task-1', 'First task'), item('task-2', 'Second task')];
  const todos = collection(items);
  const app = {
    toDos: todos,
    projects: collection(options.project ? [items[0]] : []),
    areas: collection([]),
    tags: { name: () => ['Work', 'Home'] },
    lists: {
      byName: name => ({ exists: () => name === 'Someday', toDos: collection([]) }),
    },
    ToDo: properties => {
      writes.push({ key: 'construct' });
      const draft = item('created-1', properties.name);
      Object.assign(states[states.length - 1], properties);
      return draft;
    },
    schedule: (todo, { for: date }) => { todo.activationDate = date; },
    move: () => { writes.push({ key: 'move' }); },
  };
  const context = vm.createContext({ Application: () => app });
  vm.runInContext(source, context);
  const run = request => JSON.parse(context.run([JSON.stringify(request)]));
  return { run, writes, states };
}

test('update preview returns a plan and does not mutate the item', () => {
  const f = fixture();
  const result = f.run({ op: 'update', id: 'task-1', title: 'Renamed', apply: false });
  assert.equal(result.ok, true);
  assert.equal(result.preview, true);
  assert.equal(result.before.title, 'First task');
  assert.deepEqual(result.plan.changes, { title: 'Renamed' });
  assert.deepEqual(f.writes, []);
});

test('create preview does not construct or insert an item', () => {
  const f = fixture();
  const result = f.run({ op: 'create', title: 'New task', apply: false });
  assert.equal(result.ok, true);
  assert.equal(result.before, null);
  assert.deepEqual(f.writes, []);
});

test('stale edits fail before any changes', () => {
  const f = fixture();
  const result = f.run({ op: 'update', id: 'task-1', title: 'Renamed', expected_modified: '2026-01-01T00:00:00.000Z', apply: true });
  assert.equal(result.ok, false);
  assert.match(result.error, /changed since it was read/);
  assert.equal(result.write_may_have_applied, false);
  assert.deepEqual(f.writes, []);
});

test('unknown tags and destinations are rejected before writes', () => {
  for (const fields of [{ tags: ['Missing'] }, { project_id: 'missing' }, { area_id: 'missing' }]) {
    const f = fixture();
    const result = f.run({ op: 'update', id: 'task-1', title: 'Renamed', ...fields, apply: true });
    assert.equal(result.ok, false);
    assert.equal(result.write_may_have_applied, false);
    assert.deepEqual(f.writes, []);
  }
});

test('verified edit preserves omitted fields and accepts the exact modification timestamp', () => {
  const f = fixture();
  const result = f.run({ op: 'update', id: 'task-1', title: 'Renamed', expected_modified: modified, apply: true });
  assert.equal(result.ok, true);
  assert.equal(result.verified, true);
  assert.equal(result.item.title, 'Renamed');
  assert.equal(result.item.notes, 'Synthetic notes');
  assert.equal(result.item.deadline, '2027-01-15');
  assert.deepEqual(f.writes.map(write => write.key), ['name']);
});

test('a write that Things ignores is reported as a verification failure', () => {
  const f = fixture({ ignoreField: 'name' });
  const result = f.run({ op: 'update', id: 'task-1', title: 'Renamed', apply: true });
  assert.equal(result.ok, false);
  assert.equal(result.applied, true);
  assert.equal(result.verified, false);
  assert.deepEqual(result.mismatches, ['title']);
});

test('partial failure returns the item ID and uncertainty instead of retrying', () => {
  const f = fixture({ failOn: 'notes' });
  const result = f.run({ op: 'update', id: 'task-1', title: 'Renamed', notes: 'Changed', apply: true });
  assert.equal(result.ok, false);
  assert.equal(result.write_may_have_applied, true);
  assert.equal(result.item_id, 'task-1');
  assert.equal(f.states[0].name, 'Renamed');
  assert.deepEqual(f.writes.map(write => write.key), ['name', 'notes']);
});

test('failed create scheduling returns the created ID for recovery', () => {
  const f = fixture({ failOn: 'activationDate' });
  const result = f.run({ op: 'create', title: 'New task', when: '2027-01-15', apply: true });
  assert.equal(result.ok, false);
  assert.equal(result.write_may_have_applied, true);
  assert.equal(result.item_id, 'created-1');
  assert.equal(f.writes.filter(write => write.key === 'push').length, 1);
});

test('scheduling preserves the deadline and verifies the local calendar date', () => {
  const f = fixture();
  const result = f.run({ op: 'update', id: 'task-1', when: '2027-02-03', apply: true });
  assert.equal(result.ok, true);
  assert.equal(result.verified, true);
  assert.equal(result.item.when, '2027-02-03');
  assert.equal(result.item.deadline, '2027-01-15');
});

test('Someday verification checks actual membership', () => {
  const f = fixture();
  const result = f.run({ op: 'update', id: 'task-1', when: 'someday', apply: true });
  assert.equal(result.verified, false);
  assert.deepEqual(result.mismatches, ['when']);
});

test('all status operations are verified by reading the item back', () => {
  for (const [op, status] of [['complete', 'completed'], ['cancel', 'canceled'], ['reopen', 'open']]) {
    const f = fixture();
    const result = f.run({ op, id: 'task-1', apply: true });
    assert.equal(result.ok, true);
    assert.equal(result.verified, true);
    assert.equal(result.item.status, status);
  }
});

test('reads paginate without leaking notes and distinguish projects', () => {
  const f = fixture({ project: true });
  const first = f.run({ op: 'list', limit: 1, offset: 0 });
  assert.equal(first.total, 2);
  assert.equal(first.next_offset, 1);
  assert.equal(first.items[0].type, 'project');
  assert.equal(Object.hasOwn(first.items[0], 'notes'), false);
  const second = f.run({ op: 'list', limit: 1, offset: first.next_offset, include_notes: true });
  assert.equal(second.next_offset, null);
  assert.equal(second.items[0].type, 'todo');
  assert.equal(second.items[0].notes, 'Synthetic notes');
  assert.deepEqual(f.writes, []);
});

test('search filters closed tasks only when the requested status excludes them', () => {
  const f = fixture();
  f.states[1].status = 'completed';
  const all = f.run({ op: 'search', query: 'TASK' });
  const open = f.run({ op: 'search', query: 'TASK', status: 'open' });
  assert.equal(all.total, 2);
  assert.equal(open.total, 1);
  assert.equal(open.items[0].id, 'task-1');
});
