"use client";

import { ThemeProvider } from "@mui/material/styles";
import { LicenseInfo } from "@mui/x-license";
import {
  DataGridPro,
  GridLogicOperator,
  type GridColDef,
  type GridFilterModel,
  type GridPaginationModel,
  type GridRowSelectionModel,
} from "@mui/x-data-grid-pro";
import { useEffect } from "react";

import { formatTs } from "@/lib/format";
import { muiDarkTheme, muiLightTheme } from "@/lib/muiTheme";
import { useDarkMode } from "@/lib/useDarkMode";
import {
  STATUSES,
  type MessageFilterItem,
  type MessageFilterModel,
  type MessageSortKey,
  type MessageSummary,
} from "@/lib/types";
import { STATUS_META } from "@/components/status";
import { cx } from "@/lib/format";

let licensed = false;
/** Once per page load — `DataGridPro` reads the key off a module-level singleton, not a prop. */
function ensureLicense() {
  if (licensed) return;
  const key = process.env.NEXT_PUBLIC_MUI_LICENSE_KEY;
  if (key) LicenseInfo.setLicenseKey(key);
  licensed = true;
}

/**
 * Filterable (via the grid's own header menu — `is`/`not`/`isAnyOf`, same as
 * every other column) but not sortable: `status` isn't in `MESSAGE_SORT_KEYS`,
 * the API's sort allowlist.
 */
const STATUS_COLUMN: GridColDef<MessageSummary> = {
  field: "status",
  headerName: "Status",
  width: 130,
  sortable: false,
  type: "singleSelect",
  valueOptions: STATUSES.map((status) => ({
    value: status,
    label: STATUS_META[status].label,
  })),
  renderCell: (params) => {
    const meta = STATUS_META[params.row.status];
    return (
      <span className={cx("inline-flex items-center gap-1.5 text-sm font-medium", meta.text)}>
        <meta.Icon className="h-3.5 w-3.5 shrink-0" />
        {meta.label}
      </span>
    );
  },
};

/** Columns the grid can be sorted/filtered by — same set the API allowlists (`MESSAGE_SORT_KEYS`). */
const COLUMNS: GridColDef<MessageSummary>[] = [
  {
    field: "failedAt",
    headerName: "Date",
    width: 200,
    type: "dateTime",
    valueGetter: (_value, row) => (row.failedAt ? new Date(row.failedAt) : null),
    renderCell: (params) =>
      params.value instanceof Date ? formatTs(params.value.toISOString()) : "—",
  },
  STATUS_COLUMN,
  {
    field: "sourceTopic",
    headerName: "Topic",
    width: 180,
    valueGetter: (_value, row) => row.sourceTopic ?? "",
  },
  {
    field: "errorType",
    headerName: "Error type",
    width: 200,
    valueGetter: (_value, row) => row.error.type ?? "Unknown error",
  },
  {
    field: "errorMessage",
    headerName: "Error message",
    flex: 1,
    minWidth: 260,
    valueGetter: (_value, row) => row.error.message ?? "",
  },
  {
    field: "id",
    headerName: "ID",
    width: 240,
  },
  {
    field: "partition",
    headerName: "Partition",
    width: 110,
    type: "number",
    valueGetter: (_value, row) => row.partition,
  },
  {
    field: "offset",
    headerName: "Offset",
    width: 110,
    type: "number",
    valueGetter: (_value, row) => row.offset,
  },
];

/**
 * The message list as an MUI DataGrid Pro — sortable and filterable on every
 * column via the grid's own header menus, all of it server-side: `items` is
 * always just the current page, so pagination/sorting/filtering state lives
 * in the URL one level up (`Overview`) and every change round-trips through
 * the API rather than operating on rows already in the browser.
 *
 * Row selection backs the same bulk replay/discard actions the old checkbox
 * column did; a row click opens the detail slide-over instead of navigating.
 */
