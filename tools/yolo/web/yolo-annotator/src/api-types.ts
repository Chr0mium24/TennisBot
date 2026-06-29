export type LabelStatus = "unlabeled" | "empty" | "ball";

export interface ImageEntry {
  path: string;
  video: string;
  camera: string;
  frame: number | null;
  label_exists: boolean;
  label_status: LabelStatus;
  excluded: boolean;
}

export interface CameraSummary {
  total: number;
  labeled: number;
  unlabeled: number;
  empty: number;
  ball: number;
  excluded: number;
  first_image: string;
}

export interface VideoSummary {
  id: string;
  total: number;
  labeled: number;
  unlabeled: number;
  empty: number;
  ball: number;
  excluded: number;
  cameras: Record<string, CameraSummary>;
}

export interface LabelPayload {
  text: string;
}

export interface ExcludedPayload {
  excluded: boolean;
}

export interface LabelSaveResponse {
  ok: boolean;
  path: string;
  bytes: number;
  created: boolean;
  previous_status: LabelStatus;
  label_status: LabelStatus;
}

export interface ExcludedSaveResponse {
  ok: boolean;
  path: string;
  previous_excluded: boolean;
  excluded: boolean;
}
