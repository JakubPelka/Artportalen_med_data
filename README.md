# Artportalen_med_data
Dane z artportalen uzupelnione informacjami o statusie ochrony


AP_extra_uppgifter.py
TL;DR (krótko)

Skrypt bierze Excel z Artportalen/AGOL, a następnie:

używa istniejącego TaxonId z pliku (jeśli brak – potrafi dopasować po nazwach),

usuwa duplikaty po TaxonId (zostawia pierwszy rekord),

pobiera dane ochronne ze SpeciesDataService (ArtDatabanken),

sortuje wg czerwonej listy: RE, CR, EN, VU, NT, DD, LC, NA, NE,

zapisuje:

*_with_data.xlsx – pełna tabela (po deduplikacji),

*_bara_skyddade.xlsx – tylko taksony z jakimkolwiek statusem ochronnym,

opcjonalnie *_full_nodedupe.xlsx – pełna tabela bez usuwania duplikatów (jeśli wybiorę „Tak” w okienku).

Jest okienko wyboru pliku i okienko wyboru folderu zapisu. Powstaje też *_log.txt z przebiegiem pracy.
Publikacje z BFF (Artfakta) są wyciszone (brak stabilnego filtrowania po taksonie).

Długa wersja (pełny opis)
1) Co to jest i po co?

AP_extra_uppgifter.py to „enricher” Excela z Artportalen/AGOL, który konsoliduje dane gatunków i uzupełnia je o atrybuty ochronne/konserwatorskie. Wersja „extra” zakłada, że w źródle przeważnie mamy TaxonId, więc dopasowanie nazw nie jest konieczne (ale jest dostępne, gdy TaxonId brakuje).

2) Wejście / Wyjście

Wejście:

Excel (.xlsx) z kolumną TaxonId.
Jeśli TaxonId brak – skrypt spróbuje dopasować ID po:

taxon_svensktNamn (szwedzka),

taxon_vetenskapligtNamn (naukowa).

Wyjścia (zapisywane do wybranego folderu):

*_with_data.xlsx – pełna tabela po deduplikacji po TaxonId.

*_bara_skyddade.xlsx – filtr na gatunki z jakimkolwiek statusem ochronnym.

*_full_nodedupe.xlsx – opcjonalny eksport bez usuwania duplikatów (włączany w okienku).

*_log.txt – szczegółowy log (przebieg, błędy, brak dopasowań itd.).

3) Skąd dane?

ArtDatabanken / SpeciesDataService – komplet właściwości „konserwatorskich” (redlista, listy, konwencje, fridlysning, sygnały leśne, teksty itp.).

Artfakta BFF – publikacje → wyłączone: publiczny endpoint zwraca globalną listę, nieprzefiltrowaną po taksonie.

4) Jak działa (kroki)

Dialogi: wybór pliku wejściowego oraz folderu zapisu; pytanie o dodatkowy plik bez deduplikacji.

Identyfikacja TaxonId:

jeśli kolumna TaxonId istnieje → używamy,

jeśli nie → dopasowanie po nazwach (szwedzka → „clean” → naukowa „clean” → naukowa „oryg.”). Wszystko logowane.

Dedup: po TaxonId (>0) – zostawiamy pierwszy rekord.

Pobranie danych z SpeciesDataService dla unikalnych TaxonId:

Redlist: kategoria, kryterium, okres, tekst,

Listy/konwencje: CITES, Bernkonventionen, Bonnkonventionen, Fågeldirektivet bilaga 1, Fridlyst, „Priorytetowe ptaki w skogsvårdslagen”,

Dyrektywy/załączniki: DirectiveAppendix2, ...2Priority, Appendix4, Appendix5,

ActionProgram*, ForestrySignal, TypicalSpecies, Biotopes, LandscapeType,

Teksty: Characteristic, Ecology, Threat, ConservationMeasures, SpreadAndStatus, Other,

SwedishPresence, ImmigrationHistory, SubstrateInformation, EcologicalGroups,

ConservationEcology, ConservationNatureConservation, ConservationTreeSpecies,

Artikel 17 - 2019 (zbiera skrótowe trendy z okresu 2019).

Sortowanie wyników wg RedList: RE, CR, EN, VU, NT, DD, LC, NA, NE.

Zapis plików wynikowych + log.

5) Kolumny dopisywane (przykładowo)

Identyfikacja i nazwy: ScientificName, SwedishName, DisplayName, Category

Czerwona lista: RedListCategory, RedListCriterion, RedListPeriodName, RedListCriterionText

