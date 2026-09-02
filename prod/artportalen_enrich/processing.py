# -*- coding: utf-8 -*-
"""Pobieranie danych gatunkowych i budowanie tabel wynikowych."""

import time
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests

from .config import HEADERS_SPECIES, SPECIES_SLEEP, SPECIES_URL, TIMEOUT, RL_ORDER
from .logger_utils import add_debug_row, is_debug, log
from .species_helpers import (
    any_child_named,
    is_minskande_fagel,
    join_name_with_attr,
    join_typical_species,
    select_current_or_latest_redlist,
)
from .tls_client import tls_flags_by_membership, tls_is_ready
from .utils import bool_to_ja, is_empty_value, json_safe

DATA_COLUMNS = [
    "ScientificName",
    "SwedishName",
    "DisplayName",
    "Category",
    "ConservationStatus",
    "RedListCategory",
    "RedListCriterion",
    "RedListPeriodName",
    "RedListCriterionText",
    "ActionProgramName",
    "ActionProgramStatus",
    "ActionProgramStart",
    "ActionProgramEnd",
    "ForestrySignal",
    "ForestrySignalSpecies",
    "TypicalSpecies",
    "LandscapeType",
    "Biotopes",
    "CITES",
    "Bernkonventionen",
    "Bonnkonventionen",
    "PrioriteradeFågelarterSkogsvårdslagen",
    "FågeldirektivetBilaga1",
    "minskande_faglar",
    "Fridlyst",
    "Frid_text",
    "ProtectedByWorkProtectionConstitution",
    "ProtectedBirds",
    "DirectiveAppendix2",
    "DirectiveAppendix2Priority",
    "DirectiveAppendix4",
    "DirectiveAppendix5",
    "Artikel 17 - 2019",
    "Characteristic",
    "SpreadAndStatus",
    "Ecology",
    "Threat",
    "ConservationMeasures",
    "Other",
    "SwedishPresence",
    "ImmigrationHistory",
    "SubstrateInformation",
    "EcologicalGroups",
    "ConservationEcology",
    "ConservationNatureConservation",
    "ConservationTreeSpecies",
    "AlienSpeciesRiskCategories",
    "AlienSpeciesEnvironments",
    "AlienSpeciesEcologyEffect",
    "AlienSpeciesTaxonLists",
    "AlienSpeciesInvationPotentials",
    "AlienSpeciesRegions",
    "IAS_Union_EU",
]

FLAG_COLUMNS = [
    "CITES",
    "Bernkonventionen",
    "Bonnkonventionen",
    "FågeldirektivetBilaga1",
    "PrioriteradeFågelarterSkogsvårdslagen",
    "minskande_faglar",
    "Fridlyst",
    "DirectiveAppendix2",
    "DirectiveAppendix2Priority",
    "DirectiveAppendix4",
    "ProtectedByWorkProtectionConstitution",
    "DirectiveAppendix5",
    "IAS_Union_EU",
]

PROTECTION_COLUMNS = [
    "ConservationStatus",
    "Artikel 17 - 2019",
    "TypicalSpecies",
    "CITES",
    "Bernkonventionen",
    "Bonnkonventionen",
    "PrioriteradeFågelarterSkogsvårdslagen",
    "FågeldirektivetBilaga1",
    "minskande_faglar",
    "ProtectedByWorkProtectionConstitution",
    "ProtectedBirds",
    "DirectiveAppendix2",
    "DirectiveAppendix2Priority",
    "DirectiveAppendix4",
    "DirectiveAppendix5",
    "ForestrySignal",
    "ActionProgramStatus",
    "ActionProgramStart",
    "ActionProgramEnd",
    "ActionProgramName",
    "Fridlyst",
]

# Standard-rödlistning som ska ingå i _bara_skyddade / prioriterade arter.
# "Od NT w górę" to RE, CR, EN, VU, NT. LC, NA, NE och DD filtreras bort
# om de inte samtidigt har annan skydds-/naturvårdsflagga.
DEFAULT_REDLIST_PROTECTION_CATEGORIES = {"RE", "CR", "EN", "VU", "NT"}


