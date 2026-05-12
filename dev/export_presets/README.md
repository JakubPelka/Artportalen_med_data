# Export presets

Ten folder zawiera zewnętrzne presety eksportu dla tej konkretnej wersji skryptu.

- Dla DEV: `dev/export_presets/`
- Dla PROD: `prod/export_presets/`

Presety są plikami JSON i są widoczne w UI. Skrypt ma też presety wbudowane w kodzie, więc folder może być pusty, ale lokalne presety pozwalają łatwo dostosować kolumny i filtry bez edycji kodu.

## Ważne

Preset steruje głównie kolumnami w:

- `*_with_data.xlsx`
- `*_bara_skyddade.xlsx`

Osobny plik:

- `*_frammande_invasiva.xlsx`

jest generowany automatycznie i korzysta z profilu `frammande_invasiva`.

## Edycja z UI

W oknie wyboru presetu dostępne są opcje:

- `Podgląd presetu`
- `Edytuj i zapisz JSON`
- `Zapisz kopię jako JSON`

Opcja `Edytuj i zapisz JSON` pozwala zaznaczać kolumny i filtry checkboxami. Nie zmienia istniejącego pliku, tylko zapisuje nowy preset JSON w tym folderze.

## Przykładowe filtry

```json
"filter": {
  "include_current_protection_filter": true,
  "include_redlist_filter": true,
  "redlist_categories": ["RE", "CR", "EN", "VU", "NT"],
  "include_ias_union_eu_filter": false
}
```

## Nowe kolumny TLS

Wersja ta obsługuje dodatkowo m.in.:

- `FågeldirektivetBilaga2`
- `SkogsstyrelsensNaturvardsarter`
- `Habitatdirektivet2023`
- `FrammandeArter`
- `FrammandeArterISverige`
- `RisklistaFrammandeArter`
- `Risklista_SE`
- `Risklista_HI`
- `Risklista_PH`
- `Risklista_LO`
- `Risklista_NK`

`DirectiveAppendix2` jest teraz zawężone do Habitatdirektivets bilaga 2 i nie powinno łapać Fågeldirektivet bilaga 2.
