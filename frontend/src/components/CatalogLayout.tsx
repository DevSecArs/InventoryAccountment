import { Archive, ChevronLeft, ChevronRight, Pencil, Plus, Search } from "lucide-react";
import type { FormEvent, ReactNode } from "react";

import type { CatalogRecord } from "../api/catalogs";
import { ApiErrorNotice } from "./ApiErrorNotice";

export interface CatalogColumn<T> {
  label: string;
  render: (item: T) => ReactNode;
}

interface CatalogLayoutProps<T extends CatalogRecord> {
  title: string;
  description: string;
  createLabel: string;
  columns: CatalogColumn<T>[];
  items: T[];
  total: number;
  skip: number;
  limit: number;
  searchInput: string;
  includeArchived: boolean;
  loading: boolean;
  error: unknown;
  onSearchInput: (value: string) => void;
  onSearch: () => void;
  onIncludeArchived: (value: boolean) => void;
  onCreate: () => void;
  onEdit: (item: T) => void;
  onArchive: (item: T) => void;
  onPrevious: () => void;
  onNext: () => void;
  onRetry: () => void;
}

export function CatalogLayout<T extends CatalogRecord>({
  title,
  description,
  createLabel,
  columns,
  items,
  total,
  skip,
  limit,
  searchInput,
  includeArchived,
  loading,
  error,
  onSearchInput,
  onSearch,
  onIncludeArchived,
  onCreate,
  onEdit,
  onArchive,
  onPrevious,
  onNext,
  onRetry,
}: CatalogLayoutProps<T>) {
  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    onSearch();
  };
  const from = total === 0 ? 0 : skip + 1;
  const to = Math.min(skip + limit, total);

  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Справочник</p>
          <h1>{title}</h1>
          <p className="page-description">{description}</p>
        </div>
        <button className="button button--primary" type="button" onClick={onCreate}>
          <Plus size={18} aria-hidden="true" /> {createLabel}
        </button>
      </section>

      <section className="data-panel">
        <div className="catalog-toolbar">
          <form className="search-form" role="search" onSubmit={submitSearch}>
            <label className="search-control">
              <Search size={18} aria-hidden="true" />
              <span className="sr-only">Поиск</span>
              <input value={searchInput} onChange={(event) => onSearchInput(event.target.value)} placeholder="Поиск" />
            </label>
            <button className="button button--secondary" type="submit">Найти</button>
          </form>
          <label className="checkbox-control">
            <input type="checkbox" checked={includeArchived} onChange={(event) => onIncludeArchived(event.target.checked)} />
            Показывать архив
          </label>
        </div>

        {error ? (
          <div className="panel-padding"><ApiErrorNotice error={error} onRetry={onRetry} /></div>
        ) : loading ? (
          <div className="table-loading" aria-live="polite">Загрузка данных…</div>
        ) : items.length === 0 ? (
          <div className="compact-empty"><strong>Записи не найдены</strong><span>Измените фильтры или создайте первую запись.</span></div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr>{columns.map((column) => <th key={column.label}>{column.label}</th>)}<th><span className="sr-only">Действия</span></th></tr></thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className={item.archived_at ? "row--archived" : undefined}>
                    {columns.map((column) => <td key={column.label}>{column.render(item)}</td>)}
                    <td className="row-actions">
                      {!item.archived_at && (
                        <>
                          <button className="table-action" type="button" onClick={() => onEdit(item)} aria-label={`Изменить запись ${item.id}`}><Pencil size={17} /></button>
                          <button className="table-action table-action--danger" type="button" onClick={() => onArchive(item)} aria-label={`Архивировать запись ${item.id}`}><Archive size={17} /></button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <footer className="pagination">
          <span>{from}–{to} из {total}</span>
          <div>
            <button className="icon-button" type="button" disabled={skip === 0} onClick={onPrevious} aria-label="Предыдущая страница"><ChevronLeft /></button>
            <button className="icon-button" type="button" disabled={skip + limit >= total} onClick={onNext} aria-label="Следующая страница"><ChevronRight /></button>
          </div>
        </footer>
      </section>
    </div>
  );
}
