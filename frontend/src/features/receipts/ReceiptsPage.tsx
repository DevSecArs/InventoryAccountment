import { CircleDashed, CircleX, FileCheck2, Filter, Plus, RotateCcw } from "lucide-react";

import { FeatureUnavailable } from "../../components/FeatureUnavailable";

const states = [
  { code: "draft", label: "Черновик", description: "Можно изменять документ и строки" },
  { code: "queued", label: "В очереди", description: "Событие ожидает обработки" },
  { code: "processing", label: "Обработка", description: "Worker проводит поступление" },
  { code: "posted", label: "Проведено", description: "Документ доступен только для чтения" },
];

export function ReceiptsPage() {
  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Документы</p>
          <h1>Поступления</h1>
          <p className="page-description">Черновики поставок, асинхронное проведение и история статусов.</p>
        </div>
        <button className="button button--primary" type="button" disabled title="API поступлений ещё не реализован"><Plus size={18} /> Создать поступление</button>
      </section>

      <FeatureUnavailable>
        Backend пока не предоставляет маршруты поступлений, строк, отправки и повторной обработки. Интерфейс не имитирует сохранение данных.
      </FeatureUnavailable>

      <section className="workflow-panel" aria-labelledby="workflow-title">
        <div className="section-heading"><div><p className="eyebrow">Жизненный цикл</p><h2 id="workflow-title">Статусы документа</h2></div></div>
        <div className="workflow-steps">
          {states.map((state, index) => (
            <div className="workflow-step" key={state.code}>
              <span>{index + 1}</span><div><strong>{state.label}</strong><p>{state.description}</p></div>
            </div>
          ))}
        </div>
        <div className="workflow-exception"><CircleX size={20} /><div><strong>Ошибка обработки</strong><p>После исчерпания попыток документ получает статус «Ошибка». Оператор может выполнить явный повтор.</p></div><button className="button button--secondary" type="button" disabled><RotateCcw size={17} /> Повторить</button></div>
      </section>

      <section className="data-panel">
        <div className="catalog-toolbar">
          <div className="search-control disabled-control"><Filter size={18} /><span>Период, поставщик, номер и статус</span></div>
          <button className="button button--secondary" type="button" disabled>Применить фильтры</button>
        </div>
        <div className="compact-empty">
          <CircleDashed size={30} aria-hidden="true" />
          <strong>Список поступлений недоступен</strong>
          <span>После подключения API здесь появятся реальные документы и их статусы.</span>
        </div>
      </section>

      <section className="content-grid">
        <article className="panel"><FileCheck2 size={22} /><h2>Проведённые документы</h2><p>Неизменяемы и включаются в отчёты только после успешной фиксации обработки.</p></article>
        <article className="panel"><RotateCcw size={22} /><h2>Безопасные повторы</h2><p>Повторная доставка не должна дублировать поступление благодаря ключу идемпотентности.</p></article>
      </section>
    </div>
  );
}
