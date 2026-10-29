import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';

const user = {
  id: 'u1',
  login: 'admin',
  full_name: 'Администратор',
  email: null,
  role: 'admin',
};

beforeEach(() => {
  window.history.replaceState({}, '', '/');
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path.includes('/auth/me'))
        return Response.json({ user, csrf_token: 'csrf' });
      if (path.includes('/health/')) return Response.json({ status: 'ok' });
      if (path.includes('si-options')) return Response.json([]);
      if (path.includes('/auth/logout'))
        return new Response(null, { status: 204 });
      return Response.json({ items: [], total: 0, skip: 0, limit: 20 });
    }),
  );
});

describe('App', () => {
  it('проверяет сессию и открывает защищённый обзор', async () => {
    render(<App />);
    expect(screen.getByText('Проверка сессии…')).toBeInTheDocument();
    expect(await screen.findByText('Принимает запросы')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Открыть личный кабинет' }),
    ).toHaveTextContent(user.full_name);
  });

  it('перенаправляет неавторизованного пользователя на вход', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        Response.json({ message: 'Требуется авторизация' }, { status: 401 }),
      ),
    );
    render(<App />);
    expect(
      await screen.findByRole('heading', { name: 'Вход' }),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe('/login');
  });

  it.each([
    ['/units', 'Единицы измерения', 'Добавить единицу'],
    ['/materials', 'Материалы', 'Добавить материал'],
    ['/suppliers', 'Поставщики', 'Добавить поставщика'],
  ])(
    'открывает справочник %s и форму создания',
    async (path, title, create) => {
      window.history.replaceState({}, '', path);
      render(<App />);
      expect(
        await screen.findByRole('heading', { name: title }),
      ).toBeInTheDocument();
      fireEvent.click(await screen.findByRole('button', { name: create }));
      expect(await screen.findByRole('dialog')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Закрыть' }));
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    },
  );

  it('открывает профиль и завершает сеанс', async () => {
    window.history.replaceState({}, '', '/profile');
    render(<App />);
    expect(await screen.findByDisplayValue(user.full_name)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }));
    expect(
      await screen.findByRole('heading', { name: 'Вход' }),
    ).toBeInTheDocument();
  });
});
