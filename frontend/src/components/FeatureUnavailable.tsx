import { LockKeyhole } from "lucide-react";

interface FeatureUnavailableProps {
  children: string;
}

export function FeatureUnavailable({ children }: FeatureUnavailableProps) {
  return (
    <div className="feature-unavailable" role="status">
      <LockKeyhole size={20} aria-hidden="true" />
      <div><strong>Серверная функция ещё не подключена</strong><p>{children}</p></div>
    </div>
  );
}
