export type PlaceReviewStatus = 'pending_review' | 'confirmed' | 'rejected'

export interface Place {
  id: string
  naver_place_id: string | null
  review_status: PlaceReviewStatus
  confirmed_name: string | null
  confirmed_category: string | null
  confirmed_address: string | null
  confirmed_lat: number | null
  confirmed_lng: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ImportJob {
  id: string
  job_type: string
  status: 'pending' | 'processing' | 'done' | 'failed'
  source_url: string | null
  source_file_name: string | null
  total_rows: number | null
  processed_rows: number | null
  failed_rows: number | null
  retry_count: number
  error_detail: string | null
  created_at: string
  updated_at: string
}