export function MessageDataGrid({
  items,
  total,
  isPending,
  page,
  pageSize,
  sortBy,
  sortDir,
  filterModel,
  selected,
  onSelectionChange,
  onPageChange,
  onPageSizeChange,
  onSortChange,
  onFilterChange,
  onOpen,
}: {
  items: MessageSummary[] | undefined;
  total: number;
  isPending?: boolean;
  page: number;
  pageSize: number;
  sortBy: MessageSortKey;
  sortDir: "asc" | "desc";
  filterModel: MessageFilterModel;
  selected: Set<string>;
  onSelectionChange: (ids: Set<string>) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onSortChange: (key: MessageSortKey, dir: "asc" | "desc") => void;
  onFilterChange: (model: MessageFilterModel) => void;
  onOpen: (message: MessageSummary) => void;
}) {
  useEffect(ensureLicense, []);
  const dark = useDarkMode();

  const paginationModel: GridPaginationModel = { page: page - 1, pageSize };
  const gridFilterModel: GridFilterModel = {
    items: filterModel.items.map((item, index) => ({
      id: index,
      field: item.field,
      operator: item.operator,
      value: item.value,
    })),
    logicOperator: filterModel.logicOperator === "or" ? GridLogicOperator.Or : GridLogicOperator.And,
  };

  return (
    <ThemeProvider theme={dark ? muiDarkTheme : muiLightTheme}>
      {/* A fixed height rather than `autoHeight`: autoHeight sizes the grid to
          however many rows the current page/filter happens to return, so the
          page below it would jump every time a filter changed the row count
          (or shrank to zero briefly while a new page loaded). A fixed height
          with the grid's own internal scroll keeps the rest of the page still. */}
      <div className="overflow-hidden rounded-lg border border-border/70" style={{ height: 640 }}>
        <DataGridPro
          rows={items ?? []}
          columns={COLUMNS}
          getRowId={(row) => row.id}
          loading={isPending}
          density="compact"
          localeText={{ noRowsLabel: "No messages match this filter" }}
          disableRowSelectionOnClick
          checkboxSelection
          rowSelectionModel={{ type: "include", ids: new Set(selected) }}
          onRowSelectionModelChange={(model: GridRowSelectionModel) => {
            if (model.type === "include") {
              onSelectionChange(new Set([...model.ids].map(String)));
              return;
            }
            // "exclude" comes from the header select-all checkbox — selection
            // here only ever means "every row on the current page", so
            // resolve it against the loaded rows.
            const next = new Set((items ?? []).map((m) => m.id));
            for (const id of model.ids) next.delete(String(id));
            onSelectionChange(next);
          }}
          onRowClick={(params) => onOpen(params.row as MessageSummary)}
          pagination
          paginationMode="server"
          paginationModel={paginationModel}
          onPaginationModelChange={(model) => {
            if (model.pageSize !== pageSize) onPageSizeChange(model.pageSize);
            else if (model.page !== page - 1) onPageChange(model.page + 1);
          }}
          pageSizeOptions={[25, 50, 100, 200]}
          rowCount={total}
          sortingMode="server"
          sortModel={[{ field: sortBy, sort: sortDir }]}
          onSortModelChange={(model) => {
            const next = model[0];
            if (next?.sort) onSortChange(next.field as MessageSortKey, next.sort);
          }}
          filterMode="server"
          filterModel={gridFilterModel}
          onFilterModelChange={(model) => {
            onFilterChange({
              items: model.items
                .filter((item): item is typeof item & { operator: MessageFilterItem["operator"] } =>
                  Boolean(item.field && item.operator),
                )
                .map((item) => ({
                  field: item.field as MessageFilterItem["field"],
                  operator: item.operator,
                  value: item.value,
                })),
              logicOperator: model.logicOperator === "or" ? "or" : "and",
            });
          }}
          sx={{
            border: "none",
            fontFamily: "var(--font-sans)",
            "--DataGrid-containerBackground": "transparent",
            "& .MuiDataGrid-row": { cursor: "pointer" },
          }}
        />
      </div>
    </ThemeProvider>
  );
}
