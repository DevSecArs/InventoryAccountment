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
