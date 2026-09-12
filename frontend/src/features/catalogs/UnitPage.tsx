import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { Unit, UnitInput } from "../../api/catalogs";
import { ApiErrorNotice } from "../../components/ApiErrorNotice";
import { CatalogLayout, type CatalogColumn } from "../../components/CatalogLayout";
import { Modal } from "../../components/Modal";
import { formatDate } from "./formHelpers";
import { useCatalog } from "./useCatalog";

const schema = z.object({
  code: z.string().trim().min(1, "Укажите код").max(50, "Не более 50 символов"),
  name: z.string().trim().min(1, "Укажите наименование").max(200, "Не более 200 символов"),
});

const columns: CatalogColumn<Unit>[] = [
  { label: "Код", render: (unit) => <strong>{unit.code}</strong> },
  { label: "Наименование", render: (unit) => unit.name },
  { label: "Изменено", render: (unit) => formatDate(unit.updated_at) },
  { label: "Состояние", render: (unit) => <span className={`status-pill ${unit.archived_at ? "status-pill--archived" : "status-pill--active"}`}>{unit.archived_at ? "В архиве" : "Активна"}</span> },
];

export function UnitPage() {
  const catalog = useCatalog<Unit, UnitInput>("units");
  const [editing, setEditing] = useState<Unit | null | undefined>(undefined);

  const archive = async (unit: Unit) => {
    if (window.confirm(`Архивировать единицу «${unit.name}»?`)) {
      await catalog.archiveMutation.mutateAsync(unit.id).catch(() => undefined);
    }
  };

  return (
    <>
      <CatalogLayout
        title="Единицы измерения"
        description="Единый справочник единиц хранения материалов. Используемые единицы нельзя архивировать."
        createLabel="Добавить единицу"
        columns={columns}
        items={catalog.query.data?.items ?? []}
        total={catalog.query.data?.total ?? 0}
        skip={catalog.skip}
        limit={catalog.limit}
        searchInput={catalog.searchInput}
        includeArchived={catalog.includeArchived}
        loading={catalog.query.isLoading}
        error={catalog.query.error ?? catalog.archiveMutation.error}
        onSearchInput={catalog.setSearchInput}
        onSearch={catalog.applySearch}
        onIncludeArchived={catalog.setIncludeArchived}
        onCreate={() => setEditing(null)}
        onEdit={setEditing}
        onArchive={archive}
        onPrevious={catalog.previous}
        onNext={catalog.next}
        onRetry={() => catalog.query.refetch()}
      />
      {editing !== undefined && (
        <UnitForm
          unit={editing}
          onClose={() => setEditing(undefined)}
          onSave={async (input) => {
            await catalog.saveMutation.mutateAsync({ id: editing?.id, input });
            setEditing(undefined);
          }}
        />
      )}
    </>
  );
}

function UnitForm({ unit, onClose, onSave }: { unit: Unit | null; onClose: () => void; onSave: (input: UnitInput) => Promise<void> }) {
  const [submitError, setSubmitError] = useState<unknown>();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<UnitInput>({
    resolver: zodResolver(schema),
    defaultValues: { code: unit?.code ?? "", name: unit?.name ?? "" },
  });

  return (
    <Modal title={unit ? "Изменить единицу" : "Новая единица"} onClose={onClose}>
      <form className="entity-form" onSubmit={handleSubmit(async (input) => { setSubmitError(undefined); try { await onSave(input); } catch (error) { setSubmitError(error); } })}>
        {submitError !== undefined && <ApiErrorNotice error={submitError} />}
        <label><span>Код</span><input {...register("code")} autoFocus aria-invalid={Boolean(errors.code)} />{errors.code && <small>{errors.code.message}</small>}</label>
        <label><span>Наименование</span><input {...register("name")} aria-invalid={Boolean(errors.name)} />{errors.name && <small>{errors.name.message}</small>}</label>
        <div className="form-actions"><button className="button button--secondary" type="button" onClick={onClose}>Отмена</button><button className="button button--primary" disabled={isSubmitting} type="submit">{isSubmitting ? "Сохранение…" : "Сохранить"}</button></div>
      </form>
    </Modal>
  );
}
