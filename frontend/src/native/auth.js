import { login, register, updateProfile } from '../api/auth.js';
import { element, button, field, errorNotice, heading } from './dom.js';

export function credentialErrors(values, registration, emailInvalid = false) {
  const errors = {};
  if (values.login.trim().length < 3) errors.login = 'Минимум 3 символа';
  if (!values.password) errors.password = 'Введите пароль';
  else if (registration && values.password.length < 12) errors.password = 'Минимум 12 символов';
  if (registration && !values.full_name.trim()) errors.full_name = 'Укажите имя';
  if (registration && emailInvalid) errors.email = 'Некорректный email';
  return errors;
}

export function profileInput(values) {
  const name = values.full_name.trim();
  if (!name) {
    throw new Error('Укажите имя');
  }
  return { full_name: name, email: values.email || null };
}

function showFieldErrors(form, errors) {
  for (const input of form.querySelectorAll('input')) {
    input.removeAttribute('aria-invalid');
    input.parentElement.querySelector('small')?.remove();
    if (errors[input.name]) {
      input.setAttribute('aria-invalid', 'true');
      input.parentElement.append(element('small', '', errors[input.name]));
    }
  }
}

export function loginPage(root, onAuth, signal) {
  let registration = false;
  function render() {
    const main = element('main', 'auth-page');
    const card = element('section', 'auth-card');
    card.append(element('p', 'eyebrow', 'Складской учёт'), element('h1', '', registration ? 'Первичный доступ' : 'Вход'), element('p', '', 'Используйте учётные данные для доступа к справочникам.'));
    const form = element('form', 'entity-form');
    form.noValidate = true;
    if (registration) form.append(field('Имя', 'full_name', { required: true }));
    form.append(field('Логин', 'login', { required: true, minLength: 3 }));
    if (registration) form.append(field('Email', 'email', { type: 'email' }));
    form.append(field('Пароль', 'password', { type: 'password', required: true, minLength: registration ? 12 : 1 }));
    form.elements.login.autocomplete = 'username';
    form.elements.password.autocomplete = registration ? 'new-password' : 'current-password';
    const submit = element('button', 'button button--primary', registration ? 'Создать администратора' : 'Войти'); submit.type = 'submit'; form.append(submit);
    const toggle = button(registration ? 'У меня уже есть учётная запись' : 'Создать первого администратора', 'text-button', () => { registration = !registration; render(); });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      form.querySelector('.error-notice')?.remove();
      const values = Object.fromEntries(new FormData(form));
      const errors = credentialErrors(values, registration, registration && form.elements.email.validity.typeMismatch);
      showFieldErrors(form, errors);
      if (Object.keys(errors).length) return;
      values.login = values.login.trim();
      if (registration) { values.full_name = values.full_name.trim(); if (!values.email) delete values.email; }
      submit.disabled = true; toggle.disabled = true;
      try { const result = await (registration ? register(values, signal) : login(values, signal)); if (!signal.aborted) onAuth(result); }
      catch (error) { if (!signal.aborted) form.prepend(errorNotice(error)); }
      finally { submit.disabled = false; toggle.disabled = false; }
    });
    card.append(form, toggle);
    main.append(card); root.replaceChildren(main); form.querySelector('input')?.focus();
  }
  render();
}

export function profilePage(root, user, onUpdate, signal) {
  const page = element('div', 'page-stack');
  page.append(heading('Учётная запись', 'Личный кабинет', 'Изменяйте только свои контактные данные. Роль назначается администратором.'));
  const card = element('section', 'profile-card');
  const meta = element('div', 'profile-meta');
  meta.append(element('strong', '', user.login), element('span', '', `Роль: ${user.role === 'admin' ? 'администратор' : user.role === 'reporter' ? 'наблюдатель' : 'оператор'}`));
  const form = element('form', 'entity-form');
  form.append(field('Имя', 'full_name', { required: true, value: user.full_name }), field('Email', 'email', { type: 'email', value: user.email }));
  const save = element('button', 'button button--primary', 'Сохранить'); save.type = 'submit'; form.append(save);
  form.addEventListener('submit', async event => {
    event.preventDefault(); form.querySelector('.error-notice')?.remove(); let values;
    try { values = profileInput(Object.fromEntries(new FormData(form))); }
    catch (error) { form.prepend(errorNotice(error)); return; }
    save.disabled = true;
    try { const updated = await updateProfile(values, signal); if (!signal.aborted) onUpdate(updated); }
    catch (error) { if (!signal.aborted) form.prepend(errorNotice(error)); }
    finally { save.disabled = false; }
  });
  card.append(meta, form); page.append(card); root.replaceChildren(page);
}