def has_list_flag(lists: Any, list_name: str) -> str:
    ln = (list_name or "").strip().lower()
    for it in (lists or []):
        if not isinstance(it, dict):
            continue
        nm = str(it.get("name", "")).strip().lower()
        title = str(it.get("title", "")).strip().lower()
        if ln and (ln == nm or ln in nm or ln in title):
            return "Ja"
        if any_child_named([it], list_name) == "Ja":
            return "Ja"
    return ""


def _new_record() -> Dict[str, Any]:
    return {c: "" for c in DATA_COLUMNS}


def fetch_species_record(tid: int, index: int, total: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Hämtar och tolkar SpeciesDataService för ett TaxonId."""
    record = _new_record()
    dbg: Dict[str, Any] = {"TaxonId": tid}

    try:
        resp = requests.get(
            f"{SPECIES_URL}?taxa={tid}&culture=sv-SE",
            headers=HEADERS_SPECIES,
            timeout=TIMEOUT,
        )
        data = json_safe(resp) if resp and resp.status_code == 200 else []
        item = (data[0] if isinstance(data, list) and data else data) or {}
        obj = item.get("speciesData", item) or {}

        def gv(*keys: str, default: Any = "") -> Any:
            o: Any = obj
            for ky in keys:
                if isinstance(o, dict):
                    o = o.get(ky)
                else:
                    o = None
            return o if (o is not None and o != "") else default

        record["ScientificName"] = obj.get("scientificName") or item.get("scientificName") or ""
        record["SwedishName"] = gv("swedishName")
        record["DisplayName"] = gv("displayName")
        record["Category"] = gv("category", "name")
        record["ConservationStatus"] = gv("conservationStatus")

        redlist_info = obj.get("redlistInfo", []) or []
        red = select_current_or_latest_redlist(redlist_info)

        record["RedListCategory"] = (red or {}).get("category", "")
        record["RedListCriterion"] = (red or {}).get("criterion", "")
        record["RedListPeriodName"] = ((red or {}).get("period") or {}).get("name", "")
        record["RedListCriterionText"] = (red or {}).get("criterionText", "")

        tls_flags = tls_flags_by_membership(tid) if tls_is_ready() else {}

        nc = obj.get("natureConservation", {}) or {}
        act = nc.get("actionProgram", {}) or {}
        record["ActionProgramName"] = act.get("program", "")
        record["ActionProgramStatus"] = act.get("status", "")
        record["ActionProgramStart"] = act.get("startYear", "")
        record["ActionProgramEnd"] = act.get("endYear", "")

        record["ForestrySignal"] = ((nc.get("forestryBoardSignalSpecies", {}) or {}).get("apply")) or ""
        fs_names = []
        fss = nc.get("forestryBoardSignalSpecies") or {}

        def _add_names(val: Any) -> None:
            if isinstance(val, list):
                for el in val:
                    if isinstance(el, dict):
                        nm = (
                            el.get("name")
                            or el.get("swedishName")
                            or el.get("displayName")
                            or el.get("scientificName")
                        )
                        if nm:
                            fs_names.append(str(nm))
                    elif isinstance(el, str) and el.strip():
                        fs_names.append(el.strip())
            elif isinstance(val, dict):
                nm = (
                    val.get("name")
                    or val.get("swedishName")
                    or val.get("displayName")
                    or val.get("scientificName")
                )
                if nm:
                    fs_names.append(str(nm))
            elif isinstance(val, str) and val.strip():
                fs_names.append(val.strip())

        if isinstance(fss, dict):
            for key in ("speciesNames", "species", "names", "speciesList", "items"):
                _add_names(fss.get(key))
        elif isinstance(fss, list):
            _add_names(fss)

        record["ForestrySignalSpecies"] = "; ".join(sorted(set(n for n in fs_names if n)))
        record["TypicalSpecies"] = join_typical_species(nc.get("typicalSpecies", []))
        record["LandscapeType"] = join_name_with_attr(obj.get("landscapeTypes", []), "name", "status")
        record["Biotopes"] = join_name_with_attr(obj.get("biotopes", []), "name", "significance")

        lists = nc.get("lists", []) or []
        fb_cites = has_list_flag(lists, "CITES")
        fb_bern = has_list_flag(lists, "Bernkonventionen")
        fb_bonn = has_list_flag(lists, "Bonnkonventionen")
        fb_prio = has_list_flag(lists, "Prioriterade fågelarter i skogsvårdslagen")
        fb_fd1 = has_list_flag(lists, "Fågeldirektivet bilaga 1")

        record["CITES"] = tls_flags.get("CITES") or fb_cites
        record["Bernkonventionen"] = tls_flags.get("Bernkonventionen") or fb_bern
        record["Bonnkonventionen"] = tls_flags.get("Bonnkonventionen") or fb_bonn
        record["PrioriteradeFågelarterSkogsvårdslagen"] = (
            tls_flags.get("PrioriteradeFågelarterSkogsvårdslagen") or fb_prio
        )
        record["FågeldirektivetBilaga1"] = tls_flags.get("FågeldirektivetBilaga1") or fb_fd1
        record["minskande_faglar"] = (
            "Ja"
            if is_minskande_fagel(
                record.get("SwedishName", ""),
                record.get("ScientificName", ""),
                tid,
            )
            else ""
        )

        prot_txt = (obj.get("protectedText") or "").strip()
        frid_flag = (
            tls_flags.get("Fridlyst")
            or has_list_flag(lists, "Fridlysta arter")
            or has_list_flag(lists, "Fridlysta fåglar")
        )
        if not frid_flag and prot_txt and ("fridlyst" in prot_txt.lower()):
            frid_flag = "Ja"

        record["Fridlyst"] = frid_flag or ""
        record["Frid_text"] = prot_txt or ""

        sd_hd2 = bool_to_ja(nc.get("habitatDirectiveAppendix2") or nc.get("habitatdirectiveappendix2"))
        sd_hd2p = bool_to_ja(
            nc.get("habitatDirectiveAppendix2PrioritizedSpecie")
            or nc.get("habitatDirectiveAppendix2PrioritizedSpecies")
            or nc.get("habitatdirectiveappendix2prioritizedspecie")
            or nc.get("habitatdirectiveappendix2prioritizedspecies")
        )
        sd_hd4 = bool_to_ja(nc.get("habitatDirectiveAppendix4") or nc.get("habitatdirectiveappendix4"))
        sd_hd5 = bool_to_ja(nc.get("habitatDirectiveAppendix5") or nc.get("habitatdirectiveappendix5"))

        record["DirectiveAppendix2"] = tls_flags.get("DirectiveAppendix2") or sd_hd2
        record["DirectiveAppendix2Priority"] = tls_flags.get("DirectiveAppendix2Priority") or sd_hd2p
        record["DirectiveAppendix4"] = tls_flags.get("DirectiveAppendix4") or sd_hd4
        record["DirectiveAppendix5"] = tls_flags.get("DirectiveAppendix5") or sd_hd5
        record["ProtectedByWorkProtectionConstitution"] = nc.get("protectedByWorkProtectionConstitution", "") or ""
        record["ProtectedBirds"] = nc.get("protectedBirds", "") or ""

        art17 = ""
        ca = obj.get("conservationAssessments", {}) or {}
        for p in (ca.get("periods") or []):
            if "2019" in str(p.get("name", "")):
                chunks = []
                for t in (p.get("trends", []) or []):
                    cat = t.get("category", "")
                    ev = t.get("evaluation", "")
                    tr = t.get("trend", "")
                    part = f"{cat}: {ev}{' (' + tr + ')' if tr else ''}"
                    if part.strip():
                        chunks.append(part)
                art17 = ", ".join(chunks)
                break
        record["Artikel 17 - 2019"] = art17

        sft = obj.get("speciesFactText", {}) or {}
        record["Characteristic"] = sft.get("characteristic", "") or ""
        record["SpreadAndStatus"] = sft.get("spreadAndStatus", "") or ""
        record["Ecology"] = sft.get("ecology", "") or ""
        record["Threat"] = sft.get("threat", "") or ""
        record["ConservationMeasures"] = sft.get("conservationMeasures", "") or ""
        record["Other"] = sft.get("other", "") or ""

        tri = obj.get("taxonRelatedInformation", {}) or {}
        record["SwedishPresence"] = tri.get("swedishPresence", "") or ""
        record["ImmigrationHistory"] = tri.get("immigrationHistory", "") or ""

        sub = obj.get("substrateInformation", []) or []
        record["SubstrateInformation"] = join_name_with_attr(sub, "name", sub="use")

        eco = obj.get("ecologicalGroups", []) or []
        eg = ", ".join(sorted(set(g.get("name", "") for g in eco if g.get("active"))))
        record["EcologicalGroups"] = eg

        ca2 = obj.get("conservationAssessments", {}) or {}
        record["ConservationEcology"] = ca2.get("ecology") or ""
        record["ConservationNatureConservation"] = ca2.get("natureConservation") or ""
        record["ConservationTreeSpecies"] = ca2.get("treeSpecies") or ""

        alien = obj.get("alienSpeciesRa", {}) or {}
        record["AlienSpeciesRiskCategories"] = "; ".join(alien.get("riskCategories", []) or [])
        record["AlienSpeciesEnvironments"] = "; ".join(alien.get("environments", []) or [])
        record["AlienSpeciesEcologyEffect"] = "; ".join(alien.get("ecologyEffect", []) or [])
        record["AlienSpeciesTaxonLists"] = "; ".join(str(x) for x in (alien.get("taxonLists", []) or []))
        record["AlienSpeciesInvationPotentials"] = "; ".join(alien.get("invationPotentials", []) or [])
        record["AlienSpeciesRegions"] = "; ".join(alien.get("regions", []) or [])

        record["IAS_Union_EU"] = tls_flags.get("IAS_Union_EU", "")

        if is_debug():
            dbg.update({
                "SwedishName": record["SwedishName"],
                "ScientificName": record["ScientificName"],
                "TLS_CITES": record["CITES"],
                "TLS_Bern": record["Bernkonventionen"],
                "TLS_Bonn": record["Bonnkonventionen"],
                "TLS_FD1": record["FågeldirektivetBilaga1"],
                "TLS_Prio": record["PrioriteradeFågelarterSkogsvårdslagen"],
                "TLS_Fridlyst": record["Fridlyst"],
                "TLS_HD2": record["DirectiveAppendix2"],
                "TLS_HD2P": record["DirectiveAppendix2Priority"],
                "TLS_HD4": record["DirectiveAppendix4"],
                "TLS_HD5": record["DirectiveAppendix5"],
                "TLS_IAS_Union_EU": record["IAS_Union_EU"],
            })

        if (index % 10) == 0:
            log(f"→ {index}/{total} taksonów ukończono")

    except Exception as e:
        log(f"Błąd dla TaxonId {tid}: {e}")
        dbg["Error"] = str(e)

    return record, dbg


def build_enrichment_table(uniq_ids: List[int]) -> pd.DataFrame:
    store = {c: [] for c in DATA_COLUMNS}
    id_bucket = []

    for k, tid in enumerate(uniq_ids, start=1):
        log(f"— {k}/{len(uniq_ids)} — TaxonId={tid}")
        record, dbg = fetch_species_record(tid, k, len(uniq_ids))

        id_bucket.append(tid)
        for c in DATA_COLUMNS:
            store[c].append(record.get(c, ""))

        if is_debug():
            add_debug_row(dbg)

        time.sleep(SPECIES_SLEEP)

    result = pd.DataFrame({"TaxonId": id_bucket}) if id_bucket else pd.DataFrame(columns=["TaxonId"])
    for c in DATA_COLUMNS:
        result[c] = store.get(c, [])

    result.replace(["N/A", "0", 0, None], "", inplace=True)
    return result


def sort_by_redlist(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    redlist = out["RedListCategory"] if "RedListCategory" in out.columns else pd.Series([""] * len(out), index=out.index)
    out["_rl_order"] = redlist.astype(str).str.upper().map(RL_ORDER).fillna(99).astype(int)

    for col in ("SwedishName", "ScientificName"):
        if col not in out.columns:
            out[col] = ""

    out = out.sort_values(["_rl_order", "SwedishName", "ScientificName"], ascending=[True, True, True])
    out.drop(columns=["_rl_order"], inplace=True)
    return out


def clean_flag_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in FLAG_COLUMNS:
        if c in out.columns:
            out[c] = out[c].astype(str).replace({"Nej": "", "nej": "", "False": "", "false": ""})
    return out


def has_redlist_protection(row: pd.Series, redlist_categories: set[str] | None = None) -> bool:
    """Returnerar True om RedListCategory finns i valt kategoriurval."""
    if "RedListCategory" not in row.index:
        return False
    categories = redlist_categories or DEFAULT_REDLIST_PROTECTION_CATEGORIES
    category = str(row.get("RedListCategory") or "").strip().upper()
    return category in categories


def has_current_protection_flag(row: pd.Series) -> bool:
    """Returnerar True om någon av de etablerade skydds-/naturvårdsflaggorna är ifylld."""
    for col in PROTECTION_COLUMNS:
        if col in row.index and not is_empty_value(row.get(col)):
            return True
    return False


def has_ias_union_eu_flag(row: pd.Series) -> bool:
    """Returnerar True om IAS_Union_EU är ifylld."""
    if "IAS_Union_EU" not in row.index:
        return False
    return not is_empty_value(row.get("IAS_Union_EU"))


def has_protection(row: pd.Series, preset: object | None = None) -> bool:
    """Filter för *_bara_skyddade.xlsx.

    Default: nuvarande skydds-/naturvårdsflaggor + rödlistning RE/CR/EN/VU/NT.
    Om preset innehåller filterinställningar används dessa.
    """
    include_current = getattr(preset, "include_current_protection_filter", True)
    include_redlist = getattr(preset, "include_redlist_filter", True)
    include_ias = getattr(preset, "include_ias_union_eu_filter", False)
    redlist_categories = {
        str(x).strip().upper()
        for x in getattr(preset, "redlist_categories", DEFAULT_REDLIST_PROTECTION_CATEGORIES)
        if str(x).strip()
    }

    if include_current and has_current_protection_flag(row):
        return True
    if include_redlist and has_redlist_protection(row, redlist_categories):
        return True
    if include_ias and has_ias_union_eu_flag(row):
        return True
    return False


def make_full_enriched(df: pd.DataFrame, result: pd.DataFrame) -> pd.DataFrame:
    add_cols = [c for c in result.columns if c != "TaxonId" and c not in df.columns]
    merge_cols = ["TaxonId"] + add_cols
    return df.merge(result[merge_cols], on="TaxonId", how="left")


def make_overview(full_enriched: pd.DataFrame) -> pd.DataFrame:
    overview = full_enriched[full_enriched["TaxonId"] > 0].drop_duplicates(subset=["TaxonId"], keep="first").copy()
    overview = sort_by_redlist(overview)
    overview = clean_flag_columns(overview)
    return overview


def make_protected(overview: pd.DataFrame, preset: object | None = None) -> pd.DataFrame:
    protected = overview[overview.apply(lambda r: has_protection(r, preset), axis=1)].copy()
    protected.replace(["N/A", "0", 0, None], "", inplace=True)
    protected = sort_by_redlist(protected)
    return protected


def summarize_debug(overview: pd.DataFrame) -> None:
    def _sum_yes(df_: pd.DataFrame, col: str) -> int:
        if col not in df_.columns:
            return 0
        return int((df_[col].astype(str).str.lower() == "ja").sum())

    for col in FLAG_COLUMNS + ["Fridlyst"]:
        log(f"SUMA '{col}=Ja': {_sum_yes(overview, col)}")
