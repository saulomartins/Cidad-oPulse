from __future__ import annotations

import html
import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse


STOPWORDS_PT_EN = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "para", "com", "sem", "sob", "sobre",
    "entre", "ate", "apos", "ante", "contra", "desde", "que", "qual", "quais", "quem",
    "como", "onde", "quando", "porque", "porquê", "mais", "menos", "muito", "muita",
    "muitos", "muitas", "pouco", "todo", "toda", "todos", "todas", "outro", "outra",
    "este", "esta", "esse", "essa", "isso", "isto", "aquele", "aquela", "ele", "ela",
    "eles", "elas", "nosso", "nossa", "seu", "sua", "seus", "suas", "foi", "ser",
    "sao", "são", "esta", "está", "estao", "estão", "tem", "têm", "ter", "pode",
    "permite", "permitem", "sistema", "sistemas", "plataforma", "portal", "aplicativo",
    "app", "site", "web", "online", "digital", "publico", "público", "publica", "pública",
    "cidadao", "cidadão", "cidadaos", "cidadãos", "atendimento", "servico", "serviço",
    "servicos", "serviços", "governo", "estadual", "municipal", "federal", "nacional",
    "brasil", "novo", "nova", "novos", "novas", "melhor", "maior", "tambem", "também",
    "atraves", "através", "sobre", "apoio", "gestao", "gestão", "dados", "informacoes",
    "informações", "projeto", "iniciativa", "solucao", "solução", "software", "ferramenta",
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "has",
    "have", "not", "but", "can", "all", "one", "out", "use", "using", "http", "https",
    "www", "gov", "org", "com", "net", "br",
}

GENERIC_HOST_PARTS = {
    "gov", "com", "org", "net", "edu", "br", "www", "site", "app", "portal",
    "noticias", "news", "agencia", "prefeitura", "governo", "estado", "mg", "sp", "rj",
}

BRAZIL_STATES: dict[str, dict[str, Any]] = {
    "AC": {"name": "Acre", "demonyms": ["acreano", "acreana"]},
    "AL": {"name": "Alagoas", "demonyms": ["alagoano", "alagoana"]},
    "AP": {"name": "Amapá", "demonyms": ["amapaense"]},
    "AM": {"name": "Amazonas", "demonyms": ["amazonense"]},
    "BA": {"name": "Bahia", "demonyms": ["baiano", "baiana"]},
    "CE": {"name": "Ceará", "demonyms": ["cearense"]},
    "DF": {"name": "Distrito Federal", "demonyms": ["brasiliense"]},
    "ES": {"name": "Espírito Santo", "demonyms": ["capixaba"]},
    "GO": {"name": "Goiás", "demonyms": ["goiano", "goiana"]},
    "MA": {"name": "Maranhão", "demonyms": ["maranhense"]},
    "MT": {"name": "Mato Grosso", "demonyms": ["mato-grossense"]},
    "MS": {"name": "Mato Grosso do Sul", "demonyms": ["sul-mato-grossense"]},
    "MG": {"name": "Minas Gerais", "demonyms": ["mineiro", "mineira"]},
    "PA": {"name": "Pará", "demonyms": ["paraense"]},
    "PB": {"name": "Paraíba", "demonyms": ["paraibano", "paraibana"]},
    "PR": {"name": "Paraná", "demonyms": ["paranaense"]},
    "PE": {"name": "Pernambuco", "demonyms": ["pernambucano", "pernambucana"]},
    "PI": {"name": "Piauí", "demonyms": ["piauiense"]},
    "RJ": {"name": "Rio de Janeiro", "demonyms": ["fluminense", "carioca"]},
    "RN": {"name": "Rio Grande do Norte", "demonyms": ["potiguar", "norte-rio-grandense"]},
    "RS": {"name": "Rio Grande do Sul", "demonyms": ["gaucho", "gaucha", "sul-rio-grandense"]},
    "RO": {"name": "Rondônia", "demonyms": ["rondoniense"]},
    "RR": {"name": "Roraima", "demonyms": ["roraimense"]},
    "SC": {"name": "Santa Catarina", "demonyms": ["catarinense"]},
    "SP": {"name": "São Paulo", "demonyms": ["paulista", "paulistano"]},
    "SE": {"name": "Sergipe", "demonyms": ["sergipano", "sergipana"]},
    "TO": {"name": "Tocantins", "demonyms": ["tocantinense"]},
}


