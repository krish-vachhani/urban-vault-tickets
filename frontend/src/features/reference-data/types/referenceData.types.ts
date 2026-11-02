import type { IdName } from "../../../shared/types/api.types";

export type Client = IdName;
export type Floor = IdName;
export type Department = IdName;

export type ClientOffice = {
  id: number;
  name: string;
  code: string;
  property: IdName;
  floor_count: number;
};

export type Issue = {
  id: number;
  name: string;
  department: IdName;
};

export type QuickIssue = {
  id: number;
  name: string;
  department_id: number;
  occurrences: number;
  last_reported_at: string;
};
