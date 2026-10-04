import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { parseArgs } from 'node:util';
import vm from 'node:vm';
import { validatePilot, pilotRecord } from './public/pilot.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const usage = 'node web/review_pilot.mjs --contract declaration.json --observations readings.csv --output new-report.json';
let output, identity;

async function readInput(file, limit, label) {
  if ((await fs.stat(file)).size > limit) throw new Error(`${label} exceeds ${limit} bytes.`);
  const bytes = await fs.readFile(file);
  if (bytes.length > limit) throw new Error(`${label} exceeds ${limit} bytes.`);
  return bytes;
}

try {
  const { values } = parseArgs({ options: {
    contract: { type: 'string' }, observations: { type: 'string' }, output: { type: 'string' }, help: { type: 'boolean' },
  }, allowPositionals: false });
  if (values.help) {
    console.log(`${usage}\nNode 20 or newer. Offline numeric observation review; no npm packages or plant commands.\nMaximum declaration: 256 KiB; observations: 10 MiB. COMPLETE means numeric coverage only.\nExit 0: COMPLETE or NEEDS_REVIEW (gaps/late readings). Exit 1: BLOCKED.\nReports use a new output file; existing files are preserved.`);
  } else {
    if (!values.contract || !values.observations || !values.output) throw new Error(usage);
    output = path.resolve(values.output);
    const [contractBytes, observationBytes, vendorBytes, provenanceBytes] = await Promise.all([
      readInput(values.contract, 256 * 1024, 'Declaration'), readInput(values.observations, 10 * 1024 * 1024, 'Observation CSV'),
      fs.readFile(path.join(root, 'public/vendor/papaparse.min.js')),
      fs.readFile(path.join(root, 'vendor/provenance.json')),
    ]);
    identity = {
      contract: { name: path.basename(values.contract), bytes: contractBytes.length, sha256: sha256(contractBytes) },
      observations: { name: path.basename(values.observations), bytes: observationBytes.length, sha256: sha256(observationBytes) },
    };
    const decode = bytes => new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
    const provenance = JSON.parse(decode(provenanceBytes).replace(/^\uFEFF/, ''));
    if (sha256(vendorBytes) !== provenance.script_sha256) throw new Error('Vendored PapaParse hash does not match its retained provenance.');
    const sandbox = { module: { exports: {} }, exports: {} };
    vm.runInNewContext(decode(vendorBytes), sandbox, { filename: 'papaparse.min.js', timeout: 1000 });
    const contract = JSON.parse(decode(contractBytes).replace(/^\uFEFF/, ''));
    const report = validatePilot(contract, decode(observationBytes), sandbox.module.exports);
    identity.parser = { name: provenance.name, version: provenance.version, sha256: sha256(vendorBytes) };
    const result = {
      tool: 'AquaShift offline observation reviewer',
      readiness: report.status === 'BLOCKED' ? 'BLOCKED' : report.reviewRequired ? 'NEEDS_REVIEW' : report.status,
      review: pilotRecord(contract, report, identity),
    };
    await fs.mkdir(path.dirname(output), { recursive: true });
    await fs.writeFile(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    console.log(`${result.readiness}: ${report.knownSlots} of ${report.expectedSlots} known slots; ${report.issues.length} blocking ${report.issues.length === 1 ? 'finding' : 'findings'}. Report: ${output}`);
    process.exitCode = report.status === 'BLOCKED' ? 1 : 0;
  }
} catch (error) {
  const result = { tool: 'AquaShift offline observation reviewer', readiness: 'BLOCKED', review: null, identity: identity ?? null,
    issues: [{ field: 'input / file handling', code: 'input_error', message: error.message }] };
  if (output) {
    try {
      await fs.mkdir(path.dirname(output), { recursive: true });
      await fs.writeFile(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    } catch (writeError) {
      console.error(`Report was not saved: ${writeError.message}`);
    }
  }
  console.error(`BLOCKED: ${error.message}`);
  process.exitCode = 1;
}
