export type UserRole =
  | "super_admin"
  | "admin"
  | "store_manager"
  | "staff"
  | "order_taker"
  | "kitchen"
  | "analyst";

export type AuthUser = {
  id: number;
  business_group_id: number;
  company_id: number | null;
  name: string;
  email: string;
  role: UserRole;
  branch_id: number | null;
  permissions: string[];
  is_active: boolean;
};

export type LoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUser;
};

export type ApiErrorResponse = {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: unknown;
};

export type RouteKey =
  | "overview"
  | "products"
  | "customers"
  | "pos"
  | "sales"
  | "inventory"
  | "low-stock"
  | "purchase-orders"
  | "suppliers"
  | "categories"
  | "branches"
  | "forecasting"
  | "ai-assistant"
  | "power-bi"
  | "settings";

export type PageAction = {
  label: string;
  tone: "primary" | "secondary";
};

export type PageMetric = {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "blue" | "amber" | "rose" | "slate";
};

export type TableColumn = {
  key: string;
  label: string;
};

export type TableRow = Record<string, string>;

export type Category = {
  id: number;
  name: string;
  description: string | null;
};

export type Supplier = {
  id: number;
  name: string;
  contact_person: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  payment_terms: string | null;
  lead_time_days: number;
  is_active: boolean;
};

export type Branch = {
  id: number;
  name: string;
  address: string | null;
  city: string | null;
  manager_name: string | null;
  is_active: boolean;
};

export type ProductItemType = "goods" | "service";

export type Product = {
  id: number;
  sku: string;
  name: string;
  description: string | null;
  category_id: number;
  category_name: string;
  supplier_id: number;
  supplier_name: string;
  gst_rate_id: number | null;
  gst_rate_name: string | null;
  gst_rate_percent: string | null;
  unit_cost: string;
  selling_price: string;
  hsn_sac_code: string | null;
  cess_rate_percent: string;
  primary_barcode: string | null;
  unit_of_measure: string;
  mrp: string | null;
  brand: string | null;
  manufacturer: string | null;
  item_type: ProductItemType;
  batch_tracking_enabled: boolean;
  serial_tracking_enabled: boolean;
  expiry_tracking_enabled: boolean;
  reorder_threshold: string;
  target_stock_level: string;
  total_quantity_on_hand: string;
  stock_status: string;
  is_active: boolean;
};

export type ProductFormPayload = {
  sku: string;
  name: string;
  description: string | null;
  category_id: number;
  supplier_id: number;
  gst_rate_id: number | null;
  unit_cost: number;
  selling_price: number;
  hsn_sac_code: string | null;
  cess_rate_percent: number;
  primary_barcode: string | null;
  unit_of_measure: string;
  mrp: number | null;
  brand: string | null;
  manufacturer: string | null;
  item_type: ProductItemType;
  batch_tracking_enabled: boolean;
  serial_tracking_enabled: boolean;
  expiry_tracking_enabled: boolean;
  reorder_threshold: number;
  target_stock_level: number;
  is_active: boolean;
};

export type InventoryItem = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  category_id: number;
  category_name: string;
  supplier_id: number;
  supplier_name: string;
  branch_id: number;
  branch_name: string;
  quantity_on_hand: string;
  quantity_reserved: string;
  quantity_on_order: string;
  reorder_threshold: string;
  target_stock_level: string;
  unit_cost: string;
  selling_price: string;
  is_low_stock: boolean;
  last_updated_at: string;
};

export type StockMovement = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  branch_id: number;
  branch_name: string;
  movement_type: string;
  quantity_change: string;
  reason: string | null;
  reference_type: string | null;
  reference_id: number | null;
  created_by: number | null;
  created_by_name: string | null;
  created_at: string;
};

export type SaleItemRead = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  quantity: string;
  unit_price: string;
  discount_amount: string;
  line_total: string;
};

