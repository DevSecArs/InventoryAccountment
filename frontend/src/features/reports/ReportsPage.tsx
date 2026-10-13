import { useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { listCatalog, type Material, type Supplier } from '../../api/catalogs';
import { exportSupplyReport, getSupplyReport } from '../../api/reports';
import { ApiErrorNotice } from '../../components/ApiErrorNotice';

function asIso(value: string) { return new Date(value).toISOString(); }

export function ReportsPage() {
  const [params, setParams] = useSearchParams();
  const [exportError, setExportError] = useState<unknown>(null);
  const from = params.get('from') ?? ''; const to = params.get('to') ?? ''; const supplierId = params.get('supplier_id') ?? ''; const materialId = params.get('material_id') ?? ''; const skip = Number(params.get('skip') ?? '0');
  const enabled = Boolean(from && to);
  const report = useQuery({ queryKey: ['supply-report', from, to, supplierId, materialId, skip], queryFn: ({ signal }) => getSupplyReport({ from, to, supplierId: supplierId || undefined, materialId: materialId || undefined, skip, limit: 50 }, signal), enabled });
  const suppliers = useQuery({ queryKey: ['suppliers', 'report'], queryFn: () => listCatalog<Supplier>('suppliers', { skip: 0, limit: 1000, includeArchived: true }) });
  const materials = useQuery({ queryKey: ['materials', 'report'], queryFn: () => listCatalog<Material>('materials', { skip: 0, limit: 1000, includeArchived: true }) });
  const update = (name: string, value: string) => { const next = new URLSearchParams(params); if (value) next.set(name, value); else next.delete(name); if (name !== 'skip') next.set('skip', '0'); setParams(next); };
  const download = async () => { try { setExportError(null); const blob = await exportSupplyReport({ from, to, supplierId: supplierId || undefined, materialId: materialId || undefined }); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'supplies.csv'; anchor.click(); URL.revokeObjectURL(url); } catch (error: unknown) { setExportError(error); } };
  return <div className="page-stack"><section className="page-heading"><div><p className="eyebrow">Аналитика</p><h1>Отчёт по поставкам</h1><p className="page-description">В отчёт входят только проведённые поступления. Итоги разделены по единицам измерения.</p></div><button className="button button--secondary" disabled={!enabled} onClick={download}><Download size={18}/> Скачать CSV</button></section>
    <section className="filter-panel"><div className="report-filters"><label>Начало периода<input type="datetime-local" value={from} onChange={(event) => update('from', event.target.value ? asIso(event.target.value) : '')}/></label><label>Конец периода<input type="datetime-local" value={to} onChange={(event) => update('to', event.target.value ? asIso(event.target.value) : '')}/></label><label>Поставщик<select value={supplierId} onChange={(event) => update('supplier_id', event.target.value)}><option value="">Все поставщики</option>{suppliers.data?.items.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><label>Материал<select value={materialId} onChange={(event) => update('material_id', event.target.value)}><option value="">Все материалы</option>{materials.data?.items.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label></div></section>
    {(report.error != null || exportError != null) && <ApiErrorNotice error={report.error ?? exportError} onRetry={() => report.refetch()}/>}<section className="data-panel">{!enabled ? <div className="compact-empty">Укажите начало и конец периода.</div> : report.isPending ? <div className="table-loading">Формирование отчёта…</div> : report.data?.items.length ? <div className="table-scroll"><table><thead><tr><th>Дата</th><th>Документ</th><th>Поставщик</th><th>Материал</th><th>Количество</th></tr></thead><tbody>{report.data.items.map((item) => <tr key={`${item.receipt_id}-${item.material_id}`}><td>{new Date(item.received_at).toLocaleString()}</td><td>{item.document_number}</td><td>{item.supplier_name}</td><td>{item.material_name} ({item.unit_code})</td><td>{item.quantity}</td></tr>)}</tbody></table></div> : <div className="compact-empty">За период нет проведённых поступлений.</div>} {report.data && <div className="panel panel-padding"><strong>Итоги</strong>{report.data.totals.map((item) => <p key={`${item.material_id}-${item.unit_id}`}>{item.material_name}: {item.quantity} {item.unit_code}</p>)}</div>}<div className="pagination"><span>Всего строк: {report.data?.total ?? 0}</span><div><button className="button button--secondary" disabled={skip === 0} onClick={() => update('skip', String(Math.max(0, skip - 50)))}>Назад</button><button className="button button--secondary" disabled={!report.data || skip + 50 >= report.data.total} onClick={() => update('skip', String(skip + 50))}>Далее</button></div></div></section></div>;
}