def resolve_state_info(raw_state: str) -> tuple[str, str, list[str]]:
    """Resolve UF or full state name into (UF, full_name, demonyms)."""
    cleaned = (raw_state or "").strip()
    if not cleaned:
        return "", "", []
    upper = cleaned.upper()
    if upper in BRAZIL_STATES:
        info = BRAZIL_STATES[upper]
        return upper, info["name"], info["demonyms"]
    norm = normalize_text(cleaned)
    for uf, info in BRAZIL_STATES.items():
        if normalize_text(info["name"]) == norm:
            return uf, info["name"], info["demonyms"]
    return "", cleaned, []


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str) -> str:
    clean = strip_html(text or "")
    no_accents = unicodedata.normalize("NFKD", clean).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", no_accents.lower()).strip()


def _tokenize_words(text: str) -> list[str]:
    norm = normalize_text(text)
    return re.findall(r"[a-z0-9][a-z0-9+_-]*", norm)


def _contains_phrase(norm_haystack: str, raw_phrase: str) -> bool:
    phrase = normalize_text(raw_phrase).lstrip("#@").strip()
    if not phrase or len(phrase) < 2:
        return False
    # Exact boundary check; handles symbols like "+" in "ded+"
    escaped = re.escape(phrase)
    # If phrase ends with non-alnum (e.g. "ded+"), don't require \b after "+"
    start_bound = r"(?<![a-z0-9])"
    end_bound = r"(?![a-z0-9])" if phrase[-1].isalnum() else r"(?=\s|$|[.,;:!?)])"
    return re.search(start_bound + escaped + end_bound, norm_haystack) is not None


def _split_compound_keyword(raw_kw: str) -> list[str]:
    """Handle cases where user wrote '#Tag @handle' or 'termo #tag' in one keyword entry."""
    parts = re.split(r"\s+(?=[#@])", raw_kw.strip())
    return [p.strip() for p in parts if p.strip()]


