from app.utils.format import (
    format_mcq_to_json_and_print,
    get_dynamic_exclusion_list,
    is_duplicate,
    normalize_key,
    normalize_sector,
)
from app.core.config import CONFIG


def _is_template_doc(doc) -> bool:
    meta = getattr(doc, "metadata", None) or {}
    return _is_template_meta(meta)


def _is_template_meta(meta: dict) -> bool:
    if not meta:
        return False
    if meta.get("origin") == "template":
        return True
    source_type = str(meta.get("source_type") or "")
    if source_type.startswith("template_"):
        return True
    full_path = str(meta.get("full_path") or "")
    return full_path.startswith("db://template_survey")


def _meta_filter_for_origin(origin: str):
    """FAISS metadata filter so docs don't crowd out templates in top-k."""
    if origin == "templates":
        return _is_template_meta
    if origin == "docs":
        return lambda meta: not _is_template_meta(meta)
    return None


def _search_with_filter(db, query, k, meta_filter):
    kwargs = {"k": k}
    if meta_filter is not None:
        # CRITICAL: default fetch_k=20 — must over-fetch before metadata filter
        kwargs["fetch_k"] = min(max(k * 10, 5000), 20000)
        try:
            return db.similarity_search_with_score(query, filter=meta_filter, **kwargs)
        except TypeError:
            return db.similarity_search_with_score(query, k=min(k * 5, 8000))
    return db.similarity_search_with_score(query, **kwargs)


def _passes_filters(
    doc,
    score,
    *,
    origin,
    norm_input,
    norm_survey_type,
    current_exclusions,
    seen_content,
    relevance_threshold,
):
    if score > relevance_threshold:
        return False

    is_tpl = _is_template_doc(doc)
    if origin == "templates" and not is_tpl:
        return False
    if origin == "docs" and is_tpl:
        return False

    doc_sector = normalize_key(doc.metadata.get("sector", "general"))
    if doc_sector != "general" and doc_sector != norm_input:
        return False

    # survey_type applies to word docs only; templates use survey_type="template"
    if norm_survey_type and not is_tpl:
        doc_survey_type = normalize_key(doc.metadata.get("survey_type", ""))
        if doc_survey_type != norm_survey_type:
            return False

    if is_duplicate(doc.page_content, seen_content):
        return False

    content_upper = doc.page_content.upper()
    if any(exc.upper() in content_upper for exc in current_exclusions):
        return False

    return True


def _format_question(counter, doc, target_langs):
    question_data = format_mcq_to_json_and_print(counter, doc.page_content, target_langs)
    meta = doc.metadata or {}
    is_tpl = _is_template_doc(doc)
    meta_qtype = meta.get("qtype")
    if is_tpl and meta_qtype:
        question_data["qtype"] = meta_qtype

    if is_tpl:
        question_data["source"] = "template"
        if meta.get("template_id") is not None:
            question_data["template_id"] = str(meta.get("template_id"))
        if meta.get("full_path"):
            question_data["full_path"] = meta.get("full_path")
        if meta.get("template_title"):
            question_data["template_title"] = meta.get("template_title")
    else:
        question_data["source"] = "doc"
        if meta.get("full_path"):
            question_data["full_path"] = meta.get("full_path")
        if meta.get("source_type"):
            question_data["source_type"] = meta.get("source_type")
    return question_data


def generate_robust_survey(
    db,
    sector_input,
    reference,
    total_questions,
    target_langs,
    description=None,
    survey_type=None,
    origin=None,
):
    """
    origin:
      - "templates" → only questions from template_survey (FAISS)
      - "docs"      → only wordfile questions
      - None/"all"  → both (templates + docs searched separately so docs don't flood top-k)

    Each question in Data includes:
      - source: "template" | "doc"
      - template_id / full_path when source is template
    """
    sector_input = normalize_sector(sector_input)
    search_desc = description if description else ""
    current_exclusions = get_dynamic_exclusion_list(sector_input, search_desc)
    type_hint = f"{survey_type} " if survey_type else ""
    origin = (origin or "all").lower().strip()
    if origin not in ("templates", "docs", "all"):
        origin = "all"

    query_basic = f"{type_hint}{sector_input} basic demographics profile"
    query_complex = f"{type_hint}{reference} {sector_input} {search_desc} details check"

    n = max(int(total_questions or 0), 1)

    # Fetch sizes: over-fetch for filtered paths; for "all" always use high k + dual search
    if origin in ("templates", "all"):
        k_basic = min(max(n, CONFIG["fetch_limit_basic"], 200), 2000)
        k_complex = min(max(n * 3, CONFIG["fetch_limit_complex"], 1500), 8000)
    else:
        k_basic = min(
            max(CONFIG["fetch_limit_basic"], n // 2),
            CONFIG.get("fetch_limit_basic_max", 200),
        )
        k_complex = min(
            max(CONFIG["fetch_limit_complex"], n * 2),
            CONFIG.get("fetch_limit_complex_max", 2000),
        )

    # For origin=all: search each source alone so docs cannot crowd templates out of top-k
    if origin == "all":
        result_streams = [
            (
                "templates",
                _search_with_filter(db, query_basic, k_basic, _is_template_meta)
                + _search_with_filter(db, query_complex, k_complex, _is_template_meta),
            ),
            (
                "docs",
                _search_with_filter(
                    db, query_basic, k_basic, lambda m: not _is_template_meta(m)
                )
                + _search_with_filter(
                    db, query_complex, k_complex, lambda m: not _is_template_meta(m)
                ),
            ),
        ]
    else:
        meta_filter = _meta_filter_for_origin(origin)
        result_streams = [
            (
                origin,
                _search_with_filter(db, query_basic, k_basic, meta_filter)
                + _search_with_filter(db, query_complex, k_complex, meta_filter),
            )
        ]

    final_data_list = []
    seen_content = []
    norm_input = normalize_key(sector_input)
    norm_survey_type = (
        normalize_key(survey_type) if survey_type and origin != "templates" else None
    )
    global_counter = 1
    RELEVANCE_THRESHOLD = 1.50

    def _take_from_stream(hits, quota):
        """Pick up to `quota` unique questions from scored hits."""
        nonlocal global_counter
        taken = 0
        for doc, score in hits:
            if global_counter > n or taken >= quota:
                break
            if not _passes_filters(
                doc,
                score,
                origin=origin if origin != "all" else (
                    "templates" if _is_template_doc(doc) else "docs"
                ),
                norm_input=norm_input,
                norm_survey_type=norm_survey_type,
                current_exclusions=current_exclusions,
                seen_content=seen_content,
                relevance_threshold=RELEVANCE_THRESHOLD,
            ):
                continue
            final_data_list.append(
                _format_question(global_counter, doc, target_langs)
            )
            seen_content.append(doc.page_content)
            global_counter += 1
            taken += 1
        return taken

    if origin == "all":
        # Prefer ~half templates, ~half docs; then fill remainder from either stream
        n_tpl = (n + 1) // 2
        n_doc = n - n_tpl
        for stream_name, hits in result_streams:
            quota = n_tpl if stream_name == "templates" else n_doc
            _take_from_stream(hits, quota)
        # Fill remaining from all streams (templates first, then docs)
        if global_counter <= n:
            for _stream_name, hits in result_streams:
                if global_counter > n:
                    break
                _take_from_stream(hits, n)
    else:
        for _stream_name, hits in result_streams:
            _take_from_stream(hits, n)

    return {
        "Section": sector_input,
        "Data": final_data_list,
    }
