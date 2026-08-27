// Mirrors api/search_router.py's SearchHit.
export interface SearchHit {
  type: string;
  id: number;
  label: string;
  dist: number;
  is_substring: boolean;
  drilldown: boolean;
  original_url: string | null;
  archivebox_url: string | null;
}
