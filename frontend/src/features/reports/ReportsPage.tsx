import { CalendarRange, Download, FileBarChart2 } from "lucide-react";

import { FeatureUnavailable } from "../../components/FeatureUnavailable";

export function ReportsPage() {
  return (
    <div className="page-stack">
      <section className="page-heading">
        <div><p className="eyebrow">Аналитика</p><h1>Отчёт по поставкам</h1><p className="page-description">Проведённые поступления за период с итогами отдельно по единицам измерения.</p></div>
        <button className="button button--secondary" type="button" disabled title="API экспорта ещё не реализован"><Download size={18} /> Скачать CSV</button>
      </section>

      <FeatureUnavailable>
        Backend пока не предоставляет маршруты отчёта и CSV. Параметры можно будет применять только после появления подтверждённого OpenAPI-контракта.
      </FeatureUnavailable>

      <section className="filter-panel" aria-labelledby="report-params">
        <div className="section-heading"><div><p className="eyebrow">Параметры</p><h2 id="report-params">Период и фильтры</h2></div><CalendarRange aria-hidden="true" /></div>
        <fieldset disabled>
          <div className="report-filters">
            <label><span>Начало периода</span><input type="datetime-local" /></label>
            <label><span>Конец периода</span><input type="datetime-local" /></label>
            <label><span>Поставщик</span><select><option>Все поставщики</option></select></label>
            <label><span>Материал</span><select><option>Все материалы</option></select></label>
          </div>
          <button className="button button--primary" type="button">Сформировать отчёт</button>
        </fieldset>
      </section>

      <section className="data-panel">
        <div className="compact-empty"><FileBarChart2 size={32} /><strong>Отчёт ещё не сформирован</strong><span>Укажите период после подключения серверного API.</span></div>
      </section>
    </div>
  );
}
