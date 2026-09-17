import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate } from "react-router-dom";
import { z } from "zod";

import { ApiErrorNotice } from "../../components/ApiErrorNotice";
import { useAuth } from "./AuthProvider";

const loginSchema = z.object({ login: z.string().trim().min(3, "Минимум 3 символа"), password: z.string().min(1, "Введите пароль") });
const registerSchema = loginSchema.extend({ full_name: z.string().trim().min(1, "Укажите имя"), email: z.string().email("Некорректный email").or(z.literal("")) }).refine((value) => value.password.length >= 12, { path: ["password"], message: "Минимум 12 символов" });
type LoginValues = z.infer<typeof loginSchema>;
type RegisterValues = z.infer<typeof registerSchema>;

export function LoginPage() {
  const { user, login, register } = useAuth();
  const [registerMode, setRegisterMode] = useState(false);
  const [error, setError] = useState<unknown>();
  const loginForm = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { login: "", password: "" } });
  const registerForm = useForm<RegisterValues>({ resolver: zodResolver(registerSchema), defaultValues: { login: "", password: "", full_name: "", email: "" } });
  if (user) return <Navigate to="/" replace />;
  const submitLogin = loginForm.handleSubmit(async (values) => { setError(undefined); try { await login(values); } catch (reason) { setError(reason); } });
  const submitRegister = registerForm.handleSubmit(async (values) => { setError(undefined); try { await register({ ...values, email: values.email || undefined }); } catch (reason) { setError(reason); } });
  const form = registerMode ? registerForm : loginForm;
  return <main className="auth-page"><section className="auth-card"><p className="eyebrow">Складской учёт</p><h1>{registerMode ? "Первичный доступ" : "Вход"}</h1><p>Используйте учётные данные для доступа к справочникам.</p>{error !== undefined && <ApiErrorNotice error={error} />}
    {registerMode ? <form className="entity-form" onSubmit={submitRegister}><label><span>Имя</span><input {...registerForm.register("full_name")} autoFocus />{registerForm.formState.errors.full_name && <small>{registerForm.formState.errors.full_name.message}</small>}</label><label><span>Логин</span><input {...registerForm.register("login")} />{registerForm.formState.errors.login && <small>{registerForm.formState.errors.login.message}</small>}</label><label><span>Email</span><input type="email" {...registerForm.register("email")} />{registerForm.formState.errors.email && <small>{registerForm.formState.errors.email.message}</small>}</label><label><span>Пароль</span><input type="password" autoComplete="new-password" {...registerForm.register("password")} />{registerForm.formState.errors.password && <small>{registerForm.formState.errors.password.message}</small>}</label><button className="button button--primary" disabled={form.formState.isSubmitting} type="submit">Создать администратора</button></form> : <form className="entity-form" onSubmit={submitLogin}><label><span>Логин</span><input autoFocus autoComplete="username" {...loginForm.register("login")} />{loginForm.formState.errors.login && <small>{loginForm.formState.errors.login.message}</small>}</label><label><span>Пароль</span><input type="password" autoComplete="current-password" {...loginForm.register("password")} />{loginForm.formState.errors.password && <small>{loginForm.formState.errors.password.message}</small>}</label><button className="button button--primary" disabled={form.formState.isSubmitting} type="submit">Войти</button></form>}
    <button className="text-button" type="button" onClick={() => { setError(undefined); setRegisterMode((value) => !value); }}>{registerMode ? "У меня уже есть учётная запись" : "Создать первого администратора"}</button></section></main>;
}
