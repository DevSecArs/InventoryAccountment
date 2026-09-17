import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { updateProfile } from "../../api/auth";
import { ApiErrorNotice } from "../../components/ApiErrorNotice";
import { useAuth } from "./AuthProvider";

const schema = z.object({ full_name: z.string().trim().min(1, "Укажите имя"), email: z.string().email("Некорректный email").or(z.literal("")) });
type ProfileValues = z.infer<typeof schema>;

export function ProfilePage() {
  const { user, updateUser } = useAuth();
  const [error, setError] = useState<unknown>();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<ProfileValues>({ resolver: zodResolver(schema), values: { full_name: user?.full_name ?? "", email: user?.email ?? "" } });
  if (!user) return null;
  return <div className="page-stack"><section className="page-heading"><div><p className="eyebrow">Учётная запись</p><h1>Личный кабинет</h1><p className="page-description">Изменяйте только свои контактные данные. Роль назначается администратором.</p></div></section><section className="profile-card"><div className="profile-meta"><strong>{user.login}</strong><span>Роль: {user.role === "admin" ? "администратор" : "оператор"}</span></div><form className="entity-form" onSubmit={handleSubmit(async (values) => { setError(undefined); try { const updated = await updateProfile({ ...values, email: values.email || null }); updateUser(updated); } catch (reason) { setError(reason); } })}>{error !== undefined && <ApiErrorNotice error={error} />}<label><span>Имя</span><input {...register("full_name")} aria-invalid={Boolean(errors.full_name)} />{errors.full_name && <small>{errors.full_name.message}</small>}</label><label><span>Email</span><input type="email" {...register("email")} aria-invalid={Boolean(errors.email)} />{errors.email && <small>{errors.email.message}</small>}</label><div className="form-actions"><button className="button button--primary" type="submit" disabled={isSubmitting}>{isSubmitting ? "Сохранение…" : "Сохранить"}</button></div></form></section></div>;
}
