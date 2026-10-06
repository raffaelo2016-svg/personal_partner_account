import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router';

vi.mock('react-router', async (load) => {
  const actual = await load<typeof import('react-router')>();
  return { ...actual, createBrowserRouter: (routes: Parameters<typeof actual.createMemoryRouter>[0]) => actual.createMemoryRouter(routes) };
});
const session = vi.hoisted(() => ({ role: 'partner' as 'partner' | 'admin' }));
vi.mock('./store/authStore', () => ({
  useHasHydrated: () => true,
  useAuthStore: (selector: (state: unknown) => unknown) => selector({ user: { role: session.role } }),
}));
vi.mock('./guards/AuthGuard', () => ({ default: () => <Outlet /> }));
vi.mock('./pages/Layout', () => ({ default: () => <div>Partner layout<Outlet /></div> }));
vi.mock('./pages/AdminLayout', () => ({ default: () => <div>Admin layout<Outlet /></div> }));
vi.mock('./pages/Dashboard', () => ({ default: () => <div>Partner home</div> }));
vi.mock('./pages/AdminDashboard', () => ({ default: () => <div>Admin home</div> }));
vi.mock('./pages/Login', () => ({ default: () => <div>Login</div> }));
import { router } from './routes';

afterEach(cleanup);
describe('Role restrictions on actual cabinet routes', () => {
  it('redirects partner from admin to partner dashboard', async () => {
    session.role = 'partner';
    const testRouter = createMemoryRouter(router.routes, { initialEntries: ['/admin'] });
    render(<RouterProvider router={testRouter} />);
    expect(await screen.findByText('Partner home')).toBeInTheDocument();
    expect(screen.queryByText('Admin layout')).not.toBeInTheDocument();
    expect(testRouter.state.location.pathname).toBe('/dashboard');
  });
  it('redirects admin from partner dashboard to admin dashboard', async () => {
    session.role = 'admin';
    const testRouter = createMemoryRouter(router.routes, { initialEntries: ['/dashboard'] });
    render(<RouterProvider router={testRouter} />);
    expect(await screen.findByText('Admin home')).toBeInTheDocument();
    expect(screen.queryByText('Partner layout')).not.toBeInTheDocument();
    expect(testRouter.state.location.pathname).toBe('/admin');
  });
});
