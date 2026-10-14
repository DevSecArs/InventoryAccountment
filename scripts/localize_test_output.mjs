import { spawnSync } from 'node:child_process';

const command = process.argv[2] === '--' ? process.argv.slice(3) : process.argv.slice(2);
if (command.length === 0) {
  process.stderr.write('Укажите команду проверки после --\n');
  process.exit(2);
}

const result = spawnSync(command[0], command.slice(1), { encoding: 'utf8' });
if (result.error) {
  process.stderr.write(`Не удалось запустить команду: ${result.error.message}\n`);
  process.exit(2);
}

function localize(output) {
  return output
    // Vitest colors its summary labels; strip terminal control codes before matching.
    .replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, '')
    .replace(
      /^[ \t]*Progress: resolved (\d+), reused (\d+), downloaded (\d+), added (\d+)(?:, done)?$/gm,
      (_line, resolved, reused, downloaded, added) =>
        `Ход установки pnpm: обработано пакетов — ${resolved}; взято из кэша — ${reused}; ` +
        `скачано — ${downloaded}; добавлено в node_modules на этом шаге — ${added}.`,
    )
    .replace(/^[ \t]*Packages: \+(\d+)$/gm, 'План pnpm: будет добавлено пакетов — $1.')
    .replace(
      /^[ \t]*Packages are copied from the content-addressable store to the virtual store\.$/gm,
      'pnpm копирует пакеты из адресного кэша в виртуальное хранилище node_modules.',
    )
    .replace(/^[ \t]*Content-addressable store is at: (.+)$/gm, 'Путь кэша pnpm: $1.')
    .replace(/^[ \t]*Virtual store is at: (.+)$/gm, 'Путь виртуального хранилища node_modules: $1.')
    .replace(
      /^\[WARN\] GET (\S+) error \(([^)]+)\)\. Will retry in ([^.]+)\. (\d+) retries? left\.$/gm,
      (_line, url, code, delay, retries) =>
        `Предупреждение pnpm: запрос к ${url} не удался (код ${code}); ` +
        `следующая попытка через ${delay}; осталось повторов — ${retries}.`,
    )
    .replace(
      /^[^\p{L}]*Verifying lockfile against supply-chain policies \((\d+) entries\)\.\.\.$/gmu,
      'pnpm проверяет $1 записей lock-файла по правилам безопасности зависимостей.',
    )
    .replace(
      /^Lockfile is up to date, resolution step is skipped$/gm,
      'Lock-файл актуален; повторный подбор версий пакетов не требуется.',
    )
    .replace(/^\s*(Tests|Test Files)\s+(.+)$/gm, (_line, label, summary) => {
      const translatedLabel = label === 'Tests' ? 'Тесты' : 'Файлы тестов';
      const translatedSummary = summary
        .replace(/\bpassed\b/g, 'успешно')
        .replace(/\bfailed\b/g, 'с ошибкой')
        .replace(/\bskipped\b/g, 'пропущено')
        .replace(/\btodo\b/g, 'ожидает');
      return `${translatedLabel}: ${translatedSummary}`;
    })
    .replace(/^\s*Start at:/gm, '  Начало:')
    .replace(/^\s*Duration:/gm, '  Длительность:')
    .replace(/^JUNIT report written to/gm, 'Отчёт JUnit сохранён в')
    .replace(/^✓ (.+) \((\d+) tests?\)(.*)$/gm, '✓ $1 ($2 тестов)$3')
    .replace(/^❯ (.+) \((\d+) tests?\)(.*)$/gm, '❯ $1 ($2 тестов)$3');
}

if (result.stdout) process.stdout.write(localize(result.stdout));
if (result.stderr) process.stderr.write(localize(result.stderr));
process.exit(result.status ?? 2);
