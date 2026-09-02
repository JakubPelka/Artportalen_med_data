# Audyt Pokrycia API SLU Artdatabanken (Issue #5 / Facelift 2026)

**Data audytu:** 2026-09-02  
**Status:** Zakończony (wszystkie sekcje i pola sklasyfikowane)

---

## 1. Cel audytu

Kompleksowy przegląd modeli odpowiedzi usług API SLU Artdatabanken (`SpeciesDataService`, `TaxonService`, `TaxonListService` / TLS) pod kątem pól wykorzystywanych, pomijanych oraz potencjalnie wartościowych dla naturvårdu, GIS i analizy ekologicznej.

Zgodnie z wytycznymi:
* Nowe wartościowe pola trafiają do **pełnego/maksymalnego datasetu** (`DATA_COLUMNS`),
* Istniejące presety (`kungsbacka_standard`, `hotade_arter`, `standard` itp.) **nie są automatycznie modyfikowane**,
* Każde pole ma jednoznaczną klasyfikację: `KEEP`, `ADD`, `SKIP`, `VERIFY`.

---

## 2. Tabela mapowania pól API

| Endpoint / Sekcja JSON | Pole w API | Znaczenie semantyczne | Obecna kolumna | Docelowa kolumna | Decyzja | Uzasadnienie |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Identyfikacja taksonu** | `taxonId` | Identyfikator taksonu w Dyntaxa | `TaxonId` | `TaxonId` | **KEEP** | Klucz główny dopasowania. |
| `SpeciesDataService` | `scientificName` | Pełna nazwa naukowa (łacińska) | `ScientificName` | `ScientificName` | **KEEP** | Podstawowy atrybut taksonomiczny. |
| `SpeciesDataService` | `swedishName` | Oficjalna nazwa szwedzka | `SwedishName` | `SwedishName` | **KEEP** | Podstawowa nazwa użytkowa. |
| `SpeciesDataService` | `displayName` | Nazwa wyświetlana (zwykle szwedzka/naukowa) | `DisplayName` | `DisplayName` | **KEEP** | Używane w podglądzie. |
| `SpeciesDataService` | `author` | Auktor (autor opisu taksonu i rok) | *(brak)* | `Author` | **ADD** | Wartościowe metadane taksonomiczne dla eksportów GIS/raportów. |
| `SpeciesDataService` | `category.name` | Ranga taksonomiczna (np. Art, Underart) | `Category` | `Category` | **KEEP** | Podstawowa klasyfikacja rangi. |
| `SpeciesDataService` | `conservationStatus` | Ogólny status ochrony | `ConservationStatus` | `ConservationStatus` | **KEEP** | Flaga tekstowa statusu. |
| **Rödlistning** | `redlistInfo[].category` | Kategoria czerwonej listy (np. VU, NT, LC) | `RedListCategory` | `RedListCategory` | **KEEP** | Kluczowy wskaźnik zagrożenia (dynamiczny wybór `current`). |
| `redlistInfo[]` | `redlistInfo[].criterion` | Kod kryterium IUCN (np. B2ab(iii)) | `RedListCriterion` | `RedListCriterion` | **KEEP** | Uzasadnienie kategorii. |
| `redlistInfo[]` | `redlistInfo[].period.name` | Nazwa okresu oceny (np. Rödlista 2025) | `RedListPeriodName` | `RedListPeriodName` | **KEEP** | Identyfikacja rocznika czerwonej listy. |
| `redlistInfo[]` | `redlistInfo[].criterionText` | Opis tekstowy spełnionego kryterium | `RedListCriterionText` | `RedListCriterionText` | **KEEP** | Pełny opis kryterium. |
| **Åtgärdsprogram** | `natureConservation.actionProgram.program` | Nazwa programu ochrony gatunkowej | `ActionProgramName` | `ActionProgramName` | **KEEP** | Programy ochrony (ÅGP). |
| `natureConservation` | `actionProgram.status` | Status programu (np. Pågående) | `ActionProgramStatus` | `ActionProgramStatus` | **KEEP** | Status realizacji. |
| `natureConservation` | `actionProgram.startYear` | Rok rozpoczęcia ÅGP | `ActionProgramStart` | `ActionProgramStart` | **KEEP** | Czas trwania. |
| `natureConservation` | `actionProgram.endYear` | Rok zakończenia ÅGP | `ActionProgramEnd` | `ActionProgramEnd` | **KEEP** | Czas trwania. |
| **Skogsstyrelsen** | `forestryBoardSignalSpecies.apply` | Flaga gatunku wskaźnikowego (Signalart) | `ForestrySignal` | `ForestrySignal` | **KEEP** | Gatunki wskaźnikowe leśne. |
| `natureConservation` | `forestryBoardSignalSpecies.speciesNames` | Nazwy gatunków powiązanych | `ForestrySignalSpecies` | `ForestrySignalSpecies` | **KEEP** | Lista powiązań. |
| **Biotopy i krajobraz** | `typicalSpecies` | Gatunki typowe dla siedlisk | `TypicalSpecies` | `TypicalSpecies` | **KEEP** | Gatunek charakterystyczny. |
| `SpeciesDataService` | `landscapeTypes` | Typy krajobrazu i status | `LandscapeType` | `LandscapeType` | **KEEP** | Powiązanie krajobrazowe. |
| `SpeciesDataService` | `biotopes` | Biotopy i ich istotność | `Biotopes` | `Biotopes` | **KEEP** | Siedlisko. |
| `SpeciesDataService` | `substrateInformation` | Informacje o podłożu (substrat/use) | `SubstrateInformation` | `SubstrateInformation` | **KEEP** | Wymagania substratowe. |
| `SpeciesDataService` | `ecologicalGroups` | Grupy ekologiczne | `EcologicalGroups` | `EcologicalGroups` | **KEEP** | Przynależność ekologiczna. |
| **Artfakta teksty** | `speciesFactText.characteristic` | Kännetecken (cechy rozpoznawcze) | `Characteristic` | `Characteristic` | **KEEP** | Opis morfologii. |
| `speciesFactText` | `speciesFactText.spreadAndStatus` | Utbredning och status | `SpreadAndStatus` | `SpreadAndStatus` | **KEEP** | Rozmieszczenie i status. |
| `speciesFactText` | `speciesFactText.ecology` | Ekologi | `Ecology` | `Ecology` | **KEEP** | Ekologia gatunku. |
| `speciesFactText` | `speciesFactText.threat` | Hot (zagrożenia) | `Threat` | `Threat` | **KEEP** | Czynniki zagrożenia. |
| `speciesFactText` | `speciesFactText.conservationMeasures` | Naturvårdsåtgärder | `ConservationMeasures` | `ConservationMeasures` | **KEEP** | Zalecane zabiegi ochronne. |
| `speciesFactText` | `speciesFactText.other` | Övrigt | `Other` | `Other` | **KEEP** | Uwagi dodatkowe. |
| **Występowanie i historia** | `taxonRelatedInformation.swedishPresence` | Obecność w Szwecji | `SwedishPresence` | `SwedishPresence` | **KEEP** | Status obecności. |
| `taxonRelatedInformation` | `taxonRelatedInformation.immigrationHistory` | Historia imigracji | `ImmigrationHistory` | `ImmigrationHistory` | **KEEP** | Pochodzenie gatunku. |
| `taxonRelatedInformation` | `swedishOccurrence` | Status lęgowy/osiadłości w Szwecji | *(brak)* | `SwedishOccurrence` | **ADD** | Cenne dane: Bofast, Tillfällig, Utdöd itp. |
| `taxonRelatedInformation` | `swedishHistory` | Historia osiedlenia w Szwecji | *(brak)* | `SwedishHistory` | **ADD** | Informacja o antropochorii / rodzimości. |
| **Conservation Assessments** | `conservationAssessments.periods[2019]` | Raportowanie Artikel 17 z 2019 r. | `Artikel 17 - 2019` | `Artikel 17 - 2019` | **KEEP** | Raport Dyrektywy Siedliskowej 2019. |
| `conservationAssessments` | `conservationAssessments.ecology` | Ekologia ocenowa | `ConservationEcology` | `ConservationEcology` | **KEEP** | Opis do oceny. |
| `conservationAssessments` | `conservationAssessments.natureConservation` | Ochrona przyrody ocenowa | `ConservationNatureConservation` | `ConservationNatureConservation` | **KEEP** | Działania ochronne. |
| `conservationAssessments` | `conservationAssessments.treeSpecies` | Gatunki drzew powiązane | `ConservationTreeSpecies` | `ConservationTreeSpecies` | **KEEP** | Powiązane drzewostany. |
| **Främmande / Invasiva arter** | `alienSpeciesRa.riskCategories` | Kategorie ryzyka GEIAA | `AlienSpeciesRiskCategories` | `AlienSpeciesRiskCategories` | **KEEP** | Klasyfikacja ryzyka z API. |
| `alienSpeciesRa` | `alienSpeciesRa.environments` | Środowiska inwazji | `AlienSpeciesEnvironments` | `AlienSpeciesEnvironments` | **KEEP** | Siedliska narażone. |
| `alienSpeciesRa` | `alienSpeciesRa.ecologyEffect` | Wpływ ekologiczny | `AlienSpeciesEcologyEffect` | `AlienSpeciesEcologyEffect` | **KEEP** | Skutki dla rodzimych ekosystemów. |
| `alienSpeciesRa` | `alienSpeciesRa.taxonLists` | Listy gatunków obcych | `AlienSpeciesTaxonLists` | `AlienSpeciesTaxonLists` | **KEEP** | Powiązane listy. |
| `alienSpeciesRa` | `alienSpeciesRa.invationPotentials` | Potencjał inwazyjny | `AlienSpeciesInvationPotentials` | `AlienSpeciesInvationPotentials` | **KEEP** | Szybkość i zasięg rozprzestrzeniania. |
| `alienSpeciesRa` | `alienSpeciesRa.regions` | Regiony występowania | `AlienSpeciesRegions` | `AlienSpeciesRegions` | **KEEP** | Zasięg regionalny. |
| **Konwencje i Dyrektywy (TLS)** | CITES, Bern, Bonn, Fridlyst | Flagi przynależności do list ochrony | Nazwy konwencji | Nazwy konwencji | **KEEP** | Wszystkie 15+ list TLS. |
| `TaxonListService` | `Habitatdirektivet 2023` | Lista rewizji krajowej 2023 | `Habitatdirektivet2023` | `Habitatdirektivet2023` | **KEEP** | Krajowa lista Natura 2000. |
| `TaxonListService` | `Fågeldirektivet bilaga 2` | Załącznik 2 Dyrektywy Ptasiej | `FågeldirektivetBilaga2` | `FågeldirektivetBilaga2` | **KEEP** | Gatunki łowne wg Dyrektywy Ptasiej. |
| `TaxonListService` | `Skogsstyrelsens naturvårdsarter` | Lista gatunków cennych przyrodniczo | `SkogsstyrelsensNaturvardsarter` | `SkogsstyrelsensNaturvardsarter` | **KEEP** | Gatunki leśne. |
| `Plik Excel` | `minskande_faglar50.xlsx` | Gatunki ptaków o spadku >50% | `minskande_faglar` | `minskande_faglar` | **KEEP** | Nowa kolumna analityczna. |
| **Metadane techniczne API** | `guid`, `taxonConceptId`, `sortOrder` | Wewnętrzne identyfikatory bazodanowe | *(brak)* | *(brak)* | **SKIP** | Brak wartości analitycznej dla użytkownika. |

---

## 3. Nowe pola włączane do pełnego datasetu (`ADD`)

W ramach Issue #5 do listy `DATA_COLUMNS` w pełnym/maksymalnym datasie dodajemy:
1. `Author` (`obj.get("author")` lub `item.get("author")`) — autor taksonomiczny i rok (np. `(Linnaeus, 1758)`).
2. `SwedishOccurrence` (`taxonRelatedInformation.swedishOccurrence`) — oficjalny status osiadłości w Szwecji (np. `Bofast`, `Tillfällig`, `Utdöd`).
3. `SwedishHistory` (`taxonRelatedInformation.swedishHistory`) — historia osiedlenia i status rodzimości.

Pola te nie naruszają istniejących presetów eksportu, a wzbogacają pełny zbiór danych.
