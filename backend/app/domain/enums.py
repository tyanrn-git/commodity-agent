import enum


class OpportunityType(str, enum.Enum):
    BUYER_NEED = "BUYER_NEED"
    SUPPLIER_OFFER = "SUPPLIER_OFFER"
    TENDER = "TENDER"
    AUTO_DISCOVERED = "AUTO_DISCOVERED"


class OpportunityStatus(str, enum.Enum):
    NEW = "NEW"
    IN_ANALYSIS = "IN_ANALYSIS"
    ANALYSIS_DONE = "ANALYSIS_DONE"
    NEEDS_INPUT = "NEEDS_INPUT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CONVERTED = "CONVERTED"
    ARCHIVED = "ARCHIVED"
    OTHER = "OTHER"


class OpportunityPipelineStatus(str, enum.Enum):
    DEAL_DRAFT = "DEAL_DRAFT"
    DEAL_AGREED = "DEAL_AGREED"
    IN_EXECUTION = "IN_EXECUTION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class StatusEventKind(str, enum.Enum):
    OPPORTUNITY = "OPPORTUNITY"
    PIPELINE = "PIPELINE"


class StatusActorType(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"


class DealDirection(str, enum.Enum):
    BUYER_LED = "BUYER_LED"
    SUPPLIER_LED = "SUPPLIER_LED"
    MATCHED = "MATCHED"


class DealStage(str, enum.Enum):
    QUALIFICATION = "QUALIFICATION"
    SOURCING = "SOURCING"
    RFQ = "RFQ"
    QUOTE_ANALYSIS = "QUOTE_ANALYSIS"
    CONFIGURATION = "CONFIGURATION"
    OFFER = "OFFER"
    NEGOTIATION = "NEGOTIATION"
    DUE_DILIGENCE = "DUE_DILIGENCE"
    CLOSED = "CLOSED"


class DealOutcome(str, enum.Enum):
    OPEN = "OPEN"
    WON = "WON"
    LOST = "LOST"
    ON_HOLD = "ON_HOLD"
    CANCELLED = "CANCELLED"


class SourceType(str, enum.Enum):
    URL = "URL"
    EMAIL = "EMAIL"
    DOCUMENT = "DOCUMENT"
    API_RESPONSE = "API_RESPONSE"
    MANUAL_INPUT = "MANUAL_INPUT"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    CONVERT = "CONVERT"
    UPLOAD = "UPLOAD"
    EXTRACT = "EXTRACT"
    AI_CALL = "AI_CALL"
    AUTO_EXECUTE = "AUTO_EXECUTE"


class ExtractionStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CACHED = "CACHED"


class TaskStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class TaskType(str, enum.Enum):
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DOCUMENT = "DOCUMENT"
    FOLLOW_UP = "FOLLOW_UP"


class AIUsageOperation(str, enum.Enum):
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    DRAFTING = "drafting"
    MATCHING = "matching"
    RESEARCH = "research"
    CATALOG = "catalog"
    MONITORING = "monitoring"


class ResearchCampaignStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ResearchLeadType(str, enum.Enum):
    BUYER_NEED = "BUYER_NEED"
    PUBLIC_BUYER_NEED = "PUBLIC_BUYER_NEED"
    SUPPLIER = "SUPPLIER"
    LOGISTICS_ROUTE = "LOGISTICS_ROUTE"


class OutreachType(str, enum.Enum):
    BUYER = "BUYER"
    SUPPLIER = "SUPPLIER"
    LOGISTICS = "LOGISTICS"


class OutreachStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT_EXTERNALLY = "SENT_EXTERNALLY"


class ChainViabilityStatus(str, enum.Enum):
    UNKNOWN = "UNKNOWN"
    VIABLE_CANDIDATE = "VIABLE_CANDIDATE"
    NO_VIABLE_CHAIN_FOUND = "NO_VIABLE_CHAIN_FOUND"


class ConfirmationLevel(str, enum.Enum):
    ESTIMATE = "ESTIMATE"
    PUBLIC_INFORMATION = "PUBLIC_INFORMATION"
    COUNTERPARTY_MESSAGE = "COUNTERPARTY_MESSAGE"
    FORMAL_QUOTE = "FORMAL_QUOTE"
    SIGNED_DOCUMENT = "SIGNED_DOCUMENT"


class OrganizationType(str, enum.Enum):
    PRODUCER = "PRODUCER"
    TRADER = "TRADER"
    END_BUYER = "END_BUYER"
    CARRIER = "CARRIER"
    FORWARDER = "FORWARDER"
    TERMINAL = "TERMINAL"
    WAREHOUSE = "WAREHOUSE"
    INSURER = "INSURER"
    INSPECTOR = "INSPECTOR"
    CUSTOMS_BROKER = "CUSTOMS_BROKER"
    FINANCIER = "FINANCIER"
    OTHER = "OTHER"


class CounterpartyVerificationStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    DOMAIN_VERIFIED = "DOMAIN_VERIFIED"
    REGISTRY_VERIFIED = "REGISTRY_VERIFIED"
    REPLIED = "REPLIED"
    INVALID = "INVALID"


class ComplianceReviewStatus(str, enum.Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    MANUALLY_REVIEWED = "MANUALLY_REVIEWED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ContactVerificationStatus(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    DOMAIN_VERIFIED = "DOMAIN_VERIFIED"
    PERSON_VERIFIED = "PERSON_VERIFIED"
    REPLIED = "REPLIED"
    INVALID = "INVALID"


class DealPartyRole(str, enum.Enum):
    BUYER = "BUYER"
    SUPPLIER = "SUPPLIER"
    PRODUCER = "PRODUCER"
    TRADER = "TRADER"
    CARRIER = "CARRIER"
    FORWARDER = "FORWARDER"
    TERMINAL = "TERMINAL"
    WAREHOUSE = "WAREHOUSE"
    INSURER = "INSURER"
    INSPECTOR = "INSPECTOR"
    CUSTOMS_BROKER = "CUSTOMS_BROKER"
    FINANCIER = "FINANCIER"


class DisclosureStatus(str, enum.Enum):
    HIDDEN = "HIDDEN"
    PARTIAL = "PARTIAL"
    DISCLOSED = "DISCLOSED"


class RFQType(str, enum.Enum):
    PRODUCT = "PRODUCT"
    FREIGHT = "FREIGHT"
    TERMINAL = "TERMINAL"
    INSURANCE = "INSURANCE"
    INSPECTION = "INSPECTION"
    CUSTOMS = "CUSTOMS"
    FINANCING = "FINANCING"
    OTHER = "OTHER"


class RFQStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SENT = "SENT"
    PARTIALLY_ANSWERED = "PARTIALLY_ANSWERED"
    ANSWERED = "ANSWERED"
    EXPIRED = "EXPIRED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class BindingClass(str, enum.Enum):
    INFORMATIONAL = "INFORMATIONAL"
    REQUEST = "REQUEST"
    COMMERCIAL_SENSITIVE = "COMMERCIAL_SENSITIVE"
    POTENTIALLY_BINDING = "POTENTIALLY_BINDING"
    BINDING = "BINDING"


class MessageDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class MessageLinkStatus(str, enum.Enum):
    LINKED = "LINKED"
    UNLINKED = "UNLINKED"


class SupplyOfferStatus(str, enum.Enum):
    EXTRACTED = "EXTRACTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class MailboxProvider(str, enum.Enum):
    MOCK = "MOCK"
    GMAIL = "GMAIL"
    GRAPH = "GRAPH"


class DealRiskFlag(str, enum.Enum):
    BANK_DETAILS_CHANGED = "BANK_DETAILS_CHANGED"


class ConfigurationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    FEASIBLE = "FEASIBLE"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    SELECTED = "SELECTED"


class TransportMode(str, enum.Enum):
    SEA = "SEA"
    ROAD = "ROAD"
    RAIL = "RAIL"
    PIPE = "PIPE"
    AIR = "AIR"


class ServiceQuoteType(str, enum.Enum):
    FREIGHT = "FREIGHT"
    TERMINAL = "TERMINAL"
    INSURANCE = "INSURANCE"
    INSPECTION = "INSPECTION"
    CUSTOMS = "CUSTOMS"
    FINANCING = "FINANCING"
    STORAGE = "STORAGE"
    OTHER = "OTHER"


class AllocationStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class EconomicsScenario(str, enum.Enum):
    CURRENT = "CURRENT"
    CONFIRMED = "CONFIRMED"
    CONSERVATIVE = "CONSERVATIVE"
    TARGET = "TARGET"


class SpecMatchResult(str, enum.Enum):
    MATCH = "MATCH"
    ACCEPTABLE_WITH_TOLERANCE = "ACCEPTABLE_WITH_TOLERANCE"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


class OfferStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class MonitoringConnectorType(str, enum.Enum):
    MOCK = "MOCK"
    RSS = "RSS"
    STATIC_HTML = "STATIC_HTML"


class MonitoringAccessMode(str, enum.Enum):
    PUBLIC = "PUBLIC"
    CREDENTIALS = "CREDENTIALS"
    MANUAL_IMPORT = "MANUAL_IMPORT"


class InternetSourceKind(str, enum.Enum):
    TENDER_PORTAL = "TENDER_PORTAL"
    PROCUREMENT_FEED = "PROCUREMENT_FEED"
    GOV_REGISTRY = "GOV_REGISTRY"
    NEWS = "NEWS"
    AGGREGATOR = "AGGREGATOR"
    OTHER = "OTHER"


class InternetSourceSearchRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class InternetSourceSearchHitStatus(str, enum.Enum):
    FOUND = "FOUND"
    EXPIRED = "EXPIRED"
    OPPORTUNITY_CREATED = "OPPORTUNITY_CREATED"
    FILTERED_OUT = "FILTERED_OUT"
    SKIPPED = "SKIPPED"


class InternetSourceFetchStrategy(str, enum.Enum):
    HTML = "HTML"
    TED_API = "TED_API"
    WORLD_BANK_API = "WORLD_BANK_API"


class MonitoringHealthStatus(str, enum.Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class MonitoringRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class MonitoredPublicationStatus(str, enum.Enum):
    SEEN = "SEEN"
    OPPORTUNITY_CREATED = "OPPORTUNITY_CREATED"
    FILTERED_OUT = "FILTERED_OUT"


class SupplierLeadMatchType(str, enum.Enum):
    BUYER_OPPORTUNITY = "BUYER_OPPORTUNITY"
    BUYER_REQUIREMENT = "BUYER_REQUIREMENT"


class SupplierLeadMatchStatus(str, enum.Enum):
    SUGGESTED = "SUGGESTED"
    ROUTE_BUILT = "ROUTE_BUILT"
    OUTREACH_DRAFTED = "OUTREACH_DRAFTED"


class AutomationActionType(str, enum.Enum):
    RFQ_FOLLOW_UP = "RFQ_FOLLOW_UP"


class AutomationActionCategory(str, enum.Enum):
    NON_BINDING = "NON_BINDING"


class AutomationRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class AutomatedActionStatus(str, enum.Enum):
    SENT = "SENT"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"


class CapabilityType(str, enum.Enum):
    PRODUCT = "PRODUCT"
    FREIGHT = "FREIGHT"
    TERMINAL = "TERMINAL"
    INSURANCE = "INSURANCE"
    INSPECTION = "INSPECTION"
    STORAGE = "STORAGE"
    CUSTOMS = "CUSTOMS"
    FINANCING = "FINANCING"
    OTHER = "OTHER"


class SpecValueStatus(str, enum.Enum):
    MISSING = "MISSING"
    EXTRACTED = "EXTRACTED"
    CONFIRMED = "CONFIRMED"


class SpecParameterKind(str, enum.Enum):
    IDENTITY = "IDENTITY"
    VARIANT = "VARIANT"


class SpecVariationMateriality(str, enum.Enum):
    MATERIAL = "MATERIAL"
    IMMATERIAL = "IMMATERIAL"
    UNKNOWN = "UNKNOWN"


class AgentType(str, enum.Enum):
    TENDER_DISCOVERY = "TENDER_DISCOVERY"
    TENDER_QUALIFICATION = "TENDER_QUALIFICATION"
    SUPPLY_DISCOVERY = "SUPPLY_DISCOVERY"
    LOGISTICS_DISCOVERY = "LOGISTICS_DISCOVERY"
    DEAL_COORDINATOR = "DEAL_COORDINATOR"
    PRODUCT_MATCHING = "PRODUCT_MATCHING"
    COMMUNICATION = "COMMUNICATION"
    CATALOG_ASSISTANT = "CATALOG_ASSISTANT"
    COUNTERPARTY_RESEARCH = "COUNTERPARTY_RESEARCH"
    LEGACY_TENDER_PROMOTION = "LEGACY_TENDER_PROMOTION"


class TenderPromotionMode(str, enum.Enum):
    LEGACY = "legacy"
    MANUAL = "manual"
    AUTO_GATES = "auto_gates"


class QualifiedRequirementStatus(str, enum.Enum):
    PENDING = "PENDING"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class AgentTaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentResultType(str, enum.Enum):
    PRODUCT_RESOLUTION = "PRODUCT_RESOLUTION"
    TENDER_ENRICHMENT = "TENDER_ENRICHMENT"
    TENDER_QUALIFICATION = "TENDER_QUALIFICATION"
    TENDER_FEASIBILITY = "TENDER_FEASIBILITY"
    TENDER_SEARCH = "TENDER_SEARCH"
    EXTRACTION = "EXTRACTION"
    RFQ_DRAFT = "RFQ_DRAFT"
    COUNTERPARTY_ENRICHMENT = "COUNTERPARTY_ENRICHMENT"
    CATALOG_ASSISTANT = "CATALOG_ASSISTANT"
    SOURCE_DISCOVERY = "SOURCE_DISCOVERY"
    GENERIC = "GENERIC"
