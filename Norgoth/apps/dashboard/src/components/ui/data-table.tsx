"use client";

import { Fragment, useState, type ReactNode } from "react";
import {
  CButton,
  CFormInput,
  CPagination,
  CPaginationItem,
  CTable,
  CTableBody,
  CTableDataCell,
  CTableHead,
  CTableHeaderCell,
  CTableRow,
} from "@coreui/react";
import { CIcon } from "@coreui/icons-react";
import { cilChevronBottom, cilChevronRight } from "@coreui/icons";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  className?: string;
  cell: (row: T) => ReactNode;
};

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyMessage?: string;
  search?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  toolbar?: ReactNode;
  /**
   * When provided, each row becomes expandable and this renders the detail
   * area (structured metadata / Advanced section) below the row.
   */
  expandable?: (row: T) => ReactNode;
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  emptyMessage = "No rows.",
  search,
  onSearchChange,
  searchPlaceholder = "Search…",
  page = 1,
  pageSize = 10,
  onPageChange,
  toolbar,
  expandable,
}: DataTableProps<T>) {
  const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * pageSize;
  const pageRows = rows.slice(start, start + pageSize);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const totalColumns = columns.length + (expandable ? 1 : 0);

  function toggleRow(key: string) {
    setExpanded((current) => ({ ...current, [key]: !current[key] }));
  }

  return (
    <div className="d-flex flex-column gap-3">
      {(onSearchChange || toolbar) && (
        <div className="d-flex flex-wrap align-items-center gap-3">
          {onSearchChange ? (
            <CFormInput
              value={search ?? ""}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder={searchPlaceholder}
              className="flex-grow-1"
              style={{ minWidth: 200 }}
            />
          ) : null}
          {toolbar}
        </div>
      )}

      <div className="norgoth-data-table">
        <CTable hover responsive align="middle" className="mb-0">
          <CTableHead>
            <CTableRow>
              {expandable ? (
                <CTableHeaderCell scope="col" style={{ width: 36 }} aria-label="Expand" />
              ) : null}
              {columns.map((column) => (
                <CTableHeaderCell
                  key={column.key}
                  scope="col"
                  className={column.className}
                >
                  {column.header}
                </CTableHeaderCell>
              ))}
            </CTableRow>
          </CTableHead>
          <CTableBody>
            {pageRows.length === 0 ? (
              <CTableRow>
                <CTableDataCell
                  colSpan={totalColumns}
                  className="text-center text-body-secondary py-4"
                >
                  {emptyMessage}
                </CTableDataCell>
              </CTableRow>
            ) : (
              pageRows.map((row) => {
                const key = rowKey(row);
                const isOpen = !!expanded[key];
                return (
                  <Fragment key={key}>
                    <CTableRow
                      onClick={expandable ? () => toggleRow(key) : undefined}
                      style={expandable ? { cursor: "pointer" } : undefined}
                    >
                      {expandable ? (
                        <CTableDataCell className="text-center text-body-secondary">
                          <CIcon
                            icon={isOpen ? cilChevronBottom : cilChevronRight}
                            height={14}
                          />
                        </CTableDataCell>
                      ) : null}
                      {columns.map((column) => (
                        <CTableDataCell key={column.key} className={column.className}>
                          {column.cell(row)}
                        </CTableDataCell>
                      ))}
                    </CTableRow>
                    {expandable && isOpen ? (
                      <CTableRow>
                        <CTableDataCell
                          colSpan={totalColumns}
                          className="norgoth-data-table-detail"
                        >
                          {expandable(row)}
                        </CTableDataCell>
                      </CTableRow>
                    ) : null}
                  </Fragment>
                );
              })
            )}
          </CTableBody>
        </CTable>
      </div>

      {onPageChange && rows.length > pageSize ? (
        <div className="d-flex align-items-center justify-content-between gap-3 flex-wrap norgoth-pagination-bar">
          <span className="small text-body-secondary">
            {rows.length === 0
              ? "0"
              : `${start + 1}–${Math.min(start + pageSize, rows.length)}`}{" "}
            of {rows.length}
          </span>
          <div className="d-flex align-items-center gap-2">
            <CButton
              color="secondary"
              variant="outline"
              size="sm"
              className="norgoth-pagination-btn"
              disabled={safePage <= 1}
              onClick={() => onPageChange(safePage - 1)}
            >
              Previous
            </CButton>
            <CPagination className="mb-0 norgoth-pagination" aria-label="Table pagination">
              <CPaginationItem active>
                {safePage} / {totalPages}
              </CPaginationItem>
            </CPagination>
            <CButton
              color="secondary"
              variant="outline"
              size="sm"
              className="norgoth-pagination-btn"
              disabled={safePage >= totalPages}
              onClick={() => onPageChange(safePage + 1)}
            >
              Next
            </CButton>
          </div>
        </div>
      ) : null}
    </div>
  );
}