def build_system_profile_tokens(system) -> dict[str, Any]:
    """
    Extract structured identity vs context signals from a MonitoredSystem:
    - strong_phrases: distinctive multi-word system names / explicit brand names (e.g. "diario escolar digital", "ded+")
    - short_identity: short or potentially ambiguous aliases (e.g. "ded mais", "ded ia")
    - product_domains: subdomains/hosts specific to the system (e.g. "dedmais.educacao.mg.gov.br")
    - org_domains: broader institutional hosts (e.g. "agenciaminas.mg.gov.br", "prodemge.gov.br")
    - context_tokens: domain/subject tokens from description, citizen_area, org & keywords (e.g. "educacao", "escolar", "professores", "minas", "prodemge", "see")
    """
    try:
        raw_keywords = json.loads(system.keywords_json or "[]")
    except json.JSONDecodeError:
        raw_keywords = []
    try:
        raw_urls = json.loads(system.urls_json or "[]")
    except json.JSONDecodeError:
        raw_urls = []

    expanded_keywords: list[str] = []
    for kw in raw_keywords:
        for piece in _split_compound_keyword(str(kw)):
            if piece and piece not in expanded_keywords:
                expanded_keywords.append(piece)

    # Extract system name parts, e.g. "DED+ (Diário Escolar Digital" -> ["DED+", "Diário Escolar Digital"]
    raw_name = (system.name or "").strip()
    name_parts = [p.strip(" ()[]-") for p in re.split(r"[()–—|]+", raw_name) if p.strip(" ()[]-")]

    strong_phrases: list[str] = []
    short_identity: list[str] = []

    def classify_identity(term: str, is_primary: bool = False):
        clean = term.strip()
        if not clean:
            return
        norm = normalize_text(clean).lstrip("#@").strip()
        if not norm or len(norm) < 3:
            return
        words = norm.split()
        # Symbolic brand names like "DED+" or distinctive 3+ word / long phrases are strong
        has_special_brand = "+" in norm and len(norm) >= 4
        if has_special_brand or len(words) >= 3 or (len(words) == 2 and len(norm) >= 13 and is_primary):
            if clean not in strong_phrases:
                strong_phrases.append(clean)
        elif is_primary or len(norm) >= 4:
            if clean not in short_identity:
                short_identity.append(clean)

    for np in name_parts:
        classify_identity(np, is_primary=True)

    # First few user keywords (non-hashtag or matching name tokens) are identity candidates
    name_tokens = {w for w in _tokenize_words(raw_name) if len(w) >= 3 and w not in STOPWORDS_PT_EN}
    for idx, kw in enumerate(expanded_keywords):
        clean_kw = kw.lstrip("#@").strip()
        norm_kw = normalize_text(clean_kw)
        kw_words = set(_tokenize_words(clean_kw))
        overlaps_name = bool(kw_words & name_tokens)
        if idx < 6 or overlaps_name or "+" in clean_kw:
            classify_identity(clean_kw, is_primary=(idx < 3 or overlaps_name))

    # Classify URLs into product-specific domains vs broader org domains
    product_domains: list[str] = []
    org_domains: list[str] = []
    for raw_url in raw_urls:
        parsed = urlparse(str(raw_url).strip())
        host = (parsed.netloc or parsed.path).replace("www.", "").strip("/").lower()
        if not host or "." not in host:
            continue
        host_words = set(re.split(r"[.-]+", host)) - GENERIC_HOST_PARTS
        first_label = host.split(".")[0]
        matches_identity = bool(host_words & name_tokens) or any(
            normalize_text(p).replace("+", "mais").replace(" ", "") in first_label
            for p in (strong_phrases + short_identity)
            if len(p) >= 4
        )
        if matches_identity:
            if host not in product_domains:
                product_domains.append(host)
        else:
            if host not in org_domains:
                org_domains.append(host)

    # Geographic scope (State UF + full name + Municipality)
    raw_state = getattr(system, "state_uf", "") or ""
    raw_muni = (getattr(system, "municipality", "") or "").strip()
    state_uf, state_name, state_demonyms = resolve_state_info(raw_state)

    geo_terms: list[str] = []
    if raw_muni:
        geo_terms.append(raw_muni)
    if state_name:
        geo_terms.append(state_name)
    if state_uf:
        geo_terms.append(state_uf)

    # Extract rich context tokens from description, citizen_area, organization_type, target_audience, keywords, geo
    context_source = " ".join([
        system.description or "",
        system.citizen_area or "",
        system.organization_type or "",
        system.target_audience or "",
        " ".join(geo_terms),
        " ".join(state_demonyms),
        " ".join(expanded_keywords),
    ])
    token_counts: dict[str, int] = {}
    for tok in _tokenize_words(context_source):
        if len(tok) < 3 or tok in STOPWORDS_PT_EN or tok.isdigit():
            continue
        token_counts[tok] = token_counts.get(tok, 0) + 1

    # Also capture important 2-letter Brazilian state/org acronyms if explicitly present (e.g., "mg", "sp", "rj")
    explicit_acronyms = set(re.findall(r"\b(mg|sp|rj|ba|rs|pr|sc|pe|ce|df|go|rn|es|pa|pb|pi|al|se|ma|mt|ms|ro|rr|ac|ap|to|am|sus|mec|see)\b", normalize_text(context_source)))
    if state_uf:
        explicit_acronyms.add(state_uf.lower())

    # Sort context tokens by frequency so most representative terms come first
    ranked_context = [t for t, _ in sorted(token_counts.items(), key=lambda x: (-x[1], -len(x[0])))]
    context_tokens = list(dict.fromkeys(ranked_context[:45] + sorted(explicit_acronyms)))

    # Pick crisp context anchors for search engine queries (prioritize explicit geo + citizen area!)
    query_anchors: list[str] = []
    if raw_muni:
        query_anchors.append(raw_muni)
    if state_name and state_name not in query_anchors:
        query_anchors.append(state_name)
    if state_uf and state_uf not in query_anchors:
        query_anchors.append(state_uf)

    area_clean = (system.citizen_area or "").strip()
    if area_clean and normalize_text(area_clean) not in STOPWORDS_PT_EN and area_clean not in query_anchors:
        query_anchors.append(area_clean)
    # Detect proper nouns / acronyms from description (e.g. "Minas Gerais", "Prodemge", "SEE/MG")
    desc_raw = system.description or ""
    for proper in re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)?\b", desc_raw):
        norm_p = normalize_text(proper)
        if len(norm_p) >= 4 and norm_p not in STOPWORDS_PT_EN and proper not in query_anchors:
            if not any(norm_p in normalize_text(sp) for sp in strong_phrases):
                query_anchors.append(proper)
        if len(query_anchors) >= 5:
            break
    for tok in ranked_context:
        if len(query_anchors) >= 5:
            break
        if len(tok) >= 5 and not any(tok in normalize_text(a) for a in query_anchors):
            query_anchors.append(tok)

    return {
        "strong_phrases": strong_phrases,
        "short_identity": short_identity,
        "product_domains": product_domains,
        "org_domains": org_domains,
        "context_tokens": context_tokens,
        "query_anchors": query_anchors[:4],
        "geo_terms": geo_terms,
        "state_uf": state_uf,
        "state_name": state_name,
        "state_demonyms": state_demonyms,
        "municipality": raw_muni,
        "all_keywords": expanded_keywords,
    }


