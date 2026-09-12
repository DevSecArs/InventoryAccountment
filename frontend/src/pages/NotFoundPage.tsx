import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <section className="empty-state empty-state--page">
      <p className="error-code">404</p>
      <h1>Страница не найдена</h1>
      <p>Проверьте адрес или вернитесь на обзор склада.</p>
      <Link className="button button--primary" to="/">
        <ArrowLeft size={18} aria-hidden="true" />
        Вернуться на обзор
      </Link>
    </section>
  );
}
