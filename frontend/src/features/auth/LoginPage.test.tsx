import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const auth = vi.hoisted(() => ({ login: vi.fn(), register: vi.fn(), user: null }));
vi.mock('./AuthProvider', () => ({ useAuth: () => auth }));

import { LoginPage } from './LoginPage';

describe('LoginPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('проверяет обязательные поля входа', async () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
    expect(await screen.findByText('Минимум 3 символа')).toBeInTheDocument();
    expect(screen.getByText('Введите пароль')).toBeInTheDocument();
    expect(auth.login).not.toHaveBeenCalled();
  });

  it('показывает ошибку авторизации', async () => {
    auth.login.mockRejectedValueOnce(new Error('Неверный пароль'));
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'user' } });
    fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'secret' } });
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Неверный пароль'));
  });

  it('проверяет требования регистрации администратора', async () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Создать первого администратора' }));
    fireEvent.click(screen.getByRole('button', { name: 'Создать администратора' }));
    expect(await screen.findByText('Укажите имя')).toBeInTheDocument();
    expect(screen.getByText('Минимум 12 символов')).toBeInTheDocument();
    expect(auth.register).not.toHaveBeenCalled();
  });
});
