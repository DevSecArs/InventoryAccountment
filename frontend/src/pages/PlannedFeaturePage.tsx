import { Construction } from "lucide-react";

interface PlannedFeaturePageProps {
  feature: string;
}

export function PlannedFeaturePage({ feature }: PlannedFeaturePageProps) {
  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Раздел приложения</p>
          <h1>{feature}</h1>
        </div>
      </section>
      <section className="empty-state">
        <Construction size={32} aria-hidden="true" />
        <h2>Раздел готовится к подключению</h2>
        <p>Здесь появятся данные и действия после реализации соответствующего вертикального среза.</p>
      </section>
    </div>
  );
}
