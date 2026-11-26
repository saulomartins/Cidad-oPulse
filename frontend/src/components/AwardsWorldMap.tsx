import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import { Calendar, ExternalLink, Globe2, MapPin, ZoomIn } from "lucide-react";
import type { AwardOpportunity } from "../types";
import { MatchScoreBadge } from "./MatchScoreBadge";
import { buildFallbackSearchUrl, normalizeExternalUrl } from "../utils/links";

interface Props {
  awards: AwardOpportunity[];
  heightClass?: string;
  showClosedToggle?: boolean;
}

const REGION_PRESETS = [
  { label: "Mundo", center: [20, 5] as [number, number], zoom: 2 },
  { label: "Brasil", center: [-17.5, -47] as [number, number], zoom: 5 },
  { label: "Europa", center: [48, 6] as [number, number], zoom: 5 },
  { label: "EUA", center: [40.5, -75] as [number, number], zoom: 6 },
  { label: "Oriente Médio", center: [25.2, 55.3] as [number, number], zoom: 6 },
  { label: "América Latina", center: [-10, -64] as [number, number], zoom: 4 },
];

type VisualStatus = "aberto" | "previsto" | "encerrado";

function getVisualStatus(a: AwardOpportunity): VisualStatus {
  if (a.is_open_for_application && a.award_status === "aberto") return "aberto";
  if (a.award_status === "previsto" || a.award_status === "recorrente") return "previsto";
  return "encerrado";
}

