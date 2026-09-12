import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import type { Supplier, SupplierInput } from "../../api/catalogs";
import { ApiErrorNotice } from "../../components/ApiErrorNotice";
import { CatalogLayout, type CatalogColumn } from "../../components/CatalogLayout";
import { Modal } from "../../components/Modal";
import { formatDate, nullable } from "./formHelpers";
import { useCatalog } from "./useCatalog";

const schema = z.object({
  code: z.string().trim().min(1, "Укажите код").max(50, "Не более 50 символов"),
  name: z.string().trim().min(1, "Укажите наименование").max(200, "Не более 200 символов"),
  contact_person: z.string().max(100, "Не более 100 символов"),
  phone: z.string().max(50, "Не более 50 символов"),
  email: z.union([z.literal(""), z.email("Укажите корректный email")]),
  address: z.string().max(5000, "Адрес слишком длинный"),
});

type SupplierFormValues = z.infer<typeof schema>;

const columns: CatalogColumn<Supplier>[] = [
  { label: "Код", render: (supplier) => <strong>{supplier.code}</strong> },
  { label: "Наименование", render: (supplier) => supplier.name },
  { label: "Контакт", render: (supplier) => supplier.contact_person || "—" },
  { label: "Телефон", render: (supplier) => supplier.phone || "—" },
  { label: "Изменено", render: (supplier) => formatDate(supplier.updated_at) },
  { label: "Состояние", render: (supplier) => <span className={`status-pill ${supplier.archived_at ? "status-pill--archived" : "status-pill--active"}`}>{supplier.archived_at ? "В архиве" : "Активен"}</span> },
];

export function SupplierPage() {
  const catalog = useCatalog<Supplier, SupplierInput>("suppliers");
  const [editing, setEditing] = useState<Supplier | null | undefined>(undefined);
  const archive = async (supplier: Supplier) => {
    if (window.confirm(`Архивировать поставщика «${supplier.name}»?`)) {
      await catalog.archiveMutation.mutateAsync(supplier.id).catch(() => undefined);
    }
  };

  return (
    <>
      <CatalogLayout
        title="Поставщики"
        description="Контрагенты, от которых поступают материалы на склад."
        createLabel="Добавить поставщика"
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
        <SupplierForm
          supplier={editing}
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

function SupplierForm({ supplier, onClose, onSave }: { supplier: Supplier | null; onClose: () => void; onSave: (input: SupplierInput) => Promise<void> }) {
  const [submitError, setSubmitError] = useState<unknown>();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<SupplierFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: supplier?.code ?? "",
      name: supplier?.name ?? "",
      contact_person: supplier?.contact_person ?? "",
      phone: supplier?.phone ?? "",
      email: supplier?.email ?? "",
      address: supplier?.address ?? "",
    },
  });

  return (
    <Modal title={supplier ? "Изменить поставщика" : "Новый поставщик"} onClose={onClose}>
      <form className="entity-form" onSubmit={handleSubmit(async (values) => { setSubmitError(undefined); try { await onSave({ code: values.code, name: values.name, contact_person: nullable(values.contact_person), phone: nullable(values.phone), email: nullable(values.email), address: nullable(values.address) }); } catch (error) { setSubmitError(error); } })}>
        {submitError !== undefined && <ApiErrorNotice error={submitError} />}
        <div className="form-grid">
          <label><span>Код</span><input {...register("code")} autoFocus aria-invalid={Boolean(errors.code)} />{errors.code && <small>{errors.code.message}</small>}</label>
          <label><span>Наименование</span><input {...register("name")} aria-invalid={Boolean(errors.name)} />{errors.name && <small>{errors.name.message}</small>}</label>
          <label><span>Контактное лицо <em>необязательно</em></span><input {...register("contact_person")} />{errors.contact_person && <small>{errors.contact_person.message}</small>}</label>
          <label><span>Телефон <em>необязательно</em></span><input {...register("phone")} />{errors.phone && <small>{errors.phone.message}</small>}</label>
          <label><span>Email <em>необязательно</em></span><input type="email" {...register("email")} />{errors.email && <small>{errors.email.message}</small>}</label>
        </div>
        <label><span>Адрес <em>необязательно</em></span><textarea {...register("address")} rows={3} />{errors.address && <small>{errors.address.message}</small>}</label>
        <div className="form-actions"><button className="button button--secondary" type="button" onClick={onClose}>Отмена</button><button className="button button--primary" disabled={isSubmitting} type="submit">{isSubmitting ? "Сохранение…" : "Сохранить"}</button></div>
      </form>
    </Modal>
  );
}
