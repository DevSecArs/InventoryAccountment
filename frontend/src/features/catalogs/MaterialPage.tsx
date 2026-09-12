import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { listCatalog, type Material, type MaterialInput, type Unit } from "../../api/catalogs";
import { ApiErrorNotice } from "../../components/ApiErrorNotice";
import { CatalogLayout, type CatalogColumn } from "../../components/CatalogLayout";
import { Modal } from "../../components/Modal";
import { formatDate, nullable } from "./formHelpers";
import { useCatalog } from "./useCatalog";

const schema = z.object({
  sku: z.string().trim().min(1, "Укажите артикул").max(50, "Не более 50 символов"),
  name: z.string().trim().min(1, "Укажите наименование").max(200, "Не более 200 символов"),
  description: z.string().max(5000, "Описание слишком длинное"),
  unit_id: z.string().min(1, "Выберите единицу измерения"),
});

type MaterialFormValues = z.infer<typeof schema>;

export function MaterialPage() {
  const catalog = useCatalog<Material, MaterialInput>("materials");
  const units = useQuery({
    queryKey: ["units", "options"],
    queryFn: ({ signal }) => listCatalog<Unit>("units", { skip: 0, limit: 1000 }, signal),
  });
  const [editing, setEditing] = useState<Material | null | undefined>(undefined);
  const unitNames = new Map(units.data?.items.map((unit) => [unit.id, unit.name]));
  const columns: CatalogColumn<Material>[] = [
    { label: "Артикул", render: (material) => <strong>{material.sku}</strong> },
    { label: "Наименование", render: (material) => material.name },
    { label: "Единица", render: (material) => unitNames.get(material.unit_id) ?? material.unit_id },
    { label: "Изменено", render: (material) => formatDate(material.updated_at) },
    { label: "Состояние", render: (material) => <span className={`status-pill ${material.archived_at ? "status-pill--archived" : "status-pill--active"}`}>{material.archived_at ? "В архиве" : "Активен"}</span> },
  ];

  const archive = async (material: Material) => {
    if (window.confirm(`Архивировать материал «${material.name}»?`)) {
      await catalog.archiveMutation.mutateAsync(material.id).catch(() => undefined);
    }
  };

  return (
    <>
      <CatalogLayout
        title="Материалы"
        description="Номенклатура склада с закреплёнными единицами измерения."
        createLabel="Добавить материал"
        columns={columns}
        items={catalog.query.data?.items ?? []}
        total={catalog.query.data?.total ?? 0}
        skip={catalog.skip}
        limit={catalog.limit}
        searchInput={catalog.searchInput}
        includeArchived={catalog.includeArchived}
        loading={catalog.query.isLoading || units.isLoading}
        error={catalog.query.error ?? units.error ?? catalog.archiveMutation.error}
        onSearchInput={catalog.setSearchInput}
        onSearch={catalog.applySearch}
        onIncludeArchived={catalog.setIncludeArchived}
        onCreate={() => setEditing(null)}
        onEdit={setEditing}
        onArchive={archive}
        onPrevious={catalog.previous}
        onNext={catalog.next}
        onRetry={() => { catalog.query.refetch(); units.refetch(); }}
      />
      {editing !== undefined && (
        <MaterialForm
          material={editing}
          units={units.data?.items ?? []}
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

function MaterialForm({ material, units, onClose, onSave }: { material: Material | null; units: Unit[]; onClose: () => void; onSave: (input: MaterialInput) => Promise<void> }) {
  const [submitError, setSubmitError] = useState<unknown>();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<MaterialFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      sku: material?.sku ?? "",
      name: material?.name ?? "",
      description: material?.description ?? "",
      unit_id: material?.unit_id ?? "",
    },
  });

  return (
    <Modal title={material ? "Изменить материал" : "Новый материал"} onClose={onClose}>
      <form className="entity-form" onSubmit={handleSubmit(async (values) => { setSubmitError(undefined); try { await onSave({ ...values, description: nullable(values.description) }); } catch (error) { setSubmitError(error); } })}>
        {submitError !== undefined && <ApiErrorNotice error={submitError} />}
        <div className="form-grid">
          <label><span>Артикул</span><input {...register("sku")} autoFocus aria-invalid={Boolean(errors.sku)} />{errors.sku && <small>{errors.sku.message}</small>}</label>
          <label><span>Единица измерения</span><select {...register("unit_id")} aria-invalid={Boolean(errors.unit_id)}><option value="">Выберите единицу</option>{units.map((unit) => <option key={unit.id} value={unit.id}>{unit.code} — {unit.name}</option>)}</select>{errors.unit_id && <small>{errors.unit_id.message}</small>}</label>
        </div>
        <label><span>Наименование</span><input {...register("name")} aria-invalid={Boolean(errors.name)} />{errors.name && <small>{errors.name.message}</small>}</label>
        <label><span>Описание <em>необязательно</em></span><textarea {...register("description")} rows={4} />{errors.description && <small>{errors.description.message}</small>}</label>
        <div className="form-actions"><button className="button button--secondary" type="button" onClick={onClose}>Отмена</button><button className="button button--primary" disabled={isSubmitting} type="submit">{isSubmitting ? "Сохранение…" : "Сохранить"}</button></div>
      </form>
    </Modal>
  );
}
