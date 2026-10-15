import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useState } from 'react';

import { ApiErrorNotice } from '../../components/ApiErrorNotice';
import { Modal } from '../../components/Modal';
import { useAuth } from '../auth/AuthProvider';
import {
  createReceipt,
  deleteReceipt,
  getReceiptHistory,
  listReceipts,
  postReceipt,
  type Receipt,
} from '../../api/receipts';
import {
  listCatalog,
  type Material,
  type Supplier,
  type Unit,
} from '../../api/catalogs';

const pageSize = 20;
const statusLabel: Record<string, string> = {
  draft: 'Черновик',
  posted: 'Проведено',
};

function localIso(value: string) {
  return new Date(value).toISOString();
}

export function ReceiptsPage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const [skip, setSkip] = useState(0);
  const [search, setSearch] = useState('');
  const [appliedSearch, setAppliedSearch] = useState('');
  const [dialog, setDialog] = useState<'create' | Receipt | null>(null);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const writer = user?.role === 'admin' || user?.role === 'operator';
  const receipts = useQuery({
    queryKey: ['receipts', skip, appliedSearch],
    queryFn: ({ signal }) =>
      listReceipts({ skip, limit: pageSize, search: appliedSearch }, signal),
  });
  const history = useQuery({
    queryKey: ['receipt-history', historyId],
    queryFn: () => getReceiptHistory(historyId ?? ''),
    enabled: Boolean(historyId),
  });
  const post = useMutation({
    mutationFn: postReceipt,
    onSuccess: () => client.invalidateQueries({ queryKey: ['receipts'] }),
  });
  const remove = useMutation({
    mutationFn: deleteReceipt,
    onSuccess: () => client.invalidateQueries({ queryKey: ['receipts'] }),
  });
  const apply = () => {
    setSkip(0);
    setAppliedSearch(search.trim());
  };
  return (
    <div className="page-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">Документы</p>
          <h1>Поступления</h1>
          <p className="page-description">
            Черновики проводятся синхронно и после проведения доступны только
            для просмотра.
          </p>
        </div>
        {writer && (
          <button
            className="button button--primary"
            onClick={() => setDialog('create')}
          >
            <Plus size={18} /> Создать поступление
          </button>
        )}
      </section>
      {(receipts.error || post.error || remove.error) && (
        <ApiErrorNotice
          error={receipts.error ?? post.error ?? remove.error}
          onRetry={() => receipts.refetch()}
        />
      )}
      <section className="data-panel">
        <div className="catalog-toolbar">
          <form
            className="search-form"
            onSubmit={(event) => {
              event.preventDefault();
              apply();
            }}
          >
            <label className="search-control">
              <span className="sr-only">Номер документа</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Номер документа"
              />
            </label>
            <button className="button button--secondary">Найти</button>
          </form>
        </div>
        {receipts.isPending ? (
          <div className="table-loading">Загрузка…</div>
        ) : receipts.data?.items.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Номер</th>
                  <th>Поставщик</th>
                  <th>Дата</th>
                  <th>Статус</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {receipts.data.items.map((receipt) => (
                  <tr key={receipt.id}>
                    <td>{receipt.document_number}</td>
                    <td>{receipt.supplier_name ?? receipt.supplier_id}</td>
                    <td>{new Date(receipt.received_at).toLocaleString()}</td>
                    <td>{statusLabel[receipt.status] ?? receipt.status}</td>
                    <td className="row-actions receipt-actions">
                      <button
                        className="table-action"
                        onClick={() => setDialog(receipt)}
                      >
                        Открыть
                      </button>
                      {receipt.status === 'draft' && writer && (
                        <>
                          <button
                            className="table-action"
                            disabled={post.isPending}
                            onClick={() => {
                              if (
                                confirm(
                                  'Провести документ? После этого его нельзя будет изменить.',
                                )
                              )
                                post.mutate(receipt.id);
                            }}
                          >
                            Провести
                          </button>
                          <button
                            className="table-action table-action--danger"
                            disabled={remove.isPending}
                            onClick={() => {
                              if (confirm('Удалить черновик?'))
                                remove.mutate(receipt.id);
                            }}
                          >
                            Удалить
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="compact-empty">
            Нет поступлений по заданным условиям.
          </div>
        )}
        <div className="pagination">
          <span>Всего: {receipts.data?.total ?? 0}</span>
          <div>
            <button
              className="button button--secondary"
              disabled={skip === 0}
              onClick={() => setSkip(Math.max(0, skip - pageSize))}
            >
              Назад
            </button>
            <button
              className="button button--secondary"
              disabled={
                !receipts.data || skip + pageSize >= receipts.data.total
              }
              onClick={() => setSkip(skip + pageSize)}
            >
              Далее
            </button>
          </div>
        </div>
      </section>
      {dialog === 'create' && (
        <ReceiptCreateDialog onClose={() => setDialog(null)} />
      )}
      {dialog && dialog !== 'create' && (
        <Modal
          title={`Поступление ${dialog.document_number}`}
          onClose={() => setDialog(null)}
        >
          <div className="entity-form">
            <p>
              <strong>{statusLabel[dialog.status] ?? dialog.status}</strong>
            </p>
            {dialog.items.map((item) => (
              <p key={item.id}>
                {item.material_name ?? item.material_id}: {item.quantity}{' '}
                {item.unit_code ?? ''}
              </p>
            ))}
            <button
              className="button button--secondary"
              onClick={() => setHistoryId(dialog.id)}
            >
              Показать историю
            </button>
          </div>
        </Modal>
      )}
      {historyId && (
        <Modal title="История статусов" onClose={() => setHistoryId(null)}>
          <div className="entity-form">
            {history.data?.items.length ? (
              history.data.items.map((item) => (
                <p key={item.id}>
                  {new Date(item.changed_at).toLocaleString()}:{' '}
                  {statusLabel[item.from_status] ?? item.from_status} →{' '}
                  {statusLabel[item.to_status] ?? item.to_status}
                </p>
              ))
            ) : (
              <p>История для документа до внедрения функции отсутствует.</p>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

function ReceiptCreateDialog({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const [supplierId, setSupplierId] = useState('');
  const [materialId, setMaterialId] = useState('');
  const [number, setNumber] = useState('');
  const [date, setDate] = useState('');
  const [quantity, setQuantity] = useState('');
  const suppliers = useQuery({
    queryKey: ['suppliers', 'all'],
    queryFn: () => listCatalog<Supplier>('suppliers', { skip: 0, limit: 1000 }),
  });
  const materials = useQuery({
    queryKey: ['materials', 'all'],
    queryFn: () => listCatalog<Material>('materials', { skip: 0, limit: 1000 }),
  });
  const units = useQuery({
    queryKey: ['units', 'receipt'],
    queryFn: () =>
      listCatalog<Unit>('units', {
        skip: 0,
        limit: 1000,
        includeArchived: true,
      }),
  });
  const create = useMutation({
    mutationFn: createReceipt,
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['receipts'] });
      onClose();
    },
  });
  const validQuantity = /^\d+(\.\d{1,3})?$/.test(quantity) && quantity !== '0';
  const selectedMaterial = materials.data?.items.find(
    (item) => item.id === materialId,
  );
  const unit = units.data?.items.find(
    (item) => item.id === selectedMaterial?.unit_id,
  );
  return (
    <Modal title="Новое поступление" onClose={onClose}>
      <form
        className="entity-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!validQuantity || !date) return;
          create.mutate({
            supplier_id: supplierId,
            document_number: number,
            received_at: localIso(date),
            items: [{ material_id: materialId, quantity }],
          });
        }}
      >
        <label>
          Поставщик
          <select
            required
            value={supplierId}
            onChange={(event) => setSupplierId(event.target.value)}
          >
            <option value="">Выберите поставщика</option>
            {suppliers.data?.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Номер документа
          <input
            required
            value={number}
            onChange={(event) => setNumber(event.target.value)}
          />
        </label>
        <label>
          Дата и время <em>будет отправлено с часовым поясом браузера</em>
          <input
            required
            type="datetime-local"
            value={date}
            onChange={(event) => setDate(event.target.value)}
          />
        </label>
        <label>
          Материал
          <select
            required
            value={materialId}
            onChange={(event) => setMaterialId(event.target.value)}
          >
            <option value="">Выберите материал</option>
            {materials.data?.items.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Количество{unit && ` (${unit.code})`}</span>
          <input
            required
            inputMode="decimal"
            value={quantity}
            aria-invalid={quantity !== '' && !validQuantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
          {quantity && !validQuantity && (
            <small>
              Укажите положительное число не более чем с тремя знаками.
            </small>
          )}
        </label>
        {create.error && (
          <ApiErrorNotice error={create.error} onRetry={() => create.reset()} />
        )}
        <div className="form-actions">
          <button
            className="button button--secondary"
            type="button"
            onClick={onClose}
          >
            Отмена
          </button>
          <button
            className="button button--primary"
            disabled={create.isPending || !validQuantity}
          >
            Сохранить
          </button>
        </div>
      </form>
    </Modal>
  );
}
