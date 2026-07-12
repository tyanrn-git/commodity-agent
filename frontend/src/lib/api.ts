import type { OpportunityCommercialRow } from "./opportunityCommercial";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type User = {
  id: string;
  email: string;
  timezone: string;
  is_active: boolean;
};

export type Product = {
  id: string;
  normalized_name: string;
  category: string;
  aliases: string[] | null;
  typical_units: string[] | null;
  completeness?: {
    total_parameters: number;
    filled_parameters: number;
    completeness_percent: number;
    identity_parameters: number;
    variant_parameters: number;
  };
};

export type ProductSpecProfile = {
  id: string;
  product_id: string;
  parameter_name: string;
  unit: string | null;
  minimum_value: string | null;
  maximum_value: string | null;
  is_mandatory: boolean;
  parameter_kind: string;
  variation_materiality: string;
  description: string | null;
  evidence_count: number;
};

export type ProductAssistantReply = {
  reply: string;
  spec_changes: Array<Record<string, unknown>>;
  applied_changes: string[];
  ai_model: string;
  ai_cost_usd: string;
};

export type ProductDetail = Product & {
  specification_profiles: ProductSpecProfile[];
  completeness: {
    total_parameters: number;
    filled_parameters: number;
    completeness_percent: number;
  };
  created_at: string;
  updated_at: string;
};

export type ProposedProduct = {
  normalized_name: string;
  category: string;
  aliases: string[];
  typical_units: string[];
  parameters: Array<{
    parameter_name: string;
    unit: string | null;
    is_mandatory: boolean;
    minimum_value: string | null;
    maximum_value: string | null;
  }>;
  reasoning: string | null;
};

export type OpportunityDisplayStatus = {
  code: string;
  label: string;
  kind: string;
  changed_at: string | null;
};