Konserwacja/ochrona:
ConservationStatus, ActionProgramName/Status/Start/End, ForestrySignal, TypicalSpecies,
Biotopes, LandscapeType, CITES, Bernkonventionen, Bonnkonventionen,
PrioriteradeFågelarterSkogsvårdslagen, FågeldirektivetBilaga1, Fridlyst, Frid_text,
ProtectedByWorkProtectionConstitution, ProtectedBirds,
DirectiveAppendix2, DirectiveAppendix2Priority, DirectiveAppendix4, DirectiveAppendix5,
Artikel 17 - 2019

Teksty/pozostałe:
Characteristic, SpreadAndStatus, Ecology, Threat, ConservationMeasures, Other,
SwedishPresence, ImmigrationHistory, SubstrateInformation, EcologicalGroups,
ConservationEcology, ConservationNatureConservation, ConservationTreeSpecies

Jeśli którakolwiek z tych kolumn już istnieje w Twoim Excelu, skrypt nie dubluje jej.

6) Wymagania

Python 3.10+

Pakiety: pandas, requests, openpyxl, tkinter (standard w CPython na Windows/macOS; na Linuxie może wymagać doinstalowania).

Klucze API (zmienne środowiskowe; jeśli nie ustawisz, skrypt może użyć wartości wpisanych w kodzie):

TAXONOMY_KEY – taxonservice (dopasowanie nazw → ID),

SPECIES_KEY – speciesdataservice (szczegóły gatunku).

requirements.txt

pandas>=2.0
requests>=2.31
openpyxl>=3.1

7) Instalacja i uruchomienie

Instalacja pakietów:

pip install -r requirements.txt


Ustawienie kluczy (przykłady):

Windows (PowerShell):

$env:TAXONOMY_KEY="TWÓJ_KLUCZ_TAXON"
$env:SPECIES_KEY="TWÓJ_KLUCZ_SPECIES"
python AP_extra_uppgifter.py


macOS/Linux (bash/zsh):

export TAXONOMY_KEY="TWÓJ_KLUCZ_TAXON"
export SPECIES_KEY="TWÓJ_KLUCZ_SPECIES"
python3 AP_extra_uppgifter.py


Po uruchomieniu:

wybierz plik wejściowy (*.xlsx),

wskaż folder zapisu,

odpowiedz, czy chcesz dodatkowy plik „full_nodedupe”.

Wynik:

<nazwa>_with_data.xlsx

<nazwa>_bara_skyddade.xlsx

opcjonalnie <nazwa>_full_nodedupe.xlsx

<nazwa>_log.txt

8) Parametry „techniczne” w kodzie (można pod siebie)

Opóźnienia między zapytaniami (anti-rate-limit):

NAME_QUERY_SLEEP – zapytania do taxonservice

SPECIES_SLEEP – zapytania do speciesdataservice

Timeout na request: TIMEOUT = 30

Kolejność sortowania: słownik RL_ORDER = {"RE":0, "CR":1, ...}

9) Znane ograniczenia / decyzje

Publikacje (Artfakta BFF) – wyciszone (API zwraca globalną listę, bez sprawdzalnego filtra po taksonie).
Gdy pojawi się oficjalna dokumentacja parametru filtrowania, dodamy z powrotem kolumnę i logikę.

Deduplikacja – po TaxonId (zachowujemy rekord „pierwszy z brzegu” z wejścia).

Nazwy wieloznaczne – jeśli brak jednoznacznego dopasowania, TaxonId == 0 i wiersz trafi do loga.

10) FAQ

Q: W moim wejściu nie ma TaxonId.
A: Skrypt spróbuje dopasować po nazwie szwedzkiej/naukowej. Wyniki i niepowodzenia zobaczysz w *_log.txt.

Q: Skąd biorą się różnice w polach ochronnych między gatunkami?
A: Z speciesdataservice – różne grupy mają różny zakres „list”/konwencji. Skrypt nic nie „zgaduje”.

Q: Chcę wyłączyć deduplikację.
A: W okienku wybierz Tak dla dodatkowego pliku *_full_nodedupe.xlsx.

Q: Chcę zobaczyć tylko gatunki „chronione”.
A: Użyj *_bara_skyddade.xlsx — zawiera rekordy z co najmniej jedną niepustą kolumną ochronną (CITES/Bern/Fridlyst/dyrektywy itp.).

11) Dalszy rozwój (notatki dla mnie / asystenta)

 Włączenie publikacji, gdy zespół Artfakta udostępni parametry filtrowania po TaxonId w BFF (/api/metadata/publications).

 Szybsze pobieranie: batchowanie speciesdataservice (jeżeli kiedyś udostępnią).

 Ewentualne profile wyjściowe (np. „Leśnictwo”, „Ptaki”) z minimalnym zestawem pól.

 Opcjonalny export CSV.