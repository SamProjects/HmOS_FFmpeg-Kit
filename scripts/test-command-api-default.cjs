// Execute the real ArkTS API after transpilation, using a recording NAPI binding.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const ts = require(path.resolve(process.argv[2]));
const calls = [];
const controls = [];
const binding = {
  execute(id, args, timeout) {
    calls.push({id, args, timeout});
    return Promise.resolve(JSON.stringify({exitCode: 0, cancelled: false, timedOut: false, logs: '', logsTruncated: false}));
  },
  control(id, cancel) { controls.push({id, cancel}); }
};
const source = fs.readFileSync(path.join(__dirname, '../harmony/ffmpeg/Index.ets'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020},
  fileName: 'Index.ts'
}).outputText;
const exported = {};
vm.runInNewContext(compiled, {
  exports: exported,
  require(name) {
    assert.equal(name, 'libhmosffmpeg.so');
    return {default: binding};
  }
});
(async () => {
  const args = ['-version'];
  const sessions = [
    exported.FFmpeg.execute(args),
    exported.FFmpeg.execute(args, undefined),
    exported.FFmpeg.execute(args, 0),
    exported.FFmpeg.execute(args, 7200),
    exported.FFmpeg.execute(args, 300)
  ];
  assert.deepEqual(calls.map(c => c.timeout), [0, 0, 0, 7200, 300]);
  assert(calls.every(c => c.args === args));
  exported.FFmpeg.cancel(sessions[0].id);
  assert.deepEqual(controls, [{id: sessions[0].id, cancel: true}]);
  const results = await Promise.all(sessions.map(s => s.result));
  assert(results.every(r => r.exitCode === 0 && !r.timedOut));
  console.log('ArkTS default/undefined/zero -> no total timeout; explicit 7200/300 and cancel forwarded correctly');
})().catch(error => { console.error(error); process.exitCode = 1; });
