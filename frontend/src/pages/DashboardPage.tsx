import { ArrowRight, Boxes, ClipboardCheck, CircleAlert, Database, Truck } from "lucide-react";
import { Link } from "react-router-dom";

const overviewItems = [
  { label: "Справочники", value: "3", detail: "Единицы, материалы, поставщики", icon: Boxes },
  { label: "Активные поступления", value: "—", detail: "API ожидает реализации", icon: Truck },
  { label: "Документы с ошибкой", value: "—", detail: "API ожидает реализации", icon: CircleAlert },
];

export function DashboardPage() {
  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Рабочее пространство</p>
          <h1>Обзор склада</h1>
          <p className="page-description">
            Справочники доступны для работы. Поступления и отчёты будут подключены после появления
            серверного API.
          </p>
        </div>
        <Link className="button button--primary" to="/units">
          Открыть справочники
          <ArrowRight size={18} aria-hidden="true" />
        </Link>
      </section>

      <section className="metric-grid" aria-label="Сводка">
        {overviewItems.map(({ label, value, detail, icon: Icon }) => (
          <article className="metric-card" key={label}>
            <div className="metric-icon"><Icon size={20} aria-hidden="true" /></div>
            <div>
              <p className="metric-label">{label}</p>
              <p className="metric-value">{value}</p>
              <p className="metric-detail">{detail}</p>
            </div>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Готовность</p>
              <h2>Состояние системы</h2>
            </div>
            <span className="status-pill status-pill--neutral">Проверяется через API</span>
          </div>
          <div className="service-list">
            <div className="service-row">
              <Database size={19} aria-hidden="true" />
              <div><strong>PostgreSQL</strong><span>Состояние доступно в /health/ready</span></div>
            </div>
            <div className="service-row">
              <ClipboardCheck size={19} aria-hidden="true" />
              <div><strong>HTTP API</strong><span>Состояние доступно в /health/live</span></div>
            </div>
          </div>
        </article>

        <article className="panel panel--accent">
          <p className="eyebrow">Следующий шаг</p>
          <h2>Подготовьте справочники</h2>
          <p>Начните с единиц измерения, затем добавьте материалы и поставщиков.</p>
          <Link className="text-link" to="/units">Перейти к единицам <ArrowRight size={16} /></Link>
        </article>
      </section>
    </div>
  );
}
