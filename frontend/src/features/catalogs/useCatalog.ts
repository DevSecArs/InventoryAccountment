import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  archiveCatalog,
  createCatalog,
  listCatalog,
  type CatalogRecord,
  type CatalogResource,
  updateCatalog,
} from "../../api/catalogs";

const PAGE_SIZE = 20;

export function useCatalog<T extends CatalogRecord, TInput>(resource: CatalogResource) {
  const queryClient = useQueryClient();
  const [skip, setSkip] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchivedState] = useState(false);

  const queryKey = [resource, { skip, search, includeArchived }];
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => listCatalog<T>(resource, { skip, limit: PAGE_SIZE, search, includeArchived }, signal),
  });

  const saveMutation = useMutation({
    mutationFn: ({ id, input }: { id?: string; input: TInput }) =>
      id ? updateCatalog<T, TInput>(resource, id, input) : createCatalog<T, TInput>(resource, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [resource] }),
  });

  const archiveMutation = useMutation({
    mutationFn: (id: string) => archiveCatalog(resource, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [resource] }),
  });

  const applySearch = () => {
    setSkip(0);
    setSearch(searchInput.trim());
  };

  const setIncludeArchived = (value: boolean) => {
    setSkip(0);
    setIncludeArchivedState(value);
  };

  return {
    query,
    saveMutation,
    archiveMutation,
    skip,
    limit: PAGE_SIZE,
    searchInput,
    includeArchived,
    setSearchInput,
    applySearch,
    setIncludeArchived,
    previous: () => setSkip((value) => Math.max(0, value - PAGE_SIZE)),
    next: () => setSkip((value) => value + PAGE_SIZE),
  };
}
