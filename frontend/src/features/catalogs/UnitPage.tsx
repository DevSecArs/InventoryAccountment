import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { listSiUnitOptions, type SiUnitOption, type Unit, type UnitInput } from "../../api/catalogs";
import { ApiErrorNotice } from "../../components/ApiErrorNotice";
import { CatalogLayout, type CatalogColumn } from "../../components/CatalogLayout";
import { Modal } from "../../components/Modal";
import { formatDate } from "./formHelpers";
import { useCatalog } from "./useCatalog";
import { useAuth } from "../auth/AuthProvider";

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
  const { user } = useAuth();
  const catalog = useCatalog<Unit, UnitInput>("units");
  const siOptions = useQuery({ queryKey: ["units", "si-options"], queryFn: ({ signal }) => listSiUnitOptions(signal) });
  const [editing, setEditing] = useState<Unit | null | undefined>(undefined);

  const archive = async (unit: Unit) => {
    if (window.confirm(`Архивировать единицу «${unit.name}»?`)) {
      await catalog.archiveMutation.mutateAsync(unit.id).catch(() => undefined);
    }
  };
  const purge = async (unit: Unit) => {
    if (window.confirm(`Безвозвратно удалить архивную единицу «${unit.name}»?`)) await catalog.purgeMutation.mutateAsync(unit.id).catch(() => undefined);
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
        loading={catalog.query.isLoading || siOptions.isLoading}
        error={catalog.query.error ?? siOptions.error ?? catalog.archiveMutation.error ?? catalog.purgeMutation.error}
        onSearchInput={catalog.setSearchInput}
        onSearch={catalog.applySearch}
        onIncludeArchived={catalog.setIncludeArchived}
        onCreate={() => setEditing(null)}
        onEdit={setEditing}
        onArchive={archive}
        onPurge={purge}
        canPurge={user?.role === "admin"}
        onPrevious={catalog.previous}
        onNext={catalog.next}
        onRetry={() => catalog.query.refetch()}
      />
      {editing !== undefined && (
        <UnitForm
          unit={editing}
          siOptions={siOptions.data ?? []}
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

function UnitForm({ unit, siOptions, onClose, onSave }: { unit: Unit | null; siOptions: SiUnitOption[]; onClose: () => void; onSave: (input: UnitInput) => Promise<void> }) {
  const [submitError, setSubmitError] = useState<unknown>();
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<UnitInput>({
    resolver: zodResolver(schema),
    defaultValues: { code: unit?.code ?? "", name: unit?.name ?? "" },
  });

  return (
    <Modal title={unit ? "Изменить единицу" : "Новая единица"} onClose={onClose}>
      <form className="entity-form" onSubmit={handleSubmit(async (input) => { setSubmitError(undefined); try { await onSave(input); } catch (error) { setSubmitError(error); } })}>
        {submitError !== undefined && <ApiErrorNotice error={submitError} />}
        {unit ? <><label><span>Код</span><input {...register("code")} autoFocus aria-invalid={Boolean(errors.code)} />{errors.code && <small>{errors.code.message}</small>}</label><label><span>Наименование</span><input {...register("name")} aria-invalid={Boolean(errors.name)} />{errors.name && <small>{errors.name.message}</small>}</label></> : <label><span>Единица СИ</span><select autoFocus {...register("code", { onChange: (event) => { const selected = siOptions.find((option) => option.code === event.target.value); setValue("name", selected?.name ?? "", { shouldValidate: true }); } })} aria-invalid={Boolean(errors.code)}><option value="">Выберите единицу</option>{siOptions.map((option) => <option key={option.code} value={option.code}>{option.code} — {option.name}</option>)}</select>{errors.code && <small>{errors.code.message}</small>}<em>Код и наименование устанавливаются из справочника СИ.</em><input type="hidden" {...register("name")} /></label>}
        <div className="form-actions"><button className="button button--secondary" type="button" onClick={onClose}>Отмена</button><button className="button button--primary" disabled={isSubmitting} type="submit">{isSubmitting ? "Сохранение…" : "Сохранить"}</button></div>
      </form>
    </Modal>
  );
}
