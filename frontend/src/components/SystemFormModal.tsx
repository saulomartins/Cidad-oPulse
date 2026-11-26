import { useState, type FormEvent } from "react";
import { X, Globe, MapPin, Sparkles, Tag } from "lucide-react";
import type { AiUsage, MonitoredSystem, SystemPayload, SystemStage } from "../types";

interface Props {
  initial?: MonitoredSystem | null;
  onClose: () => void;
  onSave: (payload: SystemPayload) => Promise<void>;
}

const CITIZEN_AREAS = [
  "Serviços Públicos Digitais",
  "Saúde",
  "Educação",
  "Mobilidade Urbana",
  "Transparência e Dados Abertos",
  "Assistência Social",
  "Segurança Pública",
  "Meio Ambiente e Sustentabilidade",
  "Acessibilidade e Inclusão Digital",
  "Ouvidoria e Participação Cidadã",
];

const ORGANIZATION_TYPES = [
  "Governo Estadual",
  "Governo Municipal",
  "Governo Federal",
  "Consórcio Intermunicipal",
  "Iniciativa Cívica / ONG",
  "Empresa Pública / TIC Estadual ou Municipal",
  "Privado de Impacto Social",
];

const BRAZIL_UFS = [
  { uf: "", label: "Todos os estados / Abrangência Nacional" },
  { uf: "AC", label: "AC — Acre" },
  { uf: "AL", label: "AL — Alagoas" },
  { uf: "AP", label: "AP — Amapá" },
  { uf: "AM", label: "AM — Amazonas" },
  { uf: "BA", label: "BA — Bahia" },
  { uf: "CE", label: "CE — Ceará" },
  { uf: "DF", label: "DF — Distrito Federal" },
  { uf: "ES", label: "ES — Espírito Santo" },
  { uf: "GO", label: "GO — Goiás" },
  { uf: "MA", label: "MA — Maranhão" },
  { uf: "MT", label: "MT — Mato Grosso" },
  { uf: "MS", label: "MS — Mato Grosso do Sul" },
  { uf: "MG", label: "MG — Minas Gerais" },
  { uf: "PA", label: "PA — Pará" },
  { uf: "PB", label: "PB — Paraíba" },
  { uf: "PR", label: "PR — Paraná" },
  { uf: "PE", label: "PE — Pernambuco" },
  { uf: "PI", label: "PI — Piauí" },
  { uf: "RJ", label: "RJ — Rio de Janeiro" },
  { uf: "RN", label: "RN — Rio Grande do Norte" },
  { uf: "RS", label: "RS — Rio Grande do Sul" },
  { uf: "RO", label: "RO — Rondônia" },
  { uf: "RR", label: "RR — Roraima" },
  { uf: "SC", label: "SC — Santa Catarina" },
  { uf: "SP", label: "SP — São Paulo" },
  { uf: "SE", label: "SE — Sergipe" },
  { uf: "TO", label: "TO — Tocantins" },
];

