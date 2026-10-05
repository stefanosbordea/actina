import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const fixtures = ['pilot-synthetic-declaration.json', 'pilot-synthetic-observations.csv', 'pilot-late-review-declaration.json', 'pilot-wrong-unit.csv'];
const sources = ['web/review_pilot.mjs', 'web/public/pilot.mjs', 'web/public/vendor/papaparse.min.js', 'web/vendor/provenance.json', ...fixtures.map(name => `web/fixtures/${name}`)];
const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'aquashift-pilot-cli-'));
const target = path.join(temp, 'AquaShift relocated with spaces');
const checks = [];
try {
  for (const file of sources) {
    await fs.mkdir(path.dirname(path.join(target, file)), { recursive: true });
    await fs.copyFile(path.join(root, file), path.join(target, file));
  }
  for (const absent of ['.git', 'web/node_modules', 'web/package.json', 'web/public/assets', 'web/public/data.json']) {
    await assert.rejects(fs.access(path.join(target, absent)));
  }
  async function run(name, contract, observations, expectedExit, readiness) {
    const output = `results/${name}.json`;
    const args = ['web/review_pilot.mjs', '--contract', contract, '--observations', observations, '--output', output];
    const result = spawnSync(process.execPath, args, { cwd: target, encoding: 'utf8' });
    assert.equal(result.status, expectedExit, result.stderr);
    const bytes = await fs.readFile(path.join(target, output));
    const report = JSON.parse(bytes);
    assert.equal(report.readiness, readiness);
    checks.push({ name, arguments: ['node', ...args], exit_status: result.status, readiness,
      validation_status: report.review?.status ?? null, known_slots: report.review?.knownSlots ?? null,
      expected_slots: report.review?.expectedSlots ?? null, report_sha256: sha256(bytes) });
    await fs.mkdir(path.join(root, 'results/pilot-cli-reports'), { recursive: true });
    await fs.writeFile(path.join(root, 'results/pilot-cli-reports', `${name}.json`), bytes);
    return report;
  }
  const declaration = 'web/fixtures/pilot-synthetic-declaration.json';
  const observations = 'web/fixtures/pilot-synthetic-observations.csv';
  const gap = await run('gap', declaration, observations, 0, 'NEEDS_REVIEW');
  assert.equal(gap.review.status, 'PARTIAL');
  assert.equal(gap.review.knownSlots, 15);
  assert.equal(gap.review.expectedSlots, 16);
  assert.equal(gap.review.missing.length, 1);
  const late = await run('late', 'web/fixtures/pilot-late-review-declaration.json', observations, 0, 'NEEDS_REVIEW');
  assert.equal(late.review.knownSlots, 8);
  assert.equal(late.review.missing.filter(row => row.reason === 'Not available at review time').length, 7);
  assert.equal(late.review.missing.filter(row => row.reason === 'No observation supplied').length, 1);
  const wrong = await run('wrong-unit', declaration, 'web/fixtures/pilot-wrong-unit.csv', 1, 'BLOCKED');
  assert.equal(wrong.review.observations.length, 0);
  assert(wrong.review.issues.some(issue => issue.code === 'wrong_unit'));
  const original = await fs.readFile(path.join(target, observations));
  const complete = original.toString('utf8').trimEnd() + '\n2026-07-01T12:00:00+03:00,2026-07-01T12:01:00+03:00,unit-demo,unit_load_kw,1258,kW\n';
  await fs.writeFile(path.join(target, 'complete.csv'), complete);
  const completeReport = await run('numeric-complete', declaration, 'complete.csv', 0, 'COMPLETE');
  assert.equal(completeReport.review.knownSlots, 16);
  assert.equal(completeReport.review.reviewRequired, false);
  assert(complete.includes(',1800,m3'));
  await fs.writeFile(path.join(target, 'below-reserve.csv'), complete.replace(',1800,m3', ',500,m3'));
  const reserve = await run('below-reserve', declaration, 'below-reserve.csv', 0, 'NEEDS_REVIEW');
  assert.equal(reserve.review.status, 'COMPLETE');
  assert.equal(reserve.review.reviewRequired, true);
  const bom = Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), original]);
  await fs.writeFile(path.join(target, 'bom.csv'), bom);
  const bomReport = await run('bom', declaration, 'bom.csv', 0, 'NEEDS_REVIEW');
  assert.equal(bomReport.review.identity.observations.sha256, sha256(bom));
  assert.notEqual(sha256(bom), sha256(original));
  assert.equal(bomReport.review.knownSlots, 15);
  const invalid = Buffer.from([0x63, 0x73, 0x76, 0xff]);
  await fs.writeFile(path.join(target, 'invalid-utf8.csv'), invalid);
  const utf8 = await run('invalid-utf8', declaration, 'invalid-utf8.csv', 1, 'BLOCKED');
  assert.equal(utf8.review, null);
  assert.equal(utf8.identity.observations.sha256, sha256(invalid));
  for (const [name, size, contract, csv] of [
    ['oversized-declaration.json', 256 * 1024 + 1, 'oversized-declaration.json', observations],
    ['oversized-observations.csv', 10 * 1024 * 1024 + 1, declaration, 'oversized-observations.csv'],
  ]) {
    await fs.writeFile(path.join(target, name), '');
    await fs.truncate(path.join(target, name), size);
    const report = await run(name.split('.')[0], contract, csv, 1, 'BLOCKED');
    assert(report.issues[0].message.includes('exceeds'));
    assert.equal((await fs.stat(path.join(target, name))).size, size);
  }
  const gapPath = path.join(target, 'results/gap.json');
  const gapBefore = await fs.readFile(gapPath);
  const repeat = spawnSync(process.execPath, ['web/review_pilot.mjs', '--contract', declaration, '--observations', observations, '--output', 'results/gap.json'], { cwd: target, encoding: 'utf8' });
  assert.equal(repeat.status, 1);
  assert.deepEqual(await fs.readFile(gapPath), gapBefore);
  checks.push({ name: 'existing-output-preserved', exit_status: repeat.status, original_report_sha256: sha256(gapBefore) });
  await fs.appendFile(path.join(target, 'web/public/vendor/papaparse.min.js'), '\n');
  const vendor = await run('vendor-tamper', declaration, observations, 1, 'BLOCKED');
  assert(vendor.issues[0].message.includes('hash does not match'));
  const inputHashes = {};
  for (const file of [...sources, 'web/check_pilot_cli.mjs']) inputHashes[file] = sha256(await fs.readFile(path.join(root, file)));
  const receipt = { status: 'PASS', completed_at_utc: new Date().toISOString(), node_version: process.version,
    reproduction: 'node web/check_pilot_cli.mjs', scope: 'Executed CLI in a relocated minimal folder with spaces; no Git, node_modules, package.json or public dataset assets. All inputs are synthetic fixtures.',
    input_sha256: inputHashes, checks, temporary_tree_removed: true,
    limitations: ['Numeric observational review only; no authenticated telemetry, safety certification, dispatch permission or model/scheduler change.'] };
  await fs.mkdir(path.join(root, 'results'), { recursive: true });
  await fs.writeFile(path.join(root, 'results/pilot-cli-check.json'), JSON.stringify(receipt, null, 2) + '\n');
  console.log(JSON.stringify({ status: receipt.status, checks: checks.length, receipt: 'results/pilot-cli-check.json' }));
} finally {
  await fs.rm(temp, { recursive: true, force: true });
}
