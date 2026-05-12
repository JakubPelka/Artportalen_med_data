# Export presets

Ten folder znajduje się **wewnątrz `dev/` albo `prod/`**, nie w root repozytorium.

Skrypt automatycznie czyta pliki:

```text
export_presets/*.json
```

z folderu tej wersji, która jest uruchamiana:

```text
dev/export_presets/   # gdy uruchamiasz dev/start.py
prod/export_presets/  # gdy uruchamiasz prod/start.py
```

Preset może sterować:

- kolumnami w `*_with_data.xlsx`,
- kolumnami w `*_bara_skyddade.xlsx`,
- filtrem `*_bara_skyddade.xlsx`.

Najważniejsze pola JSON:

```json
{
  "preset_id": "moja_nazwa",
  "label": "Moja nazwa widoczna w UI",
  "description": "Opis presetu",
  "include_all_columns": false,
  "include_original_columns": true,
  "original_column_candidates": [],
  "enrichment_columns": ["TaxonId", "ScientificName", "SwedishName", "RedListCategory"],
  "filter": {
    "include_current_protection_filter": true,
    "include_redlist_filter": true,
    "redlist_categories": ["RE", "CR", "EN", "VU", "NT"],
    "include_ias_union_eu_filter": false
  }
}
```

Jeśli chcesz stworzyć własny preset, najprościej skopiować jeden z istniejących plików JSON i zmienić `preset_id`, `label`, `description`, listę kolumn oraz filtr.