export function SystemFormModal({ initial, onClose, onSave }: Props) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [urlsText, setUrlsText] = useState((initial?.urls ?? []).join("\n"));
  const [keywordsText, setKeywordsText] = useState((initial?.keywords ?? []).join(", "));
  const [socialProfilesText, setSocialProfilesText] = useState((initial?.social_profiles ?? []).join(", "));
  const [stage, setStage] = useState<SystemStage>(initial?.stage ?? "iniciativa");
  const [usesAi, setUsesAi] = useState<AiUsage>(initial?.uses_ai ?? "sem_ia");
  const [aiDetails, setAiDetails] = useState(initial?.ai_details ?? "");
  const [citizenArea, setCitizenArea] = useState(initial?.citizen_area ?? CITIZEN_AREAS[0]);
  const [targetAudience, setTargetAudience] = useState(initial?.target_audience ?? "Cidadãos em geral");
  const [organizationType, setOrganizationType] = useState(initial?.organization_type ?? "Governo Estadual");
  const [country, setCountry] = useState(initial?.country ?? "Brasil");
  const [stateUf, setStateUf] = useState(initial?.state_uf ?? "");
  const [municipality, setMunicipality] = useState(initial?.municipality ?? "");
  const [impactSummary, setImpactSummary] = useState(initial?.impact_summary ?? "");
  const [monitorSentiment, setMonitorSentiment] = useState(initial?.monitor_sentiment ?? true);
  const [monitorAwards, setMonitorAwards] = useState(initial?.monitor_awards ?? true);
  const [saving, setSaving] = useState(false);

  const isMunicipalScope = organizationType.toLowerCase().includes("municipal");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const urls = urlsText
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const keywords = keywordsText
        .split(/[,\n]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const social_profiles = socialProfilesText
        .split(/[,\n]+/)
        .map((s) => s.trim())
        .filter(Boolean);

      await onSave({
        name,
        description,
        urls,
        keywords,
        social_profiles,
        stage,
        uses_ai: usesAi,
        ai_details: aiDetails,
        citizen_area: citizenArea,
        target_audience: targetAudience,
        organization_type: organizationType,
        country,
        state_uf: stateUf,
        municipality,
        impact_summary: impactSummary,
        monitor_sentiment: monitorSentiment,
        monitor_awards: monitorAwards,
        is_active: true,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
      <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              {initial ? "Editar Sistema Monitorado" : "Cadastrar Novo Sistema / Iniciativa"}
            </h2>
            <p className="text-xs text-slate-500">
              Preencha URLs, palavras-chave e o perfil do sistema para monitorar sentimento e pesquisar premiações no mundo todo.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6 p-6">
          {/* Bloco 1: Identificação */}
          <div className="space-y-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-indigo-700">
              <Globe className="h-4 w-4" />
              1. Identificação e O que o Sistema Faz
            </h3>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                Nome do Sistema ou Iniciativa *
              </label>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex.: Portal Cidadão Digital, App Saúde na Palma..."
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold text-slate-700">
                O que o sistema é e como atende ao cidadão *
              </label>
              <textarea
                required
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Descreva claramente qual problema do cidadão o software resolve, funcionalidades principais e diferenciais (usado pelo Radar Mundial de Prêmios)."
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>
          </div>

          {/* Bloco 2: Monitoramento Web e Redes Sociais */}
          <div className="space-y-4 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-indigo-700">
              <Tag className="h-4 w-4" />
              2. Monitoramento na Internet e Redes Sociais
            </h3>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  URLs do Sistema (uma por linha)
                </label>
                <textarea
                  rows={3}
                  value={urlsText}
                  onChange={(e) => setUrlsText(e.target.value)}
                  placeholder={"https://meusistema.gov.br\nhttps://play.google.com/store/apps/..."}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Palavras-chave, Hashtags e Arrobas (separadas por vírgula)
                </label>
                <textarea
                  rows={3}
                  value={keywordsText}
                  onChange={(e) => setKeywordsText(e.target.value)}
                  placeholder='Ex.: "Portal Cidadão", #CidadaoDigital, @meusistema, app prefeitura'
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Perfis / Páginas Públicas no Instagram e Facebook para monitorar comentários (separados por vírgula)
                </label>
                <input
                  value={socialProfilesText}
                  onChange={(e) => setSocialProfilesText(e.target.value)}
                  placeholder="Ex.: @educacaomg, @governomg, @prodemge, https://www.facebook.com/secretariadeeducacaomg/"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs focus:border-indigo-500 focus:outline-none"
                />
                <p className="mt-1 text-[11px] text-slate-500">
                  Informe apenas perfis com <code>@usuario</code> ou links completos do Instagram/Facebook (ex.:{" "}
                  <code>https://www.facebook.com/secretariadeeducacaomg/</code>).
                </p>
              </div>
            </div>
          </div>

          {/* Bloco 3: Perfil para Radar Mundial de Premiações */}
          <div className="space-y-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-indigo-700">
              <Sparkles className="h-4 w-4" />
              3. Perfil para Pesquisa Mundial de Premiações e Concursos
            </h3>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Estágio do Sistema
                </label>
                <select
                  value={stage}
                  onChange={(e) => setStage(e.target.value as SystemStage)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="iniciativa">Iniciativa / Protótipo / Em Desenvolvimento</option>
                  <option value="producao">Já Desenvolvido / Em Produção atendendo o Cidadão</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Utiliza Inteligência Artificial?
                </label>
                <select
                  value={usesAi}
                  onChange={(e) => setUsesAi(e.target.value as AiUsage)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="com_ia">Sim — Sistema desenvolvido com IA</option>
                  <option value="sem_ia">Não — Sistema sem IA (software tradicional)</option>
                  <option value="hibrido">Híbrido — Combina módulos tradicionais e IA</option>
                </select>
              </div>

              {usesAi !== "sem_ia" && (
                <div className="md:col-span-2">
                  <label className="mb-1 block text-xs font-semibold text-slate-700">
                    Como a IA é utilizada no atendimento ao cidadão?
                  </label>
                  <input
                    value={aiDetails}
                    onChange={(e) => setAiDetails(e.target.value)}
                    placeholder="Ex.: Chatbot generativo para dúvidas, triagem inteligente de filas, transcrição acessível..."
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                </div>
              )}

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Área de Atendimento ao Cidadão
                </label>
                <select
                  value={citizenArea}
                  onChange={(e) => setCitizenArea(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  {CITIZEN_AREAS.map((area) => (
                    <option key={area} value={area}>
                      {area}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Esfera / Tipo de Organização
                </label>
                <select
                  value={ORGANIZATION_TYPES.includes(organizationType) ? organizationType : "Governo Estadual"}
                  onChange={(e) => setOrganizationType(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  {ORGANIZATION_TYPES.map((org) => (
                    <option key={org} value={org}>
                      {org}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Estado (UF) — ancora buscas e bloqueia outros estados
                </label>
                <select
                  value={stateUf}
                  onChange={(e) => setStateUf(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                >
                  {BRAZIL_UFS.map((item) => (
                    <option key={item.uf || "ALL"} value={item.uf}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Município {isMunicipalScope ? "(recomendado para esfera municipal)" : "(opcional)"}
                </label>
                <input
                  value={municipality}
                  onChange={(e) => setMunicipality(e.target.value)}
                  placeholder="Ex.: Belo Horizonte, Uberlândia, Curitiba..."
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />
              </div>

              {(stateUf || municipality) && (
                <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50/70 px-3 py-2 text-xs text-emerald-900 md:col-span-2">
                  <MapPin className="h-4 w-4 shrink-0 text-emerald-600" />
                  <span>
                    <strong>Filtro geográfico ativo nas buscas:</strong>{" "}
                    {[municipality, stateUf ? BRAZIL_UFS.find((b) => b.uf === stateUf)?.label || stateUf : ""]
                      .filter(Boolean)
                      .join(" • ")}{" "}
                    — matérias sobre outros estados serão descartadas automaticamente.
                  </span>
                </div>
              )}

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Público-alvo Cidadão
                </label>
                <input
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  placeholder="Ex.: Pacientes do SUS, estudantes, contribuintes, idosos..."
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  País de Origem
                </label>
                <input
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  placeholder="Brasil"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />
              </div>

              <div className="md:col-span-2">
                <label className="mb-1 block text-xs font-semibold text-slate-700">
                  Impacto Esperado ou Comprovado
                </label>
                <input
                  value={impactSummary}
                  onChange={(e) => setImpactSummary(e.target.value)}
                  placeholder="Ex.: Redução de filas em 50%, 100 mil atendimentos digitais, economia de tempo para o cidadão..."
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                />
              </div>
            </div>

            <div className="flex flex-wrap gap-6 pt-1">
              <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={monitorSentiment}
                  onChange={(e) => setMonitorSentiment(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                />
                Incluir no monitoramento recorrente de sentimento
              </label>
              <label className="flex items-center gap-2 text-xs font-medium text-slate-700">
                <input
                  type="checkbox"
                  checked={monitorAwards}
                  onChange={(e) => setMonitorAwards(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600"
                />
                Incluir no radar semanal mundial de premiações
              </label>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-slate-200 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Salvando..." : initial ? "Salvar Alterações" : "Cadastrar Sistema"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
