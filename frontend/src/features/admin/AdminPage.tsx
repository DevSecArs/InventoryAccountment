import { useQuery } from "@tanstack/react-query";
import { ArchiveRestore, Database, HeartPulse, MessageSquareMore, ShieldCheck } from "lucide-react";

import { getLiveness, getReadiness } from "../../api/health";
import { ApiErrorNotice } from "../../components/ApiErrorNotice";
import { FeatureUnavailable } from "../../components/FeatureUnavailable";

export function AdminPage() {
  const live = useQuery({ queryKey: ["health", "live"], queryFn: ({ signal }) => getLiveness(signal), refetchInterval: 30_000 });
  const ready = useQuery({ queryKey: ["health", "ready"], queryFn: ({ signal }) => getReadiness(signal), refetchInterval: 30_000 });

  return (
    <div className="page-stack">
      <section className="page-heading"><div><p className="eyebrow">Эксплуатация</p><h1>Администрирование</h1><p className="page-description">Состояние обязательных сервисов и безопасные эксплуатационные действия.</p></div></section>

      {(live.error || ready.error) && <ApiErrorNotice error={live.error ?? ready.error} onRetry={() => { live.refetch(); ready.refetch(); }} />}

      <section className="admin-grid" aria-label="Состояние сервисов">
        <ServiceCard icon={HeartPulse} name="HTTP API" state={live.isPending ? "Проверка" : live.isSuccess ? "Работает" : "Недоступен"} healthy={live.isSuccess} />
        <ServiceCard icon={Database} name="PostgreSQL" state={ready.isPending ? "Проверка" : ready.isSuccess ? "Готова" : "Недоступна"} healthy={ready.isSuccess} />
        <ServiceCard icon={MessageSquareMore} name="Очередь" state="Нет API" healthy={false} unavailable />
        <ServiceCard icon={ArchiveRestore} name="Резервные копии" state="Нет API" healthy={false} unavailable />
      </section>

      <FeatureUnavailable>
        Метрики RabbitMQ, DLQ, outbox и backup пока не опубликованы через защищённый административный API. Секреты и строки подключения в браузере не отображаются.
      </FeatureUnavailable>

      <section className="panel admin-policy"><ShieldCheck size={24} /><div><h2>Безопасность операций</h2><p>Восстановление должно выполняться сначала в отдельную БД. Перезапись существующей цели требует подтверждения точного окружения и отдельного разрешения.</p></div></section>
    </div>
  );
}

function ServiceCard({ icon: Icon, name, state, healthy, unavailable = false }: { icon: typeof HeartPulse; name: string; state: string; healthy: boolean; unavailable?: boolean }) {
  return (
    <article className="service-card">
      <div className="metric-icon"><Icon size={21} /></div>
      <div><p>{name}</p><strong>{state}</strong></div>
      <span className={`health-dot ${healthy ? "health-dot--ok" : unavailable ? "health-dot--unknown" : "health-dot--error"}`} aria-hidden="true" />
    </article>
  );
}