function statusPriority(s: VisualStatus): number {
  return s === "aberto" ? 3 : s === "previsto" ? 2 : 1;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDeadlinePill(award: AwardOpportunity, vStatus: VisualStatus): string {
  if (vStatus === "encerrado") return "Encerrado";
  if (vStatus === "previsto") return "Próximo ciclo";
  if (award.days_remaining !== null && award.days_remaining !== undefined) {
    return `${award.days_remaining}d restantes`;
  }
  return "Fluxo contínuo";
}

export function AwardsWorldMap({ awards, heightClass = "h-[480px]", showClosedToggle = false }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const [zoom, setZoom] = useState<number>(2);
  const [showClosedOnMap, setShowClosedOnMap] = useState<boolean>(true);
  const [selectedAward, setSelectedAward] = useState<AwardOpportunity | null>(null);
  const [selectedCountryGroup, setSelectedCountryGroup] = useState<AwardOpportunity[] | null>(null);

  const mappedAwards = useMemo(() => {
    const byKey = new Map<string, AwardOpportunity>();
    for (const a of awards) {
      if (a.latitude === null || a.longitude === null) continue;
      if (!showClosedOnMap && getVisualStatus(a) === "encerrado") continue;
      const key = `${a.title.toLowerCase()}|${(a.city || a.country).toLowerCase()}`;
      const existing = byKey.get(key);
      if (
        !existing ||
        statusPriority(getVisualStatus(a)) > statusPriority(getVisualStatus(existing)) ||
        a.match_score > existing.match_score
      ) {
        byKey.set(key, a);
      }
    }
    return Array.from(byKey.values()).sort((a, b) => {
      const pDiff = statusPriority(getVisualStatus(b)) - statusPriority(getVisualStatus(a));
      return pDiff !== 0 ? pDiff : b.match_score - a.match_score;
    });
  }, [awards, showClosedOnMap]);

  const counts = useMemo(() => {
    let aberto = 0;
    let previsto = 0;
    let encerrado = 0;
    for (const a of awards) {
      const s = getVisualStatus(a);
      if (s === "aberto") aberto++;
      else if (s === "previsto") previsto++;
      else encerrado++;
    }
    return { aberto, previsto, encerrado };
  }, [awards]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: [22, 8],
      zoom: 2,
      minZoom: 2,
      maxZoom: 12,
      worldCopyJump: true,
      scrollWheelZoom: true,
    });

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    const group = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = group;

    const onZoom = () => setZoom(map.getZoom());
    map.on("zoomend", onZoom);

    return () => {
      map.off("zoomend", onZoom);
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const group = layerRef.current;
    if (!map || !group) return;

    group.clearLayers();
    const showCity = zoom >= 5;

    if (!showCity) {
      const byCountry = new Map<string, AwardOpportunity[]>();
      for (const a of mappedAwards) {
        const key = (a.country || a.country_region || "Internacional").trim();
        const list = byCountry.get(key) || [];
        list.push(a);
        byCountry.set(key, list);
      }

      byCountry.forEach((items, countryName) => {
        items.sort((a, b) => {
          const pDiff = statusPriority(getVisualStatus(b)) - statusPriority(getVisualStatus(a));
          return pDiff !== 0 ? pDiff : b.match_score - a.match_score;
        });
        const top = items[0];
        const vStatus = getVisualStatus(top);
        const avgLat = items.reduce((acc, i) => acc + (i.latitude ?? 0), 0) / items.length;
        const avgLng = items.reduce((acc, i) => acc + (i.longitude ?? 0), 0) / items.length;

        const shortTitle = top.title.length > 25 ? `${top.title.slice(0, 24)}…` : top.title;
        const openInCountry = items.filter((i) => getVisualStatus(i) === "aberto").length;

        const palette =
          vStatus === "aberto"
            ? {
                bg: "rgba(255,255,255,0.98)",
                border: "2px solid #059669",
                pillBg: "#d1fae5",
                pillColor: "#065f46",
                titleColor: "#0f172a",
                subColor: "#059669",
                scoreBg: "#059669",
                opacity: "1",
                z: 400,
              }
            : vStatus === "previsto"
            ? {
                bg: "rgba(255,251,235,0.96)",
                border: "2px solid #d97706",
                pillBg: "#fef3c7",
                pillColor: "#92400e",
                titleColor: "#1e293b",
                subColor: "#b45309",
                scoreBg: "#d97706",
                opacity: "0.95",
                z: 250,
              }
            : {
                bg: "rgba(248,250,252,0.88)",
                border: "1.5px dashed #94a3b8",
                pillBg: "#e2e8f0",
                pillColor: "#475569",
                titleColor: "#475569",
                subColor: "#64748b",
                scoreBg: "#64748b",
                opacity: "0.80",
                z: 100,
              };

        const subLine =
          items.length > 1
            ? openInCountry > 0
              ? `${openInCountry} aberto(s) • +${items.length - 1} no país`
              : `${items.length} encerrado(s) • Histórico`
            : formatDeadlinePill(top, vStatus);

        const statusDot = vStatus === "aberto" ? "🟢" : vStatus === "previsto" ? "🟡" : "⚪";

        const html = `
          <div class="award-map-card" style="
            display:inline-flex;
            flex-direction:column;
            gap:2px;
            min-width:148px;
            max-width:195px;
            padding:5px 8px;
            border-radius:10px;
            background:${palette.bg};
            border:${palette.border};
            opacity:${palette.opacity};
            box-shadow:0 4px 12px rgba(15,23,42,0.16);
            font-family:Inter,system-ui,sans-serif;
            cursor:pointer;
            transform:translate(-50%, -100%);
          ">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:5px;">
              <span style="
                font-size:10px;
                font-weight:700;
                color:${palette.pillColor};
                background:${palette.pillBg};
                padding:1px 6px;
                border-radius:999px;
                white-space:nowrap;
                overflow:hidden;
                text-overflow:ellipsis;
                max-width:120px;
              ">${statusDot} ${escapeHtml(countryName)}</span>
              <span style="
                font-size:10px;
                font-weight:800;
                color:#ffffff;
                background:${palette.scoreBg};
                padding:1px 5px;
                border-radius:6px;
              ">${top.match_score}%</span>
            </div>
            <div style="
              font-size:11px;
              font-weight:700;
              color:${palette.titleColor};
              line-height:1.2;
              white-space:nowrap;
              overflow:hidden;
              text-overflow:ellipsis;
            ">${escapeHtml(shortTitle)}</div>
            <div style="font-size:10px;color:${palette.subColor};font-weight:600;">
              ${escapeHtml(subLine)}
            </div>
          </div>
        `;

        const icon = L.divIcon({
          html,
          className: "award-map-pin-wrapper",
          iconSize: [0, 0],
          iconAnchor: [0, 0],
        });

        const marker = L.marker([avgLat, avgLng], { icon, zIndexOffset: palette.z }).addTo(group);
        marker.on("click", () => {
          setSelectedAward(top);
          setSelectedCountryGroup(items.length > 1 ? items : null);
          map.flyTo([avgLat, avgLng], 6, { duration: 0.75 });
        });
      });

      return;
    }

    // Zoom >= 5: individual City + Award cards with clear visual distinction (open vs upcoming vs closed)
    const coordCount = new Map<string, number>();
    mappedAwards.forEach((award) => {
      if (award.latitude === null || award.longitude === null) return;
      const vStatus = getVisualStatus(award);
      const bucketKey = `${award.latitude.toFixed(1)},${award.longitude.toFixed(1)}`;
      const dupIdx = coordCount.get(bucketKey) || 0;
      coordCount.set(bucketKey, dupIdx + 1);

      let lat = award.latitude;
      let lng = award.longitude;
      if (dupIdx > 0) {
        const angle = (dupIdx * 2.2) % (Math.PI * 2);
        const radius = zoom >= 7 ? 0.25 : 0.75;
        lat += Math.sin(angle) * radius;
        lng += Math.cos(angle) * radius * 1.4;
      }

      const isSelected = selectedAward?.id === award.id;
      const cityLabel = award.city ? `${award.city}, ${award.country}` : award.country;
      const shortTitle = award.title.length > 31 ? `${award.title.slice(0, 30)}…` : award.title;

      const palette =
        vStatus === "aberto"
          ? {
              bg: isSelected ? "#ecfdf5" : "rgba(255,255,255,0.98)",
              border: isSelected ? "2.5px solid #047857" : "2px solid #10b981",
              pillBg: "#d1fae5",
              pillColor: "#065f46",
              titleColor: "#0f172a",
              subColor: "#059669",
              scoreBg: "#059669",
              opacity: "1",
              z: 500,
              tag: "ABERTO",
            }
          : vStatus === "previsto"
          ? {
              bg: isSelected ? "#fef3c7" : "rgba(255,251,235,0.96)",
              border: "2px solid #f59e0b",
              pillBg: "#fef3c7",
              pillColor: "#92400e",
              titleColor: "#1e293b",
              subColor: "#b45309",
              scoreBg: "#d97706",
              opacity: "0.95",
              z: 300,
              tag: "PREVISTO",
            }
          : {
              bg: isSelected ? "#f1f5f9" : "rgba(248,250,252,0.88)",
              border: "1.5px dashed #94a3b8",
              pillBg: "#e2e8f0",
              pillColor: "#475569",
              titleColor: "#475569",
              subColor: "#64748b",
              scoreBg: "#64748b",
              opacity: "0.78",
              z: 100,
              tag: "ENCERRADO",
            };

      const html = `
        <div class="award-map-card" style="
          display:inline-flex;
          flex-direction:column;
          gap:2px;
          min-width:168px;
          max-width:225px;
          padding:6px 9px;
          border-radius:10px;
          background:${palette.bg};
          border:${palette.border};
          opacity:${palette.opacity};
          box-shadow:0 4px 14px rgba(15,23,42,0.20);
          font-family:Inter,system-ui,sans-serif;
          cursor:pointer;
          transform:translate(-50%, -100%);
        ">
          <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
            <span style="
              font-size:10px;
              font-weight:700;
              color:${palette.pillColor};
              background:${palette.pillBg};
              padding:1px 6px;
              border-radius:999px;
              white-space:nowrap;
              overflow:hidden;
              text-overflow:ellipsis;
              max-width:145px;
            ">📍 ${escapeHtml(cityLabel)}</span>
            <span style="
              font-size:10px;
              font-weight:800;
              color:#ffffff;
              background:${palette.scoreBg};
              padding:1px 5px;
              border-radius:6px;
            ">${award.match_score}%</span>
          </div>
          <div style="
            font-size:11px;
            font-weight:700;
            color:${palette.titleColor};
            line-height:1.25;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
          ">${escapeHtml(shortTitle)}</div>
          <div style="font-size:10px;color:${palette.subColor};display:flex;justify-content:space-between;gap:6px;font-weight:600;">
            <span>${palette.tag} • ${escapeHtml(formatDeadlinePill(award, vStatus))}</span>
          </div>
        </div>
      `;

      const icon = L.divIcon({
        html,
        className: "award-map-pin-wrapper",
        iconSize: [0, 0],
        iconAnchor: [0, 0],
      });

      const marker = L.marker([lat, lng], { icon, zIndexOffset: palette.z }).addTo(group);
      marker.on("click", () => {
        setSelectedAward(award);
        setSelectedCountryGroup(null);
        map.flyTo([award.latitude!, award.longitude!], Math.max(map.getZoom(), 7), { duration: 0.6 });
      });
    });
  }, [mappedAwards, zoom, selectedAward]);

  const flyToPreset = (center: [number, number], targetZoom: number) => {
    setSelectedCountryGroup(null);
    mapRef.current?.flyTo(center, targetZoom, { duration: 0.7 });
  };

  const showCityMode = zoom >= 5;
  const selectedStatus = selectedAward ? getVisualStatus(selectedAward) : null;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Globe2 className="h-4 w-4 text-indigo-600" />
          <span className="text-sm font-bold text-slate-900">
            Mapa Mundial de Premiações ({mappedAwards.length})
          </span>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
              showCityMode
                ? "bg-emerald-100 text-emerald-800"
                : "bg-indigo-100 text-indigo-800"
            }`}
          >
            {showCityMode ? (
              <>
                <MapPin className="h-3 w-3" /> Zoom {zoom}: Cidades
              </>
            ) : (
              <>
                <ZoomIn className="h-3 w-3" /> Países (dê zoom para Cidades)
              </>
            )}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {REGION_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => flyToPreset(preset.center, preset.zoom)}
              className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Legend Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-white px-4 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          <span className="inline-flex items-center gap-1.5 font-semibold text-emerald-800">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            Abertos ({counts.aberto})
          </span>
          <span className="inline-flex items-center gap-1.5 font-semibold text-amber-800">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            Próximos ciclos ({counts.previsto})
          </span>
          <span className="inline-flex items-center gap-1.5 font-medium text-slate-500">
            <span className="h-2.5 w-2.5 rounded-full border border-dashed border-slate-400 bg-slate-200" />
            Encerrados / Histórico ({counts.encerrado})
          </span>
        </div>

        {showClosedToggle && counts.encerrado > 0 && (
          <label className="inline-flex cursor-pointer items-center gap-1.5 text-xs font-medium text-slate-600">
            <input
              type="checkbox"
              checked={showClosedOnMap}
              onChange={(e) => setShowClosedOnMap(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-slate-300 text-indigo-600"
            />
            Exibir encerrados no mapa
          </label>
        )}
      </div>

      {/* Map Canvas */}
      <div className="relative">
        <div ref={containerRef} className={`w-full ${heightClass} z-0`} />

        {/* Selected Award Floating Detail Card */}
        {selectedAward && selectedStatus && (
          <div
            className={`absolute bottom-4 left-4 right-4 z-[500] max-w-md rounded-2xl border p-4 shadow-2xl backdrop-blur sm:left-auto sm:right-4 ${
              selectedStatus === "aberto"
                ? "border-emerald-300 bg-white/95"
                : selectedStatus === "previsto"
                ? "border-amber-300 bg-amber-50/95"
                : "border-dashed border-slate-300 bg-slate-50/95"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold">
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                      selectedStatus === "aberto"
                        ? "bg-emerald-600 text-white"
                        : selectedStatus === "previsto"
                        ? "bg-amber-500 text-white"
                        : "bg-slate-400 text-white"
                    }`}
                  >
                    {selectedStatus === "aberto"
                      ? "Aberto"
                      : selectedStatus === "previsto"
                      ? "Próximo ciclo"
                      : "Encerrado"}
                  </span>
                  <span className="inline-flex items-center gap-1 text-slate-700">
                    <MapPin className="h-3 w-3 shrink-0" />
                    {selectedAward.city ? `${selectedAward.city}, ${selectedAward.country}` : selectedAward.country}
                  </span>
                </div>
                <h4 className="mt-1 text-sm font-bold text-slate-900">{selectedAward.title}</h4>
                <p className="text-xs text-slate-500">{selectedAward.organizer}</p>
              </div>
              <div className="flex items-center gap-1.5">
                <MatchScoreBadge score={selectedAward.match_score} />
                <button
                  type="button"
                  onClick={() => {
                    setSelectedAward(null);
                    setSelectedCountryGroup(null);
                  }}
                  className="rounded-lg px-2 py-1 text-xs font-bold text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                >
                  ✕
                </button>
              </div>
            </div>

            {selectedAward.deadline_source_note && (
              <p className="mt-2 text-[11px] text-slate-600 line-clamp-2">
                {selectedAward.deadline_source_note}
              </p>
            )}

            {selectedCountryGroup && selectedCountryGroup.length > 1 && (
              <div className="mt-2.5 space-y-1 border-t border-slate-200/70 pt-2">
                <div className="text-[10px] font-bold uppercase text-slate-400">
                  Premiações em {selectedAward.country}:
                </div>
                <div className="flex flex-wrap gap-1">
                  {selectedCountryGroup.map((item) => {
                    const st = getVisualStatus(item);
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => {
                          setSelectedAward(item);
                          if (item.latitude !== null && item.longitude !== null) {
                            mapRef.current?.flyTo([item.latitude, item.longitude], 7, { duration: 0.6 });
                          }
                        }}
                        className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition ${
                          item.id === selectedAward.id
                            ? "bg-indigo-600 text-white"
                            : st === "aberto"
                            ? "bg-emerald-100 text-emerald-900 hover:bg-emerald-200"
                            : "bg-slate-200/70 text-slate-600 hover:bg-slate-200"
                        }`}
                      >
                        {st === "aberto" ? "🟢 " : st === "previsto" ? "🟡 " : "⚪ "}
                        {item.city ? `${item.city}: ` : ""}
                        {item.title.length > 22 ? `${item.title.slice(0, 21)}…` : item.title}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200/70 pt-2.5 text-xs">
              <span className="inline-flex items-center gap-1 font-semibold text-slate-700">
                <Calendar className="h-3.5 w-3.5 text-indigo-600" />
                {selectedStatus === "aberto" && selectedAward.days_remaining !== null
                  ? `Faltam ${selectedAward.days_remaining} dias (${selectedAward.deadline_date})`
                  : selectedAward.deadline}
              </span>

              <a
                href={
                  normalizeExternalUrl(selectedAward.official_url) ||
                  buildFallbackSearchUrl(`${selectedAward.title} ${selectedAward.organizer}`)
                }
                target="_blank"
                rel="noreferrer"
                className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 font-semibold text-white ${
                  selectedStatus === "aberto"
                    ? "bg-emerald-600 hover:bg-emerald-700"
                    : "bg-slate-600 hover:bg-slate-700"
                }`}
              >
                {selectedStatus === "aberto" ? "Inscrever / Edital" : "Ver página oficial"}{" "}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
