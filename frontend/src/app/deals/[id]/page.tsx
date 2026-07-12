"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  apiClient,
  ApiError,
  CounterpartyListItem,
  Deal,
  DealParty,
  Requirement,
  RFQ,
  SupplyOffer,
  FulfilmentConfiguration,
  Offer,
} from "@/lib/api";
import { styles } from "@/lib/styles";
import { AppNav } from "@/components/AppNav";
import {
  formatAmount,
  formatCostBreakdownKey,
  formatCostBreakdownValue,
  formatPercent,
} from "@/lib/format";

type Tab = "requirements" | "parties" | "rfqs" | "economics" | "offer";

const SERVICE_COST_FIELDS = [
  { type: "TERMINAL", label: "Порт / терминал" },
  { type: "INSURANCE", label: "Страхование" },
  { type: "CUSTOMS", label: "Таможня и пошлины" },
  { type: "INSPECTION", label: "Инспекция" },
  { type: "STORAGE", label: "Хранение" },
  { type: "FINANCING", label: "Финансирование" },
] as const;

const RFQ_PROTECTED_STATUSES = new Set(["SENT", "PARTIALLY_ANSWERED", "ANSWERED"]);

function canDeleteRfq(rfq: RFQ) {
  return !RFQ_PROTECTED_STATUSES.has(rfq.status);
}

function canDeleteOffer(offer: Offer) {
  return offer.status !== "SENT";
}

const dangerButton = {
  background: "#fff",
  color: "#b91c1c",
  border: "1px solid #b91c1c",
  borderRadius: 6,
  padding: "10px 16px",
  cursor: "pointer",
  fontSize: 14,
  fontWeight: 600,
} as const;

function pickQuickAddSupplier(parties: DealParty[], counterparties: CounterpartyListItem[]): CounterpartyListItem | null {
  const supplierCounterpartyIds = new Set(
    parties.filter((p) => p.role === "SUPPLIER").map((p) => p.counterparty_id)
  );
  const addable = counterparties.filter((c) => !supplierCounterpartyIds.has(c.id));
  const preferred =
    counterparties.find((c) => c.legal_name === "Gulf Base Oil Refinery LLC") ??
    counterparties.find((c) => c.organization_type === "PRODUCER");
  if (preferred && addable.some((c) => c.id === preferred.id)) return preferred;
  return addable[0] ?? null;
}

