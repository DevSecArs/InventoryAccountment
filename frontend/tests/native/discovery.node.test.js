import { test } from 'node:test';
import { readdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { resolve, join } from 'node:path';

test('все прикладные модули доступны без побочных эффектов при импорте', async () => {
  async function visit(directory) {
    for (const item of await readdir(directory, { withFileTypes: true })) {
      const path = join(directory, item.name);
      if (item.isDirectory()) await visit(path);
      else if (item.name.endsWith('.js') && !item.name.endsWith('.test.js')) await import(pathToFileURL(resolve(path)).href);
    }
  }
  await visit('src');
});
