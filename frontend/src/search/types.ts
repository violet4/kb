// Mirrors api/search_router.py's SearchHit and SearchInfo.
export interface SearchHit {
  type: string;
  id: number;
  label: string;
  dist: number;
  is_substring: boolean;
  drilldown: boolean;
  context_ids: number[]; // contexts this hit lives in (several for a tag-addressed row)
  // How a drop on a context moves it: 'parent' re-parents a Context; null means it has no context.
  placement: 'parent' | 'context' | 'context_or_tag' | null;
  original_url: string | null;
  archivebox_url: string | null;
}

export interface SearchInfo {
  default_limit: number;
  max_dist: number;
  substring_models: string[];
  substring_fields: string[];
  semantic_models: string[];
}
