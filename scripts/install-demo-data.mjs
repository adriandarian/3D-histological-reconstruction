import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const release = 'https://github.com/adriandarian/3D-histological-reconstruction/releases/download/demo-datasets-v1';
const datasets = {
  synthetic: 'b6fed30889a92384acded3704a8fa73d99213923561efa35ac078673864d8cfc',
  real: 'dccc67ecc9f588b16813308371df9b25e9ca71c0bee48eb8af9a0b86cdbdab2b',
};

const temporary = await mkdtemp(join(tmpdir(), 'histology-demo-'));
try {
  for (const [name, expectedHash] of Object.entries(datasets)) {
    const url = `${release}/${name}.tar.gz`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Dataset download failed (${response.status}): ${url}`);

    const bytes = Buffer.from(await response.arrayBuffer());
    const hash = createHash('sha256').update(bytes).digest('hex');
    if (hash !== expectedHash) throw new Error(`SHA-256 mismatch for ${url}: ${hash}`);

    const archive = join(temporary, `${name}.tar.gz`);
    const output = join('dist', 'data', name);
    await writeFile(archive, bytes);
    await mkdir(output, { recursive: true });
    execFileSync('tar', ['-xzf', archive, '-C', output], { stdio: 'inherit' });
    console.log(`Installed ${name} dataset in ${output}`);
  }
} finally {
  await rm(temporary, { recursive: true, force: true });
}
