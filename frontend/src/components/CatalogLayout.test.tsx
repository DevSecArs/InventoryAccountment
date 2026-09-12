import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Unit } from "../api/catalogs";
import { CatalogLayout } from "./CatalogLayout";

const unit: Unit = {
  id: "unit-1",
  code: "KG",
  name: "Килограмм",
  archived_at: null,
  created_at: "2026-09-12T10:00:00Z",
  updated_at: "2026-09-12T10:00:00Z",
};

describe("CatalogLayout", () => {
  it("показывает данные и запускает создание", async () => {
    const onCreate = vi.fn();
    render(
      <CatalogLayout
        title="Единицы измерения"
        description="Описание"
        createLabel="Добавить единицу"
        columns={[{ label: "Код", render: (item) => item.code }]}
        items={[unit]}
        total={1}
        skip={0}
        limit={20}
        searchInput=""
        includeArchived={false}
        loading={false}
        error={null}
        onSearchInput={vi.fn()}
        onSearch={vi.fn()}
        onIncludeArchived={vi.fn()}
        onCreate={onCreate}
        onEdit={vi.fn()}
        onArchive={vi.fn()}
        onPrevious={vi.fn()}
        onNext={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("KG")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Добавить единицу" }));
    expect(onCreate).toHaveBeenCalledOnce();
  });
});
