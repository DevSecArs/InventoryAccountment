import {
  Boxes,
  ChartNoAxesCombined,
  ClipboardList,
  Gauge,
  Menu,
  PackageOpen,
  Ruler,
  Settings,
  Truck,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

const navigation = [
  { to: "/", label: "Обзор", icon: Gauge, end: true },
  { to: "/units", label: "Единицы измерения", icon: Ruler },
  { to: "/materials", label: "Материалы", icon: Boxes },
  { to: "/suppliers", label: "Поставщики", icon: Truck },
  { to: "/receipts", label: "Поступления", icon: ClipboardList },
  { to: "/reports", label: "Отчёты", icon: ChartNoAxesCombined },
  { to: "/admin", label: "Администрирование", icon: Settings },
];

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="app-shell">
      <header className="topbar">
        <button
          className="icon-button menu-button"
          type="button"
          aria-label={menuOpen ? "Закрыть меню" : "Открыть меню"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((value) => !value)}
        >
          {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
        </button>
        <div className="brand-mark" aria-hidden="true">
          <PackageOpen />
        </div>
        <div className="brand-copy">
          <span className="brand-title">Складской учёт</span>
          <span className="brand-subtitle">InventoryAccountment</span>
        </div>
        <div className="environment-badge">Локальная среда</div>
      </header>

      <aside className={`sidebar${menuOpen ? " sidebar--open" : ""}`}>
        <nav aria-label="Основная навигация">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-item${isActive ? " nav-item--active" : ""}`}
              onClick={() => setMenuOpen(false)}
            >
              <Icon size={19} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {menuOpen && (
        <button
          className="sidebar-scrim"
          type="button"
          aria-label="Закрыть меню"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <main className="main-content" id="main-content">
        <Outlet />
      </main>
    </div>
  );
}