def build_contextual_search_queries(system, max_queries: int = 5) -> list[tuple[str, str]]:
    """
    Build high-precision search queries as (query_string, matched_label) pairs.
    Short/ambiguous terms AND state/municipal systems are automatically paired with
    geographic and domain anchors so engines don't return unrelated news from other states.
    """
    profile = build_system_profile_tokens(system)
    anchors = profile["query_anchors"]
    geo_terms = profile.get("geo_terms", [])

    geo_clause = ""
    if geo_terms:
        formatted_geo = [f'"{g}"' if " " in g else g for g in geo_terms[:3]]
        geo_clause = f" ({' OR '.join(formatted_geo)})"

    anchor_clause = ""
    if anchors:
        formatted = [f'"{a}"' if " " in a else a for a in anchors[:3]]
        anchor_clause = f" ({' OR '.join(formatted)})"

    queries: list[tuple[str, str]] = []
    seen_q: set[str] = set()

    def add_query(q: str, label: str):
        key = q.lower().strip()
        if key and key not in seen_q:
            seen_q.add(key)
            queries.append((q, label))

    # 1. Strong phrases (e.g. "Diário Escolar Digital", "DED+") — pair with geo if state/municipality specified!
    for phrase in profile["strong_phrases"][:3]:
        quoted = f'"{phrase}"'
        if geo_clause:
            add_query(f"{quoted}{geo_clause}", phrase)
        elif len(phrase) <= 8 and anchor_clause:
            add_query(f"{quoted}{anchor_clause}", phrase)
        else:
            add_query(quoted, phrase)

    # 2. Short identity aliases (e.g. "DED Mais") ALWAYS anchored to geo/context
    for alias in profile["short_identity"][:2]:
        quoted = f'"{alias}"'
        if anchor_clause:
            add_query(f"{quoted}{anchor_clause}", alias)
        else:
            add_query(quoted, alias)

    # 3. Product-specific domains (e.g. "dedmais.educacao.mg.gov.br")
    for domain in profile["product_domains"][:2]:
        add_query(f'"{domain}"', domain)

    # 4. Institutional domains paired with primary identity (never search a broad news/gov portal bare!)
    primary_terms = (profile["strong_phrases"] + profile["short_identity"])[:2]
    if primary_terms and profile["org_domains"]:
        id_clause = " OR ".join(f'"{t}"' for t in primary_terms)
        for org_dom in profile["org_domains"][:1]:
            add_query(f"site:{org_dom} ({id_clause})", f"{primary_terms[0]} @ {org_dom}")

    return queries[:max_queries]


