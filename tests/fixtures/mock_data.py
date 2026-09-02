# -*- coding: utf-8 -*-
"""Mock API payloads for offline golden regression testing."""

MOCK_TLS_DEFINITIONS = {
    "conservationLists": [
        {"id": 46, "name": "Fågeldirektivet bilaga 1"},
        {"id": 47, "name": "Fågeldirektivet bilaga 2"},
        {"id": 45, "name": "Prioriterade fågelarter i skogsvårdslagen"},
        {"id": 34, "name": "Fridlysta arter"},
        {"id": 9, "name": "Habitatdirektivets bilaga 2"},
        {"id": 10, "name": "Habitatdirektivets bilaga 2 - prioriterade arter"},
        {"id": 11, "name": "Habitatdirektivets bilaga 4"},
        {"id": 12, "name": "Habitatdirektivets bilaga 5"},
        {"id": 265, "name": "Habitatdirektivet 2023"},
        {"id": 235, "name": "Skogsstyrelsens naturvårdsarter"},
        {"id": 35, "name": "Främmande arter"},
        {"id": 36, "name": "Främmande arter i Sverige"},
        {"id": 37, "name": "EU-förordning 1143/2014 om invasiva främmande arter"},
        {"id": 38, "name": "Risklista främmande arter"},
        {"id": 39, "name": "Risklista - Mycket hög risk"},
        {"id": 40, "name": "Risklista - Hög risk"},
        {"id": 41, "name": "Risklista - Potentiellt hög risk"},
        {"id": 42, "name": "Risklista - Låg risk"},
        {"id": 43, "name": "Risklista - Ingen känd risk"},
    ]
}

# TaxonId -> Set of list IDs
MOCK_TLS_MEMBERSHIPS_BY_LIST_ID = {
    46: [100018],       # Bergand has Fågeldirektivet Bilaga 1
    34: [100021],       # Ejder is Fridlyst
    37: [208248],       # Träsksköldpadda is IAS Union EU
    39: [208248],       # Träsksköldpadda is Risklista_SE
    265: [100018],      # Bergand on Habitatdirektivet 2023
}

MOCK_SPECIES_DATA = {
    100018: {
        "taxonId": 100018,
        "scientificName": "Aythya marila",
        "swedishName": "Bergand",
        "displayName": "Bergand",
        "category": {"id": 13, "name": "Art"},
        "conservationStatus": "Skyddad",
        "redlistInfo": [
            {
                "category": "NT",
                "criterion": "A2b",
                "criterionText": "Minskning av populationsstorlek",
                "period": {"id": 12, "name": "Rödlista 2020", "year": 2020, "current": False},
            },
            {
                "category": "VU",
                "criterion": "B2ab(iii)",
                "criterionText": "Litet utbredningsområde",
                "period": {"id": 13, "name": "Rödlista 2025", "year": 2025, "current": True},
            },
        ],
        "natureConservation": {
            "actionProgram": {"program": "ÅGP Kustfåglar", "status": "Pågående", "startYear": 2022, "endYear": 2027},
            "forestryBoardSignalSpecies": {"apply": "Ja", "speciesNames": ["Bergand"]},
            "typicalSpecies": [{"typical": "Kustbiotoper", "regions": ["Västkusten"]}],
            "protectedText": "Fridlyst i hela landet.",
        },
        "landscapeTypes": [{"name": "Kust", "status": "Viktig"}],
        "biotopes": [{"name": "Grunda havsvikar", "significance": "Huvudbiotop"}],
        "speciesFactText": {
            "characteristic": "Medelstor dykand.",
            "spreadAndStatus": "Häckar sparsamt i fjällen och skärgården.",
            "ecology": "Häckar vid sjöar och vikar.",
            "threat": "Störning och predation.",
        },
        "author": "(Linnaeus, 1761)",
        "taxonRelatedInformation": {
            "swedishPresence": "Närvarande",
            "immigrationHistory": "Ursprunglig",
            "swedishOccurrence": "Bofast",
            "swedishHistory": "Spontant etablerad",
        },
    },
    100027: {
        "taxonId": 100027,
        "scientificName": "Spinus spinus",
        "swedishName": "Grönsiska",
        "displayName": "Grönsiska",
        "category": {"id": 13, "name": "Art"},
        "conservationStatus": "",
        "redlistInfo": [
            {
                "category": "LC",
                "criterion": "",
                "criterionText": "",
                "period": {"id": 13, "name": "Rödlista 2025", "year": 2025, "current": True},
            }
        ],
        "natureConservation": {},
    },
    100021: {
        "taxonId": 100021,
        "scientificName": "Somateria mollissima",
        "swedishName": "Ejder",
        "displayName": "Ejder",
        "category": {"id": 13, "name": "Art"},
        "conservationStatus": "",
        "redlistInfo": [
            {
                "category": "NT",
                "criterion": "A2b",
                "criterionText": "Minskning av häckande population",
                "period": {"id": 13, "name": "Rödlista 2025", "year": 2025, "current": True},
            }
        ],
        "natureConservation": {
            "protectedText": "Fridlyst enligt artskyddsförordningen.",
        },
    },
    100007: {
        "taxonId": 100007,
        "scientificName": "Anas platyrhynchos",
        "swedishName": "Gräsand",
        "displayName": "Gräsand",
        "category": {"id": 13, "name": "Art"},
        "conservationStatus": "",
        "redlistInfo": [
            {
                "category": "LC",
                "criterion": "",
                "criterionText": "",
                "period": {"id": 13, "name": "Rödlista 2025", "year": 2025, "current": True},
            }
        ],
        "natureConservation": {},
    },
    208248: {
        "taxonId": 208248,
        "scientificName": "Trachemys scripta",
        "swedishName": "Vattensköldpadda",
        "displayName": "Vattensköldpadda",
        "category": {"id": 13, "name": "Art"},
        "conservationStatus": "Främmande",
        "redlistInfo": [],
        "natureConservation": {},
        "alienSpecies": {
            "riskCategories": ["SE"],
            "invationPotentials": ["Hög"],
            "environments": ["Sötvatten"],
        },
    },
}

MOCK_NAME_SEARCH = {
    "ejder": 100021,
    "grönsiska": 100027,
    "bergand": 100018,
    "gräsand": 100007,
    "somateria mollissima": 100021,
    "spinus spinus": 100027,
    "aythya marila": 100018,
    "anas platyrhynchos": 100007,
}
