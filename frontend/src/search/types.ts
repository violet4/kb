// Mirrors api/record_hit.py's RecordHit: any record as a list row.
export interface RecordHit {
  type: string;
  id: number;
  label: string;
  drilldown: boolean;
  context_ids: number[]; // contexts this hit lives in (several for a tag-addressed row)
  // How a drop on a context moves it: 'parent' re-parents a Context; null means it has no context.
  placement: 'parent' | 'context' | 'context_or_tag' | null;
  original_url: string | null;
  archivebox_url: string | null;
}

// Mirrors api/search_router.py's SearchHit and SearchInfo.
export interface SearchHit extends RecordHit {
  dist: number;
  is_substring: boolean;
}

export interface SearchInfo {
  default_limit: number;
  max_dist: number;
  substring_models: string[];
  substring_fields: string[];
  semantic_models: string[];
}