def _detect_other_brazilian_state(
    raw_text: str,
    norm_text: str,
    norm_url: str,
    target_uf: str,
) -> str | None:
    """If the system belongs to a specific Brazilian state, detect explicit mentions of a DIFFERENT state."""
    if not target_uf or target_uf not in BRAZIL_STATES:
        return None
    raw_lower = strip_html(raw_text).lower()
    for uf, info in BRAZIL_STATES.items():
        if uf == target_uf:
            continue
        if uf == "PA":
            # Avoid matching the Portuguese preposition "para" after accent stripping
            if re.search(r"(?<![a-zà-ÿ])pará(?![a-zà-ÿ])", raw_lower):
                return info["name"]
        else:
            state_name = normalize_text(info["name"])
            if _contains_phrase(norm_text, state_name):
                return info["name"]
        for dem in info["demonyms"]:
            if _contains_phrase(norm_text, dem):
                return info["name"]
        # URL path segment like /rn/noticia/ or .pr.gov.br
        if f"/{uf.lower()}/" in norm_url or f".{uf.lower()}.gov.br" in norm_url:
            return info["name"]
    return None


def evaluate_mention_relevance(
    system,
    title: str,
    content: str,
    url: str = "",
    matched_keyword: str = "",
) -> tuple[bool, float, str]:
    """
    Evaluate whether a collected mention actually refers to the monitored system.
    Returns (is_relevant, relevance_score 0.0..1.0, reason).
    """
    profile = build_system_profile_tokens(system)
    norm_title = normalize_text(title)
    norm_content = normalize_text(content)
    norm_url = (url or "").lower()
    full_text = f"{norm_title} {norm_content}"
    text_tokens = set(_tokenize_words(full_text))

    # 1. Direct product domain match in URL or text -> guaranteed relevant
    for dom in profile["product_domains"]:
        if dom in norm_url or dom in full_text:
            return True, 1.0, f"Domínio oficial do sistema encontrado ({dom})."

    # 2. Check target geographic match (State / Municipality) and out-of-state conflict
    target_uf = profile.get("state_uf", "")
    target_state_name = profile.get("state_name", "")
    target_muni = profile.get("municipality", "")
    target_demonyms = profile.get("state_demonyms", [])

    mentions_target_geo = False
    if target_muni and _contains_phrase(full_text, target_muni):
        mentions_target_geo = True
    if target_state_name and _contains_phrase(full_text, target_state_name):
        mentions_target_geo = True
    if target_uf and (
        _contains_phrase(full_text, target_uf)
        or f".{target_uf.lower()}.gov.br" in norm_url
        or f"/{target_uf.lower()}/" in norm_url
    ):
        mentions_target_geo = True
    if any(_contains_phrase(full_text, d) for d in target_demonyms):
        mentions_target_geo = True

    if target_uf and not mentions_target_geo:
        other_state = _detect_other_brazilian_state(f"{title} {content}", full_text, norm_url, target_uf)
        if other_state:
            return (
                False,
                0.15,
                f"Conteúdo refere-se a outro estado ({other_state}), fora da jurisdição configurada ({target_state_name or target_uf}).",
            )

    # 3. Check strong identity phrase hits (exact boundary match)
    strong_hits = [p for p in profile["strong_phrases"] if _contains_phrase(full_text, p)]
    short_hits = [p for p in profile["short_identity"] if _contains_phrase(full_text, p)]

    # 4. Count domain/context token overlap
    context_set = set(profile["context_tokens"])
    context_hits = sorted(text_tokens & context_set)
    geo_bonus = 0.08 if mentions_target_geo else 0.0

    # Unambiguous multi-word phrase (e.g., "Diário Escolar Digital") in title/content
    long_strong_hits = [p for p in strong_hits if len(normalize_text(p).split()) >= 2 and len(normalize_text(p)) >= 12]
    if long_strong_hits:
        score = min(1.0, 0.85 + geo_bonus + 0.03 * len(context_hits))
        return True, round(score, 2), f"Nome oficial encontrado: {long_strong_hits[0]}."

    # Symbolic short brand name (e.g., "DED+") requires exact match + at least 1 context hit
    if strong_hits and len(context_hits) >= 1:
        score = min(0.98, 0.72 + geo_bonus + 0.05 * len(context_hits))
        return True, round(score, 2), f"Sigla/marca '{strong_hits[0]}' confirmada com contexto ({', '.join(context_hits[:3])})."

    # Short/ambiguous alias (e.g., "DED Mais") requires exact match + at least 2 context hits (or 1 + target geo)
    if short_hits and (len(context_hits) >= 2 or (mentions_target_geo and len(context_hits) >= 1)):
        score = min(0.92, 0.60 + geo_bonus + 0.05 * len(context_hits))
        return True, round(score, 2), f"Termo '{short_hits[0]}' confirmado com contexto ({', '.join(context_hits[:3])})."

    # Special case: explicit matched_keyword found literally + strong context (>= 3 distinct domain tokens)
    if matched_keyword and _contains_phrase(full_text, matched_keyword) and len(context_hits) >= 3:
        score = min(0.85, 0.55 + geo_bonus + 0.04 * len(context_hits))
        return True, round(score, 2), f"Palavra-chave '{matched_keyword}' com forte aderência de contexto ({', '.join(context_hits[:4])})."

    return (
        False,
        round(min(0.35, 0.08 * len(context_hits)), 2),
        "Conteúdo sem correspondência clara com o nome, domínio ou contexto do sistema.",
    )


