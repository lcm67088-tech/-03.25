export type OrderStatus =
  | 'draft'
  | 'pending_review'
  | 'confirmed'
  | 'closed'
  | 'cancelled'

export type OrderItemStatus =
  | 'received'
  | 'on_hold'
  | 'reviewing'
  | 'ready_to_route'
  | 'assigned'
  | 'in_progress'
  | 'done'
  | 'confirmed'
  | 'settlement_ready'
  | 'closed'
  | 'cancelled'

export interface Order {
  id: string
  status: OrderStatus
  source_type: string
  order_group_key: string | null
  agency_id: string | null
  agency_name_snapshot: string | null
  brand_id: string | null
  sales_rep_name: string | null
  estimator_name: string | null
  item_count?: number
  is_deleted: boolean
  created_at: string
  updated_at: string
  closed_at: string | null
}

export interface OrderItem {
  id: string
  order_id: string
  status: OrderItemStatus
  product_type_code: string | null
  product_subtype: string | null
  place_id: string | null
  place_name_snapshot: string | null
  place_url_snapshot: string | null
  naver_place_id_snapshot: string | null
  sellable_offering_id: string | null
  standard_product_type_id: string | null
  provider_id: string | null
  provider_offering_id: string | null
  main_keyword: string | null
  keywords_raw: string | null
  spec_data: Record<string, unknown> | null
  start_date: string | null
  end_date: string | null
  daily_qty: number | null
  total_qty: number | null
  working_days: number | null
  unit_price: number | null
  total_amount: number | null
  operator_note: string | null
  settlement_note: string | null
  confirmed_at: string | null
  settlement_ready_at: string | null
  closed_at: string | null
  routed_at: string | null
  is_deleted: boolean
  created_at: string
  updated_at: string
  available_transitions?: OrderItemStatus[]
}

export interface OrderItemStatusHistory {
  id: string
  order_item_id: string
  from_status: OrderItemStatus | null
  to_status: OrderItemStatus
  changed_by: string | null
  reason: string | null
  created_at: string
}

export interface StatusTransitionRequest {
  to_status: OrderItemStatus
  reason?: string
}

export interface SettlementNoteUpdate {
  settlement_note: string
}