export type OpportunityStatusEvent = {
  id: string;
  opportunity_id: string;
  status_code: string;
  status_kind: string;
  changed_at: string;
  changed_by_id: string | null;
  actor_type: string;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type Opportunity = {
  id: string;
  type: string;
  title: string;
  status: string;
  raw_product_name: string | null;
  normalized_product_id: string | null;
  buyer_or_supplier_hint: string | null;
  quantity_min: string | null;
  quantity_max: string | null;
  quantity_unit: string | null;
  origin_hint: string | null;
  destination_hint: string | null;
  deadline: string | null;
  quote_deadline: string | null;
  delivery_deadline: string | null;
  status_changed_at: string | null;
  status_note: string | null;
  notes: string | null;
  source_url: string | null;
  created_at: string;
  updated_at: string;
};

export type OpportunityBoardDocument = {
  id: string;
  source_type: string;
  label: string;
  source_url: string | null;
};

export type OpportunityBoardItem = Opportunity & {
  type_label: string;
  normalized_product_name: string | null;
  commercial_summary: string;
  commercial_row: OpportunityCommercialRow;
  display_status: OpportunityDisplayStatus;
  description: string | null;
  origin_kind: string;
  origin_label: string;
  origin_explanation: string | null;
  deal_id: string | null;
  deal_number: string | null;
  economics_preview: string | null;
  monitoring_rule_name: string | null;
  monitoring_publication_id: string | null;
  sources_count: number;
  documents: OpportunityBoardDocument[];
  internet_source_name: string | null;
};

export type SkippedMonitoringItem = {
  id: string;
  monitoring_rule_id: string;
  monitoring_rule_name: string | null;
  title: string;
  product: string | null;
  destination: string | null;
  buyer: string | null;
  quantity: number | null;
  quantity_unit: string | null;
  first_seen_at: string;
  filter_explanation: string | null;
};

export type OpportunityBoard = {
  opportunities: OpportunityBoardItem[];
  skipped_monitoring: SkippedMonitoringItem[];
};

export type SupplierLeadContext = {
  id: string;
  opportunity_id: string;
  supply_offer_id: string | null;
  unit_price: string | null;
  currency: string | null;
  incoterm: string | null;
  origin: string | null;
  supplier_hint: string | null;
  created_at: string;
  updated_at: string;
};

export type SupplierLeadMatch = {
  id: string;
  supplier_opportunity_id: string;
  match_type: string;
  matched_opportunity_id: string | null;
  matched_deal_id: string | null;
  matched_requirement_id: string | null;
  score: string;
  match_summary: string;
  match_reasons: string[];
  route_proposal: Record<string, string | boolean> | null;
  market_comparison: Record<string, unknown> | null;
  outreach_subject: string | null;
  outreach_body: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type SupplierLeadDetail = {
  context: SupplierLeadContext | null;
  matches: SupplierLeadMatch[];
  market_comparison: Record<string, unknown> | null;
};

export type Source = {
  id: string;
  opportunity_id: string | null;
  source_type: string;
  source_url: string | null;
  original_filename: string | null;
  mime_type: string | null;
  storage_key: string;
  file_size_bytes: number | null;
  is_immutable: boolean;
  created_at: string;
};

export type Deal = {
  id: string;
  deal_number: string;
  title: string;
  origin_opportunity_id: string;
  direction: string;
  base_currency: string;
  stage: string;
  outcome: string;
  deadline: string | null;
  created_at: string;
  updated_at: string;
};

export type Evidence = {
  id: string;
  requirement_id: string;
  source_id: string | null;
  field_path: string;
  excerpt: string | null;
  page_number: number | null;
  user_confirmed: boolean;
  created_at: string;
};

export type Requirement = {
  id: string;
  deal_id: string;
  product_id: string | null;
  quantity_min: string | null;
  quantity_max: string | null;
  quantity_unit: string | null;
  destination: string | null;
  requested_incoterm: string | null;
  packaging: string | null;
  commercial_deadline: string | null;
  user_confirmed: boolean;
  evidence_items: Evidence[];
  created_at: string;
  updated_at: string;
};

export type AIBudgetSettings = {
  id: string;
  monthly_budget_usd: string;
  first_warning_percent: number;
  second_warning_percent: number;
  hard_limit_enabled: boolean;
  allow_manual_override: boolean;
  budget_reset_day: number;
  preferred_default_model: string;
  fallback_model: string | null;
  ai_enabled: boolean;
};

export type AIUsageSummary = {
  monthly_budget_usd: string;
  spent_usd: string;
  remaining_usd: string;
  percent_used: number;
  forecast_usd: string;
  warning_level: string | null;
  ai_enabled: boolean;
  by_model: { model: string; cost_usd: string; count: number }[];
  by_operation: { operation: string; cost_usd: string; count: number }[];
};

export type ExtractionResult = {
  id: string;
  source_id: string;
  status: string;
  model: string | null;
  extracted_data: Record<string, unknown> | null;
  missing_fields: string[] | null;
  validation_errors: string[] | null;
};

export type ResearchCampaign = {
  id: string;
  name: string;
  product_ids: string[];
  target_buy_regions: string[] | null;
  target_sell_regions: string[] | null;
  quantity_range: Record<string, unknown> | null;
  preferred_incoterms: string[] | null;
  excluded_regions: string[] | null;
  research_hypothesis: string | null;
  status: string;
  viability_status: string;
  viability_report: Record<string, unknown> | null;
  created_opportunity_ids: string[] | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ResearchLead = {
  id: string;
  campaign_id: string;
  lead_type: string;
  title: string;
  organization_name: string | null;
  region: string | null;
  country: string | null;
  url: string | null;
  notes: string | null;
  relevance_score: string | null;
  source_type: string | null;
  lead_metadata: Record<string, unknown> | null;
};

export type OutreachDraft = {
  id: string;
  campaign_id: string;
  target_lead_id: string | null;
  outreach_type: string;
  subject: string;
  body: string;
  language: string;
  status: string;
  sent_at: string | null;
  created_at: string;
};

export type CommercialFact = {
  id: string;
  research_campaign_id: string | null;
  opportunity_id: string | null;
  source_id: string | null;
  entity_type: string;
  field_path: string;
  value: string;
  unit: string | null;
  currency: string | null;
  confirmation_level: string;
  evidence_excerpt: string | null;
  user_confirmed: boolean;
  created_at: string;
};

export type Contact = {
  id: string;
  counterparty_id: string;
  full_name: string | null;
  email: string | null;
  role_title: string | null;
  department: string | null;
  phone: string | null;
  verification_status: string;
  is_primary: boolean;
};

export type CounterpartyListItem = {
  id: string;
  legal_name: string;
  trade_name: string | null;
  organization_type: string;
  website: string | null;
  primary_domain: string | null;
  verification_status: string;
  compliance_review_status: string;
  contacts_count: number;
  capabilities_count: number;
  confirmed_capabilities_count: number;
};

export type Counterparty = CounterpartyListItem & {
  incorporation_country?: string | null;
  operating_countries?: string[] | null;
  registration_number?: string | null;
  tax_id?: string | null;
  address?: string | null;
  compliance_reviewed_at?: string | null;
  risk_flags?: string[] | null;
  domain_verification_report?: Record<string, unknown> | null;
  contacts: Contact[];
};

export type DealParty = {
  id: string;
  deal_id: string;
  counterparty_id: string;
  role: string;
  disclosure_status: string;
  verification_status: string;
  counterparty?: Counterparty;
};

export type RFQTemplate = {
  id: string;
  name: string;
  rfq_type: string;
  language: string;
  default_requested_fields: string[];
};

export type RFQ = {
  id: string;
  deal_id: string;
  target_deal_party_id: string;
  contact_id: string | null;
  rfq_type: string;
  requested_fields: string[];
  language: string;
  subject: string;
  body: string;
  status: string;
};

export type CompanySettings = {
  id: string;
  legal_name: string | null;
  trade_name: string | null;
  brand_name: string | null;
  default_rfq_language: string;
  email_signature_text: string | null;
};

export type InboxMessage = {
  id: string;
  thread_id: string;
  rfq_id: string | null;
  direction: string;
  link_status: string;
  subject: string;
  body_text: string;
  from_address: string | null;
  sent_at: string;
};

export type SupplyOffer = {
  id: string;
  deal_id: string;
  rfq_id: string | null;
  product_name: string | null;
  available_quantity: string | null;
  quantity_unit: string | null;
  price: string | null;
  currency: string | null;
  incoterm: string | null;
  origin: string | null;
  payment_terms: Record<string, unknown> | null;
  missing_fields: string[] | null;
  status: string;
  user_confirmed: boolean;
};

export type FulfilmentConfiguration = {
  id: string;
  deal_id: string;
  name: string;
  target_quantity: string | null;
  target_quantity_unit: string | null;
  destination: string | null;
  status: string;
  is_stale: boolean;
  stale_since: string | null;
  stale_reason: string | null;
  sales_price_per_unit: string | null;
  sales_currency: string | null;
  revenue: string | null;
  total_cost: string | null;
  gross_margin: string | null;
  gross_margin_percent: string | null;
  cost_breakdown: Record<string, string> | null;
  fx_rates_used: Record<string, string> | null;
  spec_match_summary: Record<string, unknown> | null;
  completeness_score: string | null;
  last_calculated_at: string | null;
  shipment_lots: Record<string, unknown>[];
  transport_legs: Record<string, unknown>[];
  service_quotes: Record<string, unknown>[];
  economics_snapshots: { id: string; scenario: string; snapshot_data: Record<string, unknown> }[];
  created_at: string;
  updated_at: string;
};

export type Offer = {
  id: string;
  deal_id: string;
  configuration_id: string;
  target_deal_party_id: string;
  subject: string;
  body: string;
  status: string;
  configuration_snapshot: Record<string, unknown>;
  economics_snapshot: Record<string, unknown>;
  disclosure_snapshot: Record<string, unknown> | null;
  validity_until: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MonitoringRule = {
  id: string;
  name: string;
  connector_type: string;
  source_url: string;
  poll_interval_hours: number;
  is_active: boolean;
  filters: Record<string, unknown>;
  access_mode: string;
  connector_config: Record<string, unknown>;
  health_status: string;
  health_message: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
};

export type MonitoringRun = {
  id: string;
  monitoring_rule_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  items_found: number;
  items_new: number;
  opportunities_created: number;
  error_message: string | null;
  health_status: string;
  created_at: string;
  updated_at: string;
};

export type MonitoredPublication = {
  id: string;
  monitoring_rule_id: string;
  source_item_id: string;
  canonical_url: string | null;
  title: string;
  publication_date: string | null;
  first_seen_at: string;
  last_seen_at: string;
  content_hash: string;
  status: string;
  extracted_fields: Record<string, unknown> | null;
  opportunity_id: string | null;
  created_at: string;
  updated_at: string;
};

export type InternetSource = {
  id: string;
  owner_id: string | null;
  name: string;
  base_url: string;
  source_kind: string;
  access_mode: string;
  fetch_strategy: string;
  fetch_config: Record<string, unknown>;
  regions: string[];
  product_tags: string[];
  languages: string[];
  description: string | null;
  search_hints: string | null;
  is_active: boolean;
  is_test: boolean;
  priority: number;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
  is_system: boolean;
};

export type InternetSourceMatch = {
  sources: InternetSource[];
  matched_count: number;
  product_keywords: string[];
  regions: string[];
  sources_discovered?: number;
  discovery_notes?: string | null;
};

export type InternetSourceSearchRun = {
  id: string;
  owner_id: string;
  product_keywords: string[];
  regions: string[];
  search_date: string;
  access_mode: string | null;
  status: string;
  sources_matched: number;
  sources_scanned: number;
  hits_found: number;
  hits_new: number;
  opportunities_created: number;
  ai_calls: number;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
  sources_discovered?: number;
};

export type TenderMonitoringRow = {
  buyer_name: string | null;
  product_name: string | null;
  volume: string | null;
  destination: string | null;
  submission_deadline: string | null;
  delivery_deadline: string | null;
  submission_expired: boolean;
  product_match: boolean;
  product_match_reason: string | null;
  display_status: string;
  display_status_label: string;
  source_url: string | null;
  feasibility?: Record<string, unknown> | null;
  opportunity_id?: string | null;
};

export type InternetSourceSearchHit = {
  id: string;
  search_run_id: string;
  internet_source_id: string;
  title: string;
  canonical_url: string | null;
  publication_date: string | null;
  content_hash: string;
  status: string;
  confidence: number | null;
  evidence_excerpt: string | null;
  fetch_status: string | null;
  extracted_fields: Record<string, unknown> | null;
  opportunity_id: string | null;
  created_at: string;
  updated_at: string;
  source_name: string | null;
  monitoring_row: TenderMonitoringRow | null;
};

export type AutomationSettings = {
  id: string;
  user_id: string;
  auto_follow_up_enabled: boolean;
  follow_up_after_days: number;
  max_follow_ups_per_rfq: number;
  min_days_between_follow_ups: number;
  max_auto_actions_per_day: number;
  created_at: string;
  updated_at: string;
};

export type AutomationRun = {
  id: string;
  owner_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  actions_evaluated: number;
  actions_sent: number;
  actions_blocked: number;
  actions_skipped: number;
  actions_rate_limited: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type AutomatedActionLog = {
  id: string;
  owner_id: string;
  automation_run_id: string;
  action_type: string;
  action_category: string;
  binding_class: string;
  entity_type: string;
  entity_id: string;
  status: string;
  reason: string | null;
  message_id: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type OpportunitySpecValue = {
  id: string;
  opportunity_id: string;
  parameter_name: string;
  unit: string | null;
  value_text: string | null;
  value_min: string | null;
  value_max: string | null;
  status: string;
  source_id: string | null;
  evidence_excerpt: string | null;
  user_confirmed: boolean;
  is_mandatory: boolean;
  created_at: string;
  updated_at: string;
};

export type ProductResolution = {
  opportunity_id: string;
  normalized_product_id: string | null;
  normalized_product_name: string | null;
  rough_product_name: string;
  matched: boolean;
  product_created: boolean;
  proposed_new_product: ProposedProduct | null;
  catalog_products: string[];
  confidence: number;
  reasoning: string | null;
  missing_mandatory: string[];
  spec_values: OpportunitySpecValue[];
  ai_model: string;
  ai_cost_usd: string;
};

export type CounterpartyCapability = {
  id: string;
  counterparty_id: string;
  capability_type: string;
  product_id: string | null;
  title: string;
  rough_product_name: string | null;
  regions: string[] | null;
  routes: string[] | null;
  incoterms: string[] | null;
  notes: string | null;
  confirmation_level: string;
  evidence_excerpt: string | null;
  user_confirmed: boolean;
  extracted_by_ai: boolean;
  created_at: string;
  updated_at: string;
};

export type ContactHint = {
  full_name: string | null;
  role_title: string | null;
  email: string | null;
  department: string | null;
  evidence_excerpt: string | null;
};

export type CounterpartyEnrichment = {
  summary: string | null;
  capabilities: CounterpartyCapability[];
  contact_hints: ContactHint[];
  missing_fields: string[];
  ai_model: string;
  ai_cost_usd: string;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text || response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function openSourceContent(sourceId: string, sourceUrl?: string | null) {
  if (sourceUrl) {
    window.open(sourceUrl, "_blank", "noopener,noreferrer");
    return;
  }
  const response = await fetch(`${API_URL}/sources/${sourceId}/open`, {
    credentials: "include",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text || response.statusText);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  window.open(objectUrl, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

export const apiClient = {
  login: (email: string, password: string) =>
    api<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => api<{ status: string }>("/auth/logout", { method: "POST" }),
  me: () => api<User>("/auth/me"),
  listProducts: () => api<Product[]>("/products"),
  listProductsCatalog: () => api<Product[]>("/products"),
  getProduct: (id: string) => api<ProductDetail>(`/products/${id}`),
  createProduct: (data: Record<string, unknown>) =>
    api<ProductDetail>("/products", { method: "POST", body: JSON.stringify(data) }),
  productAssistant: (productId: string, data: Record<string, unknown>) =>
    api<ProductAssistantReply>(`/products/${productId}/assistant`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listOpportunities: () => api<Opportunity[]>("/opportunities"),
  getOpportunitiesBoard: () => api<OpportunityBoard>("/opportunities/board"),
  createOpportunity: (data: Record<string, unknown>) =>
    api<Opportunity>("/opportunities", { method: "POST", body: JSON.stringify(data) }),
  createSupplierLedOpportunity: (data: Record<string, unknown>) =>
    api<Opportunity>("/opportunities/supplier-led", { method: "POST", body: JSON.stringify(data) }),
  getSupplierLeadDetail: (id: string) => api<SupplierLeadDetail>(`/opportunities/${id}/supplier-lead`),
  matchBuyerNeeds: (id: string) =>
    api<SupplierLeadMatch[]>(`/opportunities/${id}/match-buyer-needs`, { method: "POST" }),
  buildSupplierLeadRoute: (matchId: string) =>
    api<SupplierLeadMatch>(`/supplier-lead-matches/${matchId}/build-route`, { method: "POST" }),
  draftSupplierLeadOutreach: (matchId: string) =>
    api<SupplierLeadMatch>(`/supplier-lead-matches/${matchId}/draft-outreach`, { method: "POST" }),
  getOpportunity: (id: string) => api<Opportunity>(`/opportunities/${id}`),
  changeOpportunityStatus: (id: string, data: { status: string; note?: string | null }) =>
    api<Opportunity>(`/opportunities/${id}/status`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getOpportunityStatusHistory: (id: string) =>
    api<OpportunityStatusEvent[]>(`/opportunities/${id}/status-history`),
  getOpportunityDisplayStatus: (id: string) =>
    api<OpportunityDisplayStatus>(`/opportunities/${id}/display-status`),
  uploadSource: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Source>(`/opportunities/${id}/sources`, { method: "POST", body: form });
  },
  listSources: (id: string) => api<Source[]>(`/opportunities/${id}/sources`),
  convertOpportunity: (id: string) =>
    api<Deal>(`/opportunities/${id}/convert`, { method: "POST" }),
  getDeal: (id: string) => api<Deal>(`/deals/${id}`),
  createRequirement: (dealId: string, data: Record<string, unknown>) =>
    api<Requirement>(`/deals/${dealId}/requirements`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listRequirements: (dealId: string) => api<Requirement[]>(`/deals/${dealId}/requirements`),
  getAIBudget: () => api<AIBudgetSettings>("/settings/ai-budget"),
  updateAIBudget: (data: Record<string, unknown>) =>
    api<AIBudgetSettings>("/settings/ai-budget", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  getAIUsage: () => api<AIUsageSummary>("/settings/ai-usage"),
  extractSource: (sourceId: string, force = false) =>
    api<ExtractionResult>(`/sources/${sourceId}/extract`, {
      method: "POST",
      body: JSON.stringify({ force }),
    }),
  getExtraction: (sourceId: string) =>
    api<ExtractionResult | null>(`/sources/${sourceId}/extraction`),
  applyExtraction: (opportunityId: string, extractionId: string, fields?: string[]) =>
    api<{ status: string }>(`/opportunities/${opportunityId}/apply-extraction`, {
      method: "POST",
      body: JSON.stringify({ extraction_id: extractionId, fields }),
    }),
  importEml: (opportunityId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Source>(`/opportunities/${opportunityId}/import-eml`, {
      method: "POST",
      body: form,
    });
  },
  importUrl: (opportunityId: string, url: string) =>
    api<Source>(`/opportunities/${opportunityId}/import-url`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  listResearchCampaigns: () => api<ResearchCampaign[]>("/research-campaigns"),
  createResearchCampaign: (data: Record<string, unknown>) =>
    api<ResearchCampaign>("/research-campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getResearchCampaign: (id: string) => api<ResearchCampaign>(`/research-campaigns/${id}`),
  runResearchCampaign: (id: string) =>
    api<ResearchCampaign>(`/research-campaigns/${id}/run`, { method: "POST" }),
  listResearchLeads: (id: string) => api<ResearchLead[]>(`/research-campaigns/${id}/leads`),
  generateOutreach: (id: string) =>
    api<OutreachDraft[]>(`/research-campaigns/${id}/outreach`, { method: "POST" }),
  listOutreach: (id: string) => api<OutreachDraft[]>(`/research-campaigns/${id}/outreach`),
  markOutreachSent: (draftId: string) =>
    api<OutreachDraft>(`/research-campaigns/outreach/${draftId}/mark-sent`, { method: "POST" }),
  importCampaignResponse: (id: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<{ source: Source; facts: CommercialFact[] }>(
      `/research-campaigns/${id}/import-response`,
      { method: "POST", body: form }
    );
  },
  listCampaignFacts: (id: string) => api<CommercialFact[]>(`/research-campaigns/${id}/facts`),
  getCampaignViability: (id: string) =>
    api<Record<string, unknown>>(`/research-campaigns/${id}/viability`),
  createOpportunityFromCampaign: (
    id: string,
    data: { lead_id?: string; opportunity_type?: string }
  ) =>
    api<Opportunity>(`/research-campaigns/${id}/create-opportunity`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listCounterparties: () => api<CounterpartyListItem[]>("/counterparties"),
  createCounterparty: (data: Record<string, unknown>) =>
    api<Counterparty>("/counterparties", { method: "POST", body: JSON.stringify(data) }),
  getCounterparty: (id: string) => api<Counterparty>(`/counterparties/${id}`),
  updateCounterparty: (id: string, data: Record<string, unknown>) =>
    api<Counterparty>(`/counterparties/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  createContact: (counterpartyId: string, data: Record<string, unknown>) =>
    api<Contact>(`/counterparties/${counterpartyId}/contacts`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  verifyCounterpartyDomain: (id: string) =>
    api<Record<string, unknown>>(`/counterparties/${id}/verify-domain`, { method: "POST" }),
  confirmCounterpartyDomain: (id: string) =>
    api<Counterparty>(`/counterparties/${id}/confirm-domain`, { method: "POST" }),
  markCounterpartyReviewed: (id: string) =>
    api<Counterparty>(`/counterparties/${id}/mark-reviewed`, { method: "POST" }),
  listDealParties: (dealId: string) => api<DealParty[]>(`/deals/${dealId}/parties`),
  addDealParty: (dealId: string, data: Record<string, unknown>) =>
    api<DealParty>(`/deals/${dealId}/parties`, { method: "POST", body: JSON.stringify(data) }),
  listRfqTemplates: () => api<RFQTemplate[]>("/rfq-templates"),
  listDealRfqs: (dealId: string) => api<RFQ[]>(`/deals/${dealId}/rfqs`),
  createRfq: (dealId: string, data: Record<string, unknown>) =>
    api<RFQ>(`/deals/${dealId}/rfqs`, { method: "POST", body: JSON.stringify(data) }),
  getRfq: (id: string) => api<RFQ>(`/rfqs/${id}`),
  updateRfq: (id: string, data: Record<string, unknown>) =>
    api<RFQ>(`/rfqs/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteRfq: (id: string) => api<void>(`/rfqs/${id}`, { method: "DELETE" }),
  draftRfqWithAi: (id: string) =>
    api<RFQ>(`/rfqs/${id}/draft-with-ai`, { method: "POST" }),
  getRfqApprovalPreview: (id: string) =>
    api<Record<string, unknown>>(`/rfqs/${id}/approval-preview`),
  submitRfqForApproval: (id: string) =>
    api<RFQ>(`/rfqs/${id}/submit-for-approval`, { method: "POST" }),
  approveRfq: (id: string, acknowledgeWarnings = false) =>
    api<RFQ>(`/rfqs/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ acknowledge_warnings: acknowledgeWarnings }),
    }),
  getCompanySettings: () => api<CompanySettings>("/settings/company"),
  sendRfq: (rfqId: string) =>
    api<{ rfq_id: string; status: string; message_id: string }>(`/rfqs/${rfqId}/send`, {
      method: "POST",
    }),
  listInbox: () => api<InboxMessage[]>("/inbox"),
  listUnlinkedInbox: () => api<InboxMessage[]>("/inbox/unlinked"),
  importInboxEml: (file: File, dealId?: string, rfqId?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (dealId) form.append("deal_id", dealId);
    if (rfqId) form.append("rfq_id", rfqId);
    return api<{ message: InboxMessage; supply_offer: SupplyOffer | null }>(
      "/inbox/import-eml",
      { method: "POST", body: form }
    );
  },
  linkMessage: (messageId: string, rfqId: string) =>
    api<{ message: InboxMessage; supply_offer: SupplyOffer }>(
      `/messages/${messageId}/link`,
      { method: "POST", body: JSON.stringify({ rfq_id: rfqId }) }
    ),
  listSupplyOffers: (dealId: string) => api<SupplyOffer[]>(`/deals/${dealId}/supply-offers`),
  confirmSupplyOffer: (offerId: string) =>
    api<SupplyOffer>(`/supply-offers/${offerId}/confirm`, { method: "POST" }),
  listConfigurations: (dealId: string) =>
    api<FulfilmentConfiguration[]>(`/deals/${dealId}/configurations`),
  createConfiguration: (dealId: string, data: Record<string, unknown>) =>
    api<FulfilmentConfiguration>(`/deals/${dealId}/configurations`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  recalculateConfiguration: (configId: string) =>
    api<FulfilmentConfiguration>(`/configurations/${configId}/recalculate`, { method: "POST" }),
  confirmConfiguration: (configId: string) =>
    api<FulfilmentConfiguration>(`/configurations/${configId}/confirm`, { method: "POST" }),
  addTransportLeg: (configId: string, data: Record<string, unknown>) =>
    api<Record<string, unknown>>(`/configurations/${configId}/transport-legs`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  addServiceQuote: (configId: string, data: Record<string, unknown>) =>
    api<Record<string, unknown>>(`/configurations/${configId}/service-quotes`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listOffers: (dealId: string) => api<Offer[]>(`/deals/${dealId}/offers`),
  createOffer: (dealId: string, data: Record<string, unknown>) =>
    api<Offer>(`/deals/${dealId}/offers`, { method: "POST", body: JSON.stringify(data) }),
  getOfferApprovalPreview: (offerId: string) =>
    api<Record<string, unknown>>(`/offers/${offerId}/approval-preview`),
  submitOfferForApproval: (offerId: string) =>
    api<Offer>(`/offers/${offerId}/submit-for-approval`, { method: "POST" }),
  approveOffer: (offerId: string, acknowledgeWarnings = false) =>
    api<Offer>(`/offers/${offerId}/approve`, {
      method: "POST",
      body: JSON.stringify({ acknowledge_warnings: acknowledgeWarnings }),
    }),
  sendOffer: (offerId: string) =>
    api<{ offer_id: string; status: string; message_id: string }>(`/offers/${offerId}/send`, {
      method: "POST",
    }),
  updateOffer: (offerId: string, data: Record<string, unknown>) =>
    api<Offer>(`/offers/${offerId}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteOffer: (offerId: string) => api<void>(`/offers/${offerId}`, { method: "DELETE" }),
  listMonitoringRules: () => api<MonitoringRule[]>("/monitoring-rules"),
  createMonitoringRule: (data: Record<string, unknown>) =>
    api<MonitoringRule>("/monitoring-rules", { method: "POST", body: JSON.stringify(data) }),
  getMonitoringHealth: (ruleId: string) =>
    api<{ rule_id: string; health_status: string; message: string }>(
      `/monitoring-rules/${ruleId}/health`
    ),
  runMonitoringRule: (ruleId: string) =>
    api<MonitoringRun>(`/monitoring-rules/${ruleId}/run`, { method: "POST" }),
  listMonitoringPublications: (ruleId: string) =>
    api<MonitoredPublication[]>(`/monitoring-rules/${ruleId}/publications`),
  listInternetSources: (params?: {
    product_tag?: string;
    region?: string;
    access_mode?: string;
    source_kind?: string;
    active_only?: boolean;
    include_inactive?: boolean;
  }) => {
    const query = new URLSearchParams();
    if (params?.product_tag) query.set("product_tag", params.product_tag);
    if (params?.region) query.set("region", params.region);
    if (params?.access_mode) query.set("access_mode", params.access_mode);
    if (params?.source_kind) query.set("source_kind", params.source_kind);
    if (params?.active_only === false) query.set("active_only", "false");
    if (params?.include_inactive) query.set("include_inactive", "true");
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return api<InternetSource[]>(`/internet-sources${suffix}`);
  },
  matchInternetSources: (params?: {
    product_keywords?: string;
    regions?: string;
    access_mode?: string;
    include_inactive?: boolean;
  }) => {
    const query = new URLSearchParams();
    if (params?.product_keywords) query.set("product_keywords", params.product_keywords);
    if (params?.regions) query.set("regions", params.regions);
    if (params?.access_mode) query.set("access_mode", params.access_mode);
    if (params?.include_inactive) query.set("include_inactive", "true");
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return api<InternetSourceMatch>(`/internet-sources/match${suffix}`);
  },
  patchInternetSource: (sourceId: string, data: Record<string, unknown>) =>
    api<InternetSource>(`/internet-sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  createInternetSource: (data: Record<string, unknown>) =>
    api<InternetSource>("/internet-sources", { method: "POST", body: JSON.stringify(data) }),
  runInternetSourceSearch: (data: Record<string, unknown>) =>
    api<InternetSourceSearchRun>("/internet-sources/search", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listInternetSourceSearchRuns: () => api<InternetSourceSearchRun[]>("/internet-sources/search/runs"),
  listInternetSourceSearchHits: (runId: string) =>
    api<InternetSourceSearchHit[]>(`/internet-sources/search/runs/${runId}/hits`),
  promoteSearchHit: (hitId: string) =>
    api<{
      hit: InternetSourceSearchHit;
      opportunity_id: string;
      opportunity_title: string;
      feasibility_summary: string;
      supplier_hint: string | null;
      economics_preview: string | null;
    }>(`/internet-sources/search/hits/${hitId}/promote`, { method: "POST" }),
  getAutomationSettings: () => api<AutomationSettings>("/settings/automation"),
  updateAutomationSettings: (data: Record<string, unknown>) =>
    api<AutomationSettings>("/settings/automation", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  runAutomation: () => api<AutomationRun>("/automation/run", { method: "POST" }),
  listAutomationRuns: () => api<AutomationRun[]>("/automation/runs"),
  listAutomationActions: () => api<AutomatedActionLog[]>("/automation/actions"),
  resolveProduct: (opportunityId: string, data: Record<string, unknown>) =>
    api<ProductResolution>(`/opportunities/${opportunityId}/resolve-product`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listSpecValues: (opportunityId: string) =>
    api<OpportunitySpecValue[]>(`/opportunities/${opportunityId}/spec-values`),
  confirmSpecValue: (specValueId: string) =>
    api<OpportunitySpecValue>(`/opportunity-spec-values/${specValueId}/confirm`, {
      method: "POST",
    }),
  listCounterpartyCapabilities: (counterpartyId: string) =>
    api<CounterpartyCapability[]>(`/counterparties/${counterpartyId}/capabilities`),
  enrichCounterparty: (counterpartyId: string, data: Record<string, unknown>) =>
    api<CounterpartyEnrichment>(`/counterparties/${counterpartyId}/enrich`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  confirmCounterpartyCapability: (capabilityId: string) =>
    api<CounterpartyCapability>(`/counterparty-capabilities/${capabilityId}/confirm`, {
      method: "POST",
    }),
};