SPAM_COMMENT_PATTERNS = [
    r"aumente\s+o\s+seu\s+engajamento",
    r"marque\s+\d+\s+amigos",
    r"conhe[cç]a\s+nossos\s+p[ae]rceiros",
    r"publique\s+essa\s+postagem\s+no\s+seu\s+stories",
    r"ganhe\s+seguidores",
    r"renda\s+extra\s+(no\s+link|na\s+bio)",
    r"chama\s+no\s+direct\s+para\s+ganhar",
    r"sigam\s+meu\s+perfil",
]


def is_spam_comment(text: str) -> bool:
    """Detect obvious engagement-bait / bot spam comments on social posts."""
    norm = normalize_text(text)
    if not norm:
        return False
    return any(re.search(pat, norm) for pat in SPAM_COMMENT_PATTERNS)


# Signals that a comment is actually talking about the software/digital tool/service itself
SOFTWARE_OR_TOOL_PATTERNS = [
    r"\b(?:app|aplicativo|sistema|plataforma|portal|site|ferramenta|software|programa|tecnologia)\b",
    r"\b(?:login|senha|acesso|acessar|entrar|cadastro|cadastrar|atualiza[cç][aã]o|vers[aã]o)\b",
    r"\b(?:tela|menu|bot[aã]o|interface|usabilidade|navega[cç][aã]o|suporte|instabilidade)\b",
    r"\b(?:lento|lentid[aã]o|trava|travando|erro|erros|bug|bugs|falha|fora\s+do\s+ar|caiu|n[aã]o\s+funciona|funciona|carrega)\b",
    r"\b(?:intelig[eê]ncia\s+artificial|ia|automati[cz]|digital|papel|online|internet)\b",
    r"\b(?:di[aá]rio|chamada|frequ[eê]ncia|boletim|registro|planejamento|aula|aulas|prova|provas|atividade|atividades)\b",
    r"\b(?:prodemge|extin[cç][aã]o\s+da\s+profiss[aã]o|substituir\s+professor|execu[cç][aã]o\s+do\s+trabalho)\b",
]