export type Sale = {
  id: number;
  sale_number: string;
  branch_id: number;
  branch_name: string;
  sale_datetime: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total_amount: string;
  created_by: number;
  created_by_name: string;
  created_at: string;
  items: SaleItemRead[];
};

export type SaleSummary = {
  revenue: string;
  gross_profit: string;
  gross_margin_percent: string;
  transaction_count: number;
  units_sold: string;
  average_order_value: string;
};

export type DashboardOverview = {
  sales: SaleSummary;
  stock_value: string;
  low_stock_count: number;
  pending_purchase_order_count: number;
  pending_purchase_order_value: string;
  slow_moving_count: number;
};

export type DashboardSalesPoint = {
  date: string;
  revenue: string;
  gross_profit: string;
  units_sold: string;
};

export type DashboardInventoryPoint = {
  product_id: number;
  sku: string;
  name: string;
  quantity_on_hand: string;
  reorder_threshold: string;
  target_stock_level: string;
  stock_value: string;
  is_low_stock: boolean;
};

export type PurchaseOrderStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "ordered"
  | "partially_received"
  | "received"
  | "cancelled";

export type PurchaseOrderItem = {
  id: number;
  product_id: number;
  product_sku: string;
  product_name: string;
  quantity_ordered: string;
  quantity_received: string;
  unit_cost: string;
  line_total: string;
};

export type PurchaseOrder = {
  id: number;
  po_number: string;
  supplier_id: number;
  supplier_name: string;
  branch_id: number;
  branch_name: string;
  status: PurchaseOrderStatus;
  order_date: string;
  expected_delivery_date: string | null;
  total_amount: string;
  created_by: number;
  created_by_name: string;
  approved_by: number | null;
  approved_by_name: string | null;
  approved_at: string | null;
  items: PurchaseOrderItem[];
};

export type ForecastType = "revenue" | "units" | "demand";

export type Forecast = {
  id: number;
  product_id: number | null;
  product_sku: string | null;
  product_name: string | null;
  category_id: number | null;
  category_name: string | null;
  branch_id: number | null;
  branch_name: string | null;
  forecast_type: ForecastType;
  forecast_start_date: string;
  forecast_end_date: string;
  forecast_value: string;
  confidence_low: string | null;
  confidence_high: string | null;
  model_name: string;
  created_at: string;
};

export type ForecastPoint = {
  date: string;
  value: string;
};

export type ForecastRunResponse = {
  forecast: Forecast;
  message: string;
  historical_points: ForecastPoint[];
  forecast_points: ForecastPoint[];
};

export type ReorderRecommendation = {
  product_id: number;
  product_sku: string;
  product_name: string;
  supplier_id: number;
  supplier_name: string;
  branch_id: number;
  branch_name: string;
  current_quantity: string;
  reorder_threshold: string;
  target_stock_level: string;
  supplier_lead_time_days: number;
  average_daily_sales: string;
  expected_demand_during_lead_time: string;
  suggested_reorder_quantity: string;
  priority: "critical" | "high" | "normal" | "healthy";
};

export type Customer = {
  id: number;
  branch_id: number | null;
  name: string;
  phone: string | null;
  email: string | null;
  gstin: string | null;
  billing_address: string | null;
  shipping_address: string | null;
  city: string | null;
  state: string | null;
  state_code: string | null;
  pincode: string | null;
  credit_limit: string;
  opening_balance: string;
  is_active: boolean;
  outstanding_balance: string;
  available_credit: string;
};

export type TaxMode = "gst" | "non_gst";

export type Company = {
  id: number;
  code: string;
  name: string;
  legal_name: string;
  trade_name: string | null;
  pan: string | null;
  default_currency: string;
  is_active: boolean;
};

export type BusinessProfile = {
  id: number;
  company_id: number;
  legal_name: string;
  trade_name: string | null;
  pan: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  state_code: string | null;
  pincode: string | null;
  default_tax_mode: TaxMode;
  default_currency: string;
  terms_and_conditions: string | null;
};
