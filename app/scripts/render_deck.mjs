import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import os from 'node:os';
const root = fileURLToPath(new URL('../', import.meta.url));
const modules = process.env.RUNTIME_NODE_MODULES ?? path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const artifact = process.env.AQUASHIFT_ARTIFACT_TOOL_FILE ?? path.join(modules, '@oai/artifact-tool/dist/artifact_tool.mjs');
const { FileBlob, PresentationFile } = await import(pathToFileURL(artifact));
const deck = await PresentationFile.importPptx(await FileBlob.load(path.resolve(root, process.argv[2] ?? 'delivery/AquaShift-Pafos-2026.pptx')));
const output = path.resolve(root, process.argv[3] ?? 'build/deck-final-previews');
await fs.mkdir(output, { recursive: true });
for (let i = 0; i < deck.slides.items.length; i++) {
  const image = await deck.export({ slide: deck.slides.items[i], format: 'png', scale: 1 });
  await fs.writeFile(path.join(output, `slide-${String(i+1).padStart(2, '0')}.png`), new Uint8Array(await image.arrayBuffer()));
}
console.log(`Rendered ${deck.slides.items.length} final slides.`);