# Common off-topic public-sector / political / HR grievances posted on government accounts
# that have nothing to do with the monitored digital system unless the system/tool is also mentioned.
OFF_TOPIC_COMMENT_PATTERNS = [
    r"\bpiso\s+salarial\b",
    r"\bpagamento\s+do\s+piso\b",
    r"\b(?:sal[aá]rio|sal[aá]rios|reajuste\s+salarial|aumento\s+salarial|d[eé]cimo\s+terceiro|13[ºo])\b",
    r"\b(?:aux[ií]lio\s+alimenta[cç][aã]o|vale\s+alimenta[cç][aã]o|vale\s+transporte|ipsemg|atendimento\s+m[eé]dico)\b",
    r"\b(?:saneamento\s+b[aá]sico|asfalto|buraco\s+na\s+rua|merenda|transporte\s+escolar|alunos\s+tea)\b",
    r"\b(?:concurso\s+p[uú]blico|designa[cç][aã]o|convoca[cç][aã]o|contrata[cç][aã]o\s+tempor[aá]ria|f[eé]rias\s+pr[eê]mio|aposentadoria)\b",
    r"\b(?:greve|sindicato|elei[cç][aã]o|elei[cç][oõ]es|governador|deputado|prefeito|vereador|partido)\b",
    r"\b(?:fundo\s+espec[ií]fico|rateio\s+do\s+fundeb|repassar\s+o\s+fundeb|n[aã]o\s+pagar)\b",
]


def evaluate_comment_relevance(system, comment_text: str) -> tuple[bool, str]:
    """
    Filter social-media comments collected under a relevant post so only comments that
    actually evaluate or discuss the monitored system/software are kept.
    Rejects:
      1. Bot/engagement spam.
      2. Pure emojis or ultra-short vague reactions without actionable feedback (e.g. 'Sério ?', 'É pra rir?', '👏👏').
      3. Off-topic political/labor/salary hijacking comments (e.g. 'piso salarial', 'saneamento básico')
         that do NOT mention the system or any software/tool/AI aspect.
    """
    raw = (comment_text or "").strip()
    if is_spam_comment(raw):
        return False, "Comentário identificado como spam/isca de engajamento."

    norm = normalize_text(raw)
    letters_only = re.sub(r"[^a-z]", "", norm)
    words = [w for w in re.findall(r"[a-z0-9+]+", norm) if len(w) >= 2]

    # Reject pure emojis or empty text
    if len(letters_only) < 4:
        return False, "Comentário contém apenas emojis ou texto vazio (sem opinião analisável sobre o sistema)."

    # Check explicit mention of the monitored system (strong phrases / short identity)
    mentions_system = False
    if system is not None:
        profile = build_system_profile_tokens(system)
        id_terms = profile.get("strong_phrases", []) + profile.get("short_identity", [])
        mentions_system = any(_contains_phrase(norm, term) for term in id_terms)
        # Also catch bare acronym like "ded" when the system name starts with "DED+"
        if not mentions_system:
            for term in id_terms:
                base = normalize_text(term).rstrip("+").strip()
                if len(base) >= 3 and re.search(rf"(?<![a-z0-9]){re.escape(base)}(?![a-z0-9])", norm):
                    mentions_system = True
                    break

    mentions_tool = any(re.search(pat, norm) for pat in SOFTWARE_OR_TOOL_PATTERNS)

    # Reject ultra-short ambiguous exclamations (e.g. "Sério ?", "É pra rir?", "Absurdo!") unless they mention the system/tool
    if (len(letters_only) < 12 or len(words) <= 2) and not (mentions_system or mentions_tool):
        return False, "Comentário muito curto/vago sem referência clara ao sistema."

    # Reject off-topic government/salary/HR hijacking comments when they don't mention the system or software/tool
    has_off_topic = any(re.search(pat, norm) for pat in OFF_TOPIC_COMMENT_PATTERNS)
    if has_off_topic and not (mentions_system or mentions_tool):
        return (
            False,
            "Comentário fora de escopo (reclamação geral trabalhista/política/serviço alheio, sem relação direta com o sistema).",
        )

    return True, "OK"