export default function DealPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("requirements");
  const [deal, setDeal] = useState<Deal | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [parties, setParties] = useState<DealParty[]>([]);
  const [counterparties, setCounterparties] = useState<CounterpartyListItem[]>([]);
  const [rfqs, setRfqs] = useState<RFQ[]>([]);
  const [selectedCounterparty, setSelectedCounterparty] = useState("");
  const [partyRole, setPartyRole] = useState("SUPPLIER");
  const [selectedPartyForRfq, setSelectedPartyForRfq] = useState("");
  const [rfqType, setRfqType] = useState("PRODUCT");
  const [activeRfq, setActiveRfq] = useState<RFQ | null>(null);
  const [supplyOffers, setSupplyOffers] = useState<SupplyOffer[]>([]);
  const [configurations, setConfigurations] = useState<FulfilmentConfiguration[]>([]);
  const [activeConfig, setActiveConfig] = useState<FulfilmentConfiguration | null>(null);
  const [configName, setConfigName] = useState("Вариант поставки");
  const [salesPrice, setSalesPrice] = useState("920");
  const [selectedOfferForConfig, setSelectedOfferForConfig] = useState("");
  const [freightCost, setFreightCost] = useState("5000");
  const [serviceCosts, setServiceCosts] = useState<Record<string, string>>({});
  const [offers, setOffers] = useState<Offer[]>([]);
  const [activeOffer, setActiveOffer] = useState<Offer | null>(null);
  const [selectedConfigForOffer, setSelectedConfigForOffer] = useState("");
  const [selectedBuyerParty, setSelectedBuyerParty] = useState("");
  const [offerPreview, setOfferPreview] = useState<Record<string, unknown> | null>(null);
  const [approvalPreview, setApprovalPreview] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");

  function openConfiguration(config: FulfilmentConfiguration) {
    setActiveConfig(config);
    const seaLeg = config.transport_legs.find((leg) => String(leg.mode) === "SEA") as
      | { cost?: string }
      | undefined;
    if (seaLeg?.cost) {
      setFreightCost(String(Math.round(Number(seaLeg.cost))));
    }
    const costs: Record<string, string> = {};
    for (const field of SERVICE_COST_FIELDS) {
      const quote = config.service_quotes.find((q) => String(q.quote_type) === field.type) as
        | { amount?: string }
        | undefined;
      if (quote?.amount) costs[field.type] = String(Math.round(Number(quote.amount)));
    }
    setServiceCosts(costs);
  }

  const load = useCallback(async () => {
    try {
      const [d, reqs, ps, cps, rs, offersList, configs, dealOffers] = await Promise.all([
        apiClient.getDeal(params.id),
        apiClient.listRequirements(params.id),
        apiClient.listDealParties(params.id),
        apiClient.listCounterparties(),
        apiClient.listDealRfqs(params.id),
        apiClient.listSupplyOffers(params.id),
        apiClient.listConfigurations(params.id),
        apiClient.listOffers(params.id),
      ]);
      setDeal(d);
      setRequirements(reqs);
      setParties(ps);
      setCounterparties(cps);
      setRfqs(rs);
      setSupplyOffers(offersList);
      setConfigurations(configs);
      setOffers(dealOffers);
      const confirmed = offersList.filter((o) => o.user_confirmed);
      setSelectedOfferForConfig((prev) => prev || confirmed[0]?.id || offersList[0]?.id || "");
      const buyers = ps.filter((p) => p.role === "BUYER");
      setSelectedBuyerParty((prev) => prev || buyers[0]?.id || "");
      const selectedConfigs = configs.filter((c) => c.status === "SELECTED" || c.status === "FEASIBLE");
      setSelectedConfigForOffer((prev) => prev || selectedConfigs[0]?.id || configs[0]?.id || "");
      setSelectedCounterparty((prev) => prev || cps[0]?.id || "");
      setSelectedPartyForRfq((prev) => {
        if (prev && ps.some((p) => p.id === prev)) return prev;
        const supplier = ps.find((p) => p.role === "SUPPLIER");
        return supplier?.id || ps[0]?.id || "";
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setMessage(err instanceof Error ? err.message : "Ошибка загрузки сделки");
    }
  }, [params.id, router]);

  useEffect(() => {
    if (params.id) load();
  }, [params.id, load]);

  async function onAddParty(event: FormEvent) {
    event.preventDefault();
    if (!selectedCounterparty) {
      setMessage("Сначала создайте контрагента в разделе «Контрагенты»");
      return;
    }
    try {
      await apiClient.addDealParty(params.id, {
        counterparty_id: selectedCounterparty,
        role: partyRole,
      });
      setMessage("Сторона добавлена в сделку");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Не удалось добавить сторону");
    }
  }

  async function onQuickAddSupplier() {
    const supplier = pickQuickAddSupplier(parties, counterparties);
    if (!supplier) {
      setMessage("Все доступные контрагенты уже добавлены как поставщики");
      return;
    }
    try {
      await apiClient.addDealParty(params.id, {
        counterparty_id: supplier.id,
        role: "SUPPLIER",
      });
      setMessage(`Поставщик «${supplier.trade_name || supplier.legal_name}» добавлен в сделку`);
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Не удалось добавить поставщика");
    }
  }

  async function onCreateRfq(event: FormEvent) {
    event.preventDefault();
    if (!parties.length) {
      setMessage("Сначала добавьте сторону на вкладке «Стороны»");
      return;
    }
    if (!selectedPartyForRfq) {
      setMessage("Выберите сторону для RFQ");
      return;
    }
    try {
      const created = await apiClient.createRfq(params.id, {
        target_deal_party_id: selectedPartyForRfq,
        rfq_type: rfqType,
      });
      setActiveRfq(created);
      setMessage("RFQ создан из шаблона");
      await load();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Не удалось создать RFQ");
    }
  }

  async function openRfq(rfqId: string) {
    const rfq = await apiClient.getRfq(rfqId);
    setActiveRfq(rfq);
    const preview = await apiClient.getRfqApprovalPreview(rfqId);
    setApprovalPreview(preview);
  }

  async function onDeleteRfq(rfqId: string) {
    if (!confirm("Удалить проект письма (RFQ)?")) return;
    try {
      await apiClient.deleteRfq(rfqId);
      if (activeRfq?.id === rfqId) {
        setActiveRfq(null);
        setApprovalPreview(null);
      }
      await load();
      setMessage("Проект письма удалён");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Не удалось удалить RFQ");
    }
  }

  async function onDeleteOffer(offerId: string) {
    if (!confirm("Удалить оферту?")) return;
    try {
      await apiClient.deleteOffer(offerId);
      if (activeOffer?.id === offerId) {
        setActiveOffer(null);
        setOfferPreview(null);
      }
      await load();
      setMessage("Оферта удалена");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Не удалось удалить оферту");
    }
  }

  async function onDraftAi() {
    if (!activeRfq) return;
    const updated = await apiClient.draftRfqWithAi(activeRfq.id);
    setActiveRfq(updated);
    setMessage("AI адаптировал черновик");
    const preview = await apiClient.getRfqApprovalPreview(updated.id);
    setApprovalPreview(preview);
  }

  async function onSubmitApproval() {
    if (!activeRfq) return;
    const updated = await apiClient.submitRfqForApproval(activeRfq.id);
    setActiveRfq(updated);
    setMessage("RFQ отправлен на approval");
    setApprovalPreview(await apiClient.getRfqApprovalPreview(updated.id));
  }

  async function onSendRfq() {
    if (!activeRfq) return;
    const result = await apiClient.sendRfq(activeRfq.id);
    setActiveRfq({ ...activeRfq, status: result.status });
    setMessage("RFQ отправлен (mock mailbox)");
    await load();
  }

  async function onImportReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeRfq) return;
    const input = event.currentTarget.elements.namedItem("reply") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    await apiClient.importInboxEml(file, params.id, activeRfq.id);
    setMessage("Ответ импортирован, SupplyOffer создан");
    input.value = "";
    await load();
    setActiveRfq(await apiClient.getRfq(activeRfq.id));
  }

  async function onApprove() {
    if (!activeRfq) return;
    const updated = await apiClient.approveRfq(activeRfq.id, true);
    setActiveRfq(updated);
    setMessage("RFQ утверждён (без отправки)");
    await load();
  }

  if (!deal) {
    return (
      <main style={{ padding: 24 }}>
        {message ? (
          <>
            <p>{message}</p>
            <button style={styles.button} onClick={() => load()}>
              Повторить
            </button>
          </>
        ) : (
          "Загрузка..."
        )}
      </main>
    );
  }

  const warnings = (approvalPreview?.compliance_warnings as string[]) || [];
  const supplierParties = parties.filter((p) => p.role === "SUPPLIER");
  const quickAddSupplier = pickQuickAddSupplier(parties, counterparties);

  return (
    <main style={styles.page}>
      <div style={styles.container}>
        <AppNav backHref="/opportunities" backLabel="← К возможностям" />

        <div style={styles.card}>
          <h1 style={{ marginTop: 0 }}>Сделка {deal.deal_number}: {deal.title}</h1>
          <p style={{ color: "#64748b" }}>Стадия: {deal.stage}</p>
          <div style={{ display: "flex", gap: 8 }}>
            {(["requirements", "parties", "rfqs", "economics", "offer"] as Tab[]).map((t) => (
              <button
                key={t}
                style={tab === t ? styles.button : styles.secondaryButton}
                onClick={() => setTab(t)}
              >
                {t === "requirements"
                  ? "Требования"
                  : t === "parties"
                    ? "Стороны"
                    : t === "rfqs"
                      ? "RFQ"
                      : t === "economics"
                        ? "Экономика"
                        : "Оферта"}
              </button>
            ))}
          </div>
        </div>

        {tab === "requirements" ? (
          <div style={styles.card}>
            <h2 style={{ marginTop: 0 }}>Требования</h2>
            {requirements.length === 0 ? (
              <p style={{ color: "#64748b" }}>Пока нет требований</p>
            ) : (
              requirements.map((req) => (
                <div key={req.id} style={{ marginBottom: 12 }}>
                  {req.quantity_min} {req.quantity_unit} → {req.destination} ({req.requested_incoterm})
                </div>
              ))
            )}
          </div>
        ) : null}

        {tab === "parties" ? (
          <div style={styles.card}>
            <h2 style={{ marginTop: 0 }}>Стороны сделки</h2>
            {counterparties.length === 0 ? (
              <div style={{ background: "#fef3c7", padding: 12, borderRadius: 6, marginBottom: 16 }}>
                Нет контрагентов.{" "}
                <Link href="/counterparties" style={styles.link}>Создайте контрагента</Link>{" "}
                (поставщика с email), затем добавьте его сюда.
              </div>
            ) : null}
            <form onSubmit={onAddParty}>
              <label style={styles.label}>Контрагент</label>
              <select style={styles.input} value={selectedCounterparty} onChange={(e) => setSelectedCounterparty(e.target.value)}>
                {counterparties.map((c) => (
                  <option key={c.id} value={c.id}>{c.trade_name || c.legal_name}</option>
                ))}
              </select>
              <label style={styles.label}>Роль</label>
              <select style={styles.input} value={partyRole} onChange={(e) => setPartyRole(e.target.value)}>
                <option value="SUPPLIER">Поставщик</option>
                <option value="BUYER">Покупатель</option>
                <option value="FORWARDER">Экспедитор</option>
              </select>
              <button style={styles.button} type="submit">Добавить сторону</button>
            </form>
            <ul style={{ marginTop: 16 }}>
              {parties.length === 0 ? (
                <li style={{ color: "#64748b" }}>Пока нет сторон в сделке</li>
              ) : (
                parties.map((p) => (
                  <li key={p.id}>
                    {p.counterparty?.trade_name || p.counterparty?.legal_name} · {p.role} · {p.disclosure_status}
                  </li>
                ))
              )}
            </ul>
          </div>
        ) : null}

        {tab === "rfqs" ? (
          <>
            <div style={styles.card}>
              <h2 style={{ marginTop: 0 }}>Создать RFQ</h2>
              {supplierParties.length === 0 ? (
                <div style={{ background: "#fef3c7", padding: 12, borderRadius: 6, marginBottom: 16 }}>
                  <p style={{ margin: "0 0 8px" }}>
                    RFQ на товар отправляется поставщику. В сделке пока нет стороны с ролью SUPPLIER.
                  </p>
                  {quickAddSupplier ? (
                    <button type="button" style={styles.button} onClick={onQuickAddSupplier}>
                      Быстро добавить {quickAddSupplier.trade_name || quickAddSupplier.legal_name}
                    </button>
                  ) : (
                    <p style={{ margin: 0, color: "#64748b" }}>
                      <Link href="/counterparties" style={styles.link}>Создайте контрагента</Link>{" "}
                      или добавьте на вкладке «Стороны».
                    </p>
                  )}
                </div>
              ) : quickAddSupplier ? (
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 6, marginBottom: 16, border: "1px solid #e2e8f0" }}>
                  <p style={{ margin: "0 0 8px", color: "#64748b" }}>
                    Можно добавить ещё одного поставщика для сравнения котировок:
                  </p>
                  <button type="button" style={styles.secondaryButton} onClick={onQuickAddSupplier}>
                    Быстро добавить {quickAddSupplier.trade_name || quickAddSupplier.legal_name}
                  </button>
                </div>
              ) : null}
              <form onSubmit={onCreateRfq}>
                <label style={styles.label}>Сторона</label>
                <select
                  style={styles.input}
                  value={selectedPartyForRfq}
                  onChange={(e) => setSelectedPartyForRfq(e.target.value)}
                  disabled={parties.length === 0}
                >
                  <option value="">— выберите сторону —</option>
                  {parties.map((p) => (
                    <option key={p.id} value={p.id}>
                      {(p.counterparty?.trade_name || p.counterparty?.legal_name) + " · " + p.role}
                      {p.role !== "SUPPLIER" && rfqType === "PRODUCT" ? " (не поставщик)" : ""}
                    </option>
                  ))}
                </select>
                <label style={styles.label}>Тип RFQ</label>
                <select style={styles.input} value={rfqType} onChange={(e) => setRfqType(e.target.value)}>
                  <option value="PRODUCT">PRODUCT</option>
                  <option value="FREIGHT">FREIGHT</option>
                </select>
                <button
                  style={styles.button}
                  type="submit"
                  disabled={parties.length === 0 || !selectedPartyForRfq}
                >
                  Создать из шаблона
                </button>
              </form>
              <ul style={{ marginTop: 16 }}>
                {rfqs.map((r) => (
                  <li key={r.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <button type="button" style={{ ...styles.link, border: "none", background: "none", padding: 0, cursor: "pointer" }} onClick={() => openRfq(r.id)}>
                      {r.rfq_type} · {r.status} · {r.subject || "(без темы)"}
                    </button>
                    {canDeleteRfq(r) ? (
                      <button type="button" style={dangerButton} onClick={() => onDeleteRfq(r.id)}>
                        Удалить
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>

            {activeRfq ? (
              <div style={styles.card}>
                <h2 style={{ marginTop: 0 }}>RFQ builder · {activeRfq.status}</h2>
                <label style={styles.label}>Subject</label>
                <input
                  style={styles.input}
                  value={activeRfq.subject}
                  onChange={(e) => setActiveRfq({ ...activeRfq, subject: e.target.value })}
                />
                <label style={styles.label}>Body</label>
                <textarea
                  style={{ ...styles.input, minHeight: 180 }}
                  value={activeRfq.body}
                  onChange={(e) => setActiveRfq({ ...activeRfq, body: e.target.value })}
                />
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button style={styles.secondaryButton} onClick={onDraftAi}>AI адаптация</button>
                  <button
                    style={styles.button}
                    onClick={async () => {
                      const updated = await apiClient.updateRfq(activeRfq.id, {
                        subject: activeRfq.subject,
                        body: activeRfq.body,
                      });
                      setActiveRfq(updated);
                      setApprovalPreview(await apiClient.getRfqApprovalPreview(updated.id));
                      setMessage("Черновик сохранён");
                    }}
                  >
                    Сохранить
                  </button>
                  <button style={styles.button} onClick={onSubmitApproval}>На approval</button>
                  <button style={styles.secondaryButton} onClick={onApprove}>Утвердить</button>
                  {activeRfq.status === "APPROVED" ? (
                    <button style={styles.button} onClick={onSendRfq}>Отправить RFQ</button>
                  ) : null}
                  {canDeleteRfq(activeRfq) ? (
                    <button type="button" style={dangerButton} onClick={() => onDeleteRfq(activeRfq.id)}>
                      Удалить
                    </button>
                  ) : null}
                </div>
                {activeRfq.status === "SENT" || activeRfq.status === "PARTIALLY_ANSWERED" || activeRfq.status === "ANSWERED" ? (
                  <form onSubmit={onImportReply} style={{ marginTop: 16 }}>
                    <label style={styles.label}>Импорт ответа (.eml)</label>
                    <input type="file" name="reply" accept=".eml" required />
                    <button style={{ ...styles.button, marginTop: 8 }} type="submit">Импортировать ответ</button>
                  </form>
                ) : null}
                <div style={{ marginTop: 12, fontSize: 13 }}>
                  Requested fields: {activeRfq.requested_fields.join(", ")}
                </div>
              </div>
            ) : null}

            {approvalPreview ? (
              <div style={styles.card}>
                <h2 style={{ marginTop: 0 }}>Approval preview</h2>
                {warnings.includes("counterparty_not_reviewed") ? (
                  <div style={{ background: "#fef3c7", padding: 12, borderRadius: 6, marginBottom: 12 }}>
                    Внимание: контрагент NOT_REVIEWED — требуется подтверждение при утверждении
                  </div>
                ) : null}
                <div style={{ fontSize: 14 }}>
                  <div>Binding class: {String(approvalPreview.binding_class)}</div>
                  <div>Recipients: {JSON.stringify(approvalPreview.recipients)}</div>
                  <div>Warnings: {warnings.join(", ") || "нет"}</div>
                </div>
              </div>
            ) : null}

            <div style={styles.card}>
              <h2 style={{ marginTop: 0 }}>SupplyOffers</h2>
              {supplyOffers.length === 0 ? (
                <p style={{ color: "#64748b" }}>Пока нет котировок от поставщиков</p>
              ) : (
                supplyOffers.map((o) => (
                  <div key={o.id} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid #e2e8f0" }}>
                    <strong>{o.product_name || "Товар"}</strong> · {o.price} {o.currency} · {o.incoterm}
                    <div style={{ fontSize: 13, color: "#64748b" }}>
                      {o.available_quantity} {o.quantity_unit} · {o.status}
                      {o.missing_fields?.length ? ` · missing: ${o.missing_fields.join(", ")}` : ""}
                    </div>
                    {!o.user_confirmed ? (
                      <button
                        style={{ ...styles.secondaryButton, marginTop: 8 }}
                        onClick={async () => {
                          await apiClient.confirmSupplyOffer(o.id);
                          setMessage("SupplyOffer подтверждён");
                          await load();
                        }}
                      >
                        Подтвердить извлечение
                      </button>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </>
        ) : null}

        {tab === "economics" ? (
          <>
            <div style={styles.card}>
              <h2 style={{ marginTop: 0 }}>Создать конфигурацию</h2>
              {supplyOffers.length === 0 ? (
                <p style={{ color: "#64748b" }}>
                  Сначала импортируйте ответ поставщика на вкладке RFQ и подтвердите SupplyOffer.
                </p>
              ) : (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (!selectedOfferForConfig) return;
                    const created = await apiClient.createConfiguration(params.id, {
                      supply_offer_id: selectedOfferForConfig,
                      name: configName,
                      sales_price_per_unit: Number(salesPrice),
                      sales_currency: "USD",
                    });
                    setActiveConfig(created);
                    openConfiguration(created);
                    setMessage("Конфигурация создана и рассчитана");
                    await load();
                  }}
                >
                  <label style={styles.label}>SupplyOffer</label>
                  <select
                    style={styles.input}
                    value={selectedOfferForConfig}
                    onChange={(e) => setSelectedOfferForConfig(e.target.value)}
                  >
                    {supplyOffers.map((o) => (
                      <option key={o.id} value={o.id}>
                        {(o.product_name || "Товар") + " · " + o.price + " " + o.currency}
                        {o.user_confirmed ? " ✓" : ""}
                      </option>
                    ))}
                  </select>
                  <label style={styles.label}>Название</label>
                  <input style={styles.input} value={configName} onChange={(e) => setConfigName(e.target.value)} />
                  <label style={styles.label}>Цена продажи за единицу (USD/MT)</label>
                  <input style={styles.input} value={salesPrice} onChange={(e) => setSalesPrice(e.target.value)} />
                  <button style={styles.button} type="submit">Собрать и рассчитать</button>
                </form>
              )}
            </div>

            <div style={styles.card}>
              <h2 style={{ marginTop: 0 }}>Варианты поставки</h2>
              {configurations.length === 0 ? (
                <p style={{ color: "#64748b" }}>Пока нет конфигураций</p>
              ) : (
                configurations.map((c) => (
                  <div key={c.id} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid #e2e8f0" }}>
                    <button
                      type="button"
                      style={{ ...styles.link, border: "none", background: "none", padding: 0, cursor: "pointer" }}
                      onClick={() => openConfiguration(c)}
                    >
                      <strong>{c.name}</strong>
                    </button>
                    {" · "}{c.status}
                    {c.is_stale ? " · STALE" : ""}
                    <div style={{ fontSize: 13, color: "#64748b" }}>
                      Выручка {formatAmount(c.revenue)} · Себестоимость {formatAmount(c.total_cost)} · Маржа{" "}
                      {formatAmount(c.gross_margin)} ({formatPercent(c.gross_margin_percent)}%)
                    </div>
                  </div>
                ))
              )}
            </div>

            {activeConfig ? (
              <div style={styles.card}>
                <h2 style={{ marginTop: 0 }}>{activeConfig.name}</h2>
                {activeConfig.is_stale ? (
                  <div style={{ background: "#fef3c7", padding: 12, borderRadius: 6, marginBottom: 12 }}>
                    Входные данные устарели: {activeConfig.stale_reason}
                  </div>
                ) : null}
                <div style={{ fontSize: 14, marginBottom: 12 }}>
                  <div>Spec match: {String((activeConfig.spec_match_summary as { health_status?: string })?.health_status || "—")}</div>
                  <div>Полнота данных: {formatPercent(activeConfig.completeness_score)}%</div>
                </div>
                {activeConfig.cost_breakdown ? (
                  <div style={{ fontSize: 13, marginBottom: 12 }}>
                    {Object.entries(activeConfig.cost_breakdown).map(([k, v]) => (
                      <div key={k}>
                        {formatCostBreakdownKey(k)}: {formatCostBreakdownValue(k, String(v))}
                      </div>
                    ))}
                  </div>
                ) : null}
                <div style={{ fontSize: 14, marginBottom: 12 }}>
                  <div>
                    Выручка {formatAmount(activeConfig.revenue)} · Себестоимость {formatAmount(activeConfig.total_cost)} ·
                    Маржа {formatAmount(activeConfig.gross_margin)} ({formatPercent(activeConfig.gross_margin_percent)}%)
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
                  <button
                    style={styles.secondaryButton}
                    onClick={async () => {
                      const updated = await apiClient.recalculateConfiguration(activeConfig.id);
                      setActiveConfig(updated);
                      setMessage("Пересчитано (CURRENT)");
                      await load();
                    }}
                  >
                    Пересчитать
                  </button>
                  <button
                    style={styles.button}
                    onClick={async () => {
                      const updated = await apiClient.confirmConfiguration(activeConfig.id);
                      setActiveConfig(updated);
                      setMessage("Сценарий CONFIRMED сохранён");
                      await load();
                    }}
                  >
                    Подтвердить сценарий
                  </button>
                </div>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    await apiClient.addTransportLeg(activeConfig.id, {
                      origin: "Jebel Ali",
                      destination: activeConfig.destination || "Rotterdam",
                      cost: Number(freightCost.replace(/\s/g, "")),
                      currency: "USD",
                      mode: "SEA",
                    });
                    const updated = await apiClient.recalculateConfiguration(activeConfig.id);
                    openConfiguration(updated);
                    setMessage("Фрахт сохранён");
                    await load();
                  }}
                >
                  <label style={styles.label}>Морской фрахт (USD, всего за партию)</label>
                  <input style={styles.input} value={freightCost} onChange={(e) => setFreightCost(e.target.value)} />
                  <button style={{ ...styles.button, marginTop: 8 }} type="submit">Сохранить фрахт</button>
                </form>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    for (const field of SERVICE_COST_FIELDS) {
                      const amount = serviceCosts[field.type];
                      if (!amount) continue;
                      await apiClient.addServiceQuote(activeConfig.id, {
                        quote_type: field.type,
                        amount: Number(amount.replace(/\s/g, "")),
                        currency: "USD",
                      });
                    }
                    const updated = await apiClient.recalculateConfiguration(activeConfig.id);
                    openConfiguration(updated);
                    setMessage("Доп. расходы сохранены");
                    await load();
                  }}
                  style={{ marginTop: 16 }}
                >
                  <label style={styles.label}>Дополнительные расходы (USD)</label>
                  {SERVICE_COST_FIELDS.map((field) => (
                    <div key={field.type} style={{ marginBottom: 8 }}>
                      <span style={{ fontSize: 13, color: "#64748b" }}>{field.label}</span>
                      <input
                        style={styles.input}
                        value={serviceCosts[field.type] || ""}
                        placeholder="0"
                        onChange={(e) =>
                          setServiceCosts({ ...serviceCosts, [field.type]: e.target.value })
                        }
                      />
                    </div>
                  ))}
                  <button style={styles.secondaryButton} type="submit">Сохранить доп. расходы</button>
                </form>
              </div>
            ) : null}
          </>
        ) : null}

        {tab === "offer" ? (
          <>
            <div style={styles.card}>
              <h2 style={{ marginTop: 0 }}>Оферта покупателю</h2>
              {parties.filter((p) => p.role === "BUYER").length === 0 ? (
                <div style={{ background: "#fef3c7", padding: 12, borderRadius: 6, marginBottom: 16 }}>
                  <p style={{ margin: "0 0 8px" }}>Нужна сторона с ролью BUYER в сделке.</p>
                  {counterparties.find((c) => c.legal_name === "Rotterdam Base Oils BV") ? (
                    <button
                      type="button"
                      style={styles.button}
                      onClick={async () => {
                        const buyer = counterparties.find((c) => c.legal_name === "Rotterdam Base Oils BV");
                        if (!buyer) return;
                        await apiClient.addDealParty(params.id, {
                          counterparty_id: buyer.id,
                          role: "BUYER",
                        });
                        setMessage("Покупатель добавлен в сделку");
                        await load();
                      }}
                    >
                      Быстро добавить Rotterdam Base Oils
                    </button>
                  ) : null}
                </div>
              ) : null}
              {configurations.length === 0 ? (
                <p style={{ color: "#64748b" }}>Сначала создайте конфигурацию на вкладке «Экономика».</p>
              ) : (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    if (!selectedConfigForOffer || !selectedBuyerParty) return;
                    const created = await apiClient.createOffer(params.id, {
                      configuration_id: selectedConfigForOffer,
                      target_deal_party_id: selectedBuyerParty,
                    });
                    setActiveOffer(created);
                    setOfferPreview(await apiClient.getOfferApprovalPreview(created.id));
                    setMessage("Оферта создана");
                    await load();
                  }}
                >
                  <label style={styles.label}>Конфигурация</label>
                  <select
                    style={styles.input}
                    value={selectedConfigForOffer}
                    onChange={(e) => setSelectedConfigForOffer(e.target.value)}
                  >
                    {configurations.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} · {c.status}{c.is_stale ? " · STALE" : ""}
                      </option>
                    ))}
                  </select>
                  <label style={styles.label}>Покупатель</label>
                  <select
                    style={styles.input}
                    value={selectedBuyerParty}
                    onChange={(e) => setSelectedBuyerParty(e.target.value)}
                    disabled={parties.filter((p) => p.role === "BUYER").length === 0}
                  >
                    <option value="">— выберите покупателя —</option>
                    {parties
                      .filter((p) => p.role === "BUYER")
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {(p.counterparty?.trade_name || p.counterparty?.legal_name) + " · " + p.disclosure_status}
                        </option>
                      ))}
                  </select>
                  <button style={styles.button} type="submit" disabled={!selectedBuyerParty}>
                    Создать оферту
                  </button>
                </form>
              )}
            </div>

            {offers.length > 0 ? (
              <div style={styles.card}>
                <h2 style={{ marginTop: 0 }}>Оферты</h2>
                {offers.map((o) => (
                  <div key={o.id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                    <button
                      type="button"
                      style={{ ...styles.link, border: "none", background: "none", padding: 0, cursor: "pointer" }}
                      onClick={async () => {
                        setActiveOffer(o);
                        setOfferPreview(await apiClient.getOfferApprovalPreview(o.id));
                      }}
                    >
                      {o.subject || "(без темы)"}
                    </button>
                    <span>· {o.status}</span>
                    {canDeleteOffer(o) ? (
                      <button type="button" style={dangerButton} onClick={() => onDeleteOffer(o.id)}>
                        Удалить
                      </button>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : null}

            {activeOffer ? (
              <div style={styles.card}>
                <h2 style={{ marginTop: 0 }}>Превью · {activeOffer.status}</h2>
                <textarea
                  style={{ ...styles.input, minHeight: 200 }}
                  value={activeOffer.body}
                  onChange={(e) => setActiveOffer({ ...activeOffer, body: e.target.value })}
                />
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                  <button
                    style={styles.secondaryButton}
                    onClick={async () => {
                      const updated = await apiClient.updateOffer(activeOffer.id, { body: activeOffer.body });
                      setActiveOffer(updated);
                      setOfferPreview(await apiClient.getOfferApprovalPreview(updated.id));
                      setMessage("Оферта сохранена");
                    }}
                  >
                    Сохранить
                  </button>
                  <button
                    style={styles.button}
                    onClick={async () => {
                      const updated = await apiClient.submitOfferForApproval(activeOffer.id);
                      setActiveOffer(updated);
                      setOfferPreview(await apiClient.getOfferApprovalPreview(updated.id));
                      setMessage("На approval");
                    }}
                  >
                    На approval
                  </button>
                  <button
                    style={styles.secondaryButton}
                    onClick={async () => {
                      const updated = await apiClient.approveOffer(activeOffer.id, true);
                      setActiveOffer(updated);
                      setMessage("Оферта утверждена");
                    }}
                  >
                    Утвердить
                  </button>
                  {activeOffer.status === "APPROVED" ? (
                    <button
                      style={styles.button}
                      onClick={async () => {
                        await apiClient.sendOffer(activeOffer.id);
                        setMessage("Оферта отправлена (mock)");
                        await load();
                      }}
                    >
                      Отправить
                    </button>
                  ) : null}
                  {canDeleteOffer(activeOffer) ? (
                    <button type="button" style={dangerButton} onClick={() => onDeleteOffer(activeOffer.id)}>
                      Удалить
                    </button>
                  ) : null}
                </div>
                {offerPreview ? (
                  <div style={{ marginTop: 12, fontSize: 13 }}>
                    <div>Warnings: {((offerPreview.compliance_warnings as string[]) || []).join(", ") || "нет"}</div>
                    <div>Recipients: {JSON.stringify(offerPreview.recipients)}</div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </>
        ) : null}

        {message ? (
          <p style={{ padding: 12, background: "#f1f5f9", borderRadius: 6 }}>{message}</p>
        ) : null}
      </div>
    </main>
  );
}