def is_corrupted_search_snippet(title: str, content: str) -> bool:
    """
    Detect search-engine HTML scraping glitches (e.g. DDGS gluing 3-7 different results
    into a single title/snippet attached to the first URL).
    """
    raw_title = (title or "").strip()
    raw_content = (content or "").strip()

    # 1. Multiple platform suffixes glued in title (e.g. "... - Facebook... - Facebook")
    if raw_title.lower().count("facebook") >= 2:
        return True
    if raw_title.lower().count("instagram") >= 2:
        return True

    # 2. Ellipsis or platform word glued directly to the next title without whitespace
    if re.search(r"\.\.\.[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]", raw_title):
        return True
    if re.search(r"(?:Facebook|Instagram|YouTube)[A-ZÁÉÍÓÚÂÊÔÃÕÇ]", raw_title):
        return True
    if re.search(r"\| Facebook.*\| Facebook", raw_title):
        return True

    # 3. Multiple search-result date prefixes glued inside a single snippet body
    en_dates = re.findall(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+20\d{2}\s*[·•-]",
        raw_content,
    )
    if len(en_dates) >= 2:
        return True

    pt_dates = re.findall(
        r"\b\d{1,2}\s+de\s+[a-zçãéíóú]+\.?\s+de\s+20\d{2}\s*[·•-]",
        raw_content.lower(),
    )
    if len(pt_dates) >= 2:
        return True

    return False


def is_specific_social_permalink(url: str, platform: str) -> bool:
    """
    For social networks discovered via web search, require a direct permalink to a
    specific post/video/reel rather than a generic profile or group homepage.
    """
    raw = (url or "").strip()
    if not raw:
        return False
    low = raw.lower()
    parsed = urlparse(low)
    path = (parsed.path or "").strip("/")

    if platform == "facebook":
        if any(
            marker in low
            for marker in (
                "/posts/",
                "/permalink/",
                "/videos/",
                "/reel/",
                "/photo",
                "/watch",
                "story.php",
                "permalink.php",
                "pfbid",
            )
        ):
            return True
        return False

    if platform == "instagram":
        return any(marker in low for marker in ("/p/", "/reel/", "/reels/", "/tv/"))

    if platform == "youtube":
        return "watch?v=" in low or "/shorts/" in low or "youtu.be/" in low

    if platform == "x":
        return "/status/" in low

    return bool(path) or bool(parsed.netloc)


def evaluate_mention_quality(
    source_connector: str,
    platform: str,
    content_type: str,
    title: str,
    content: str,
    url: str,
    system=None,
) -> tuple[bool, str]:
    """
    Verify data provenance & integrity before saving or keeping a mention:
    - Rejects bot/engagement spam comments.
    - Rejects corrupted multi-result search-engine concatenations.
    - Rejects generic non-permalink social pages from web search.
    - Rejects Facebook/Instagram web-search sidebar leaks where the post title/URL is
      actually about a completely different topic.
    """
    if content_type == "comment":
        ok_comment, comment_reason = evaluate_comment_relevance(system, content or title)
        if not ok_comment:
            return False, comment_reason

    if source_connector in {"open_web_social", "gemini_web"}:
        if is_corrupted_search_snippet(title, content):
            return False, "Trecho de buscador corrompido (múltiplos resultados concatenados em um só registro)."

        if platform in {"facebook", "instagram", "youtube", "x"} and not is_specific_social_permalink(url, platform):
            return False, f"Link genérico de perfil/grupo no {platform} (sem URL direta da publicação)."

        # Facebook/Instagram pages often render unrelated recent/sidebar posts in search snippets.
        # Require the monitored system identity to appear in the post TITLE or URL slug itself.
        if platform in {"facebook", "instagram"} and system is not None:
            profile = build_system_profile_tokens(system)
            id_terms = profile.get("strong_phrases", []) + profile.get("short_identity", [])
            title_and_url = normalize_text(f"{title} {url.replace('-', ' ').replace('_', ' ')}")
            has_id_in_title_or_url = any(_contains_phrase(title_and_url, term) for term in id_terms)
            if not has_id_in_title_or_url:
                return (
                    False,
                    f"Trecho de busca no {platform} sem menção ao sistema no título/link (risco de vazamento de barra lateral/outro post).",
                )

    return True, "OK"
