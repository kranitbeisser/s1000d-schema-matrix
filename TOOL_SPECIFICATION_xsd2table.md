# Fach- und Systemspezifikation: XSD Schema to Table Converter (`xsd2table`)

| Metadatum | Wert |
| :--- | :--- |
| **Dokument-Version** | **3.0.0 (Final / Implemented)** |
| **Datum** | 09.11.2026 |
| **Status** | Genehmigt & Implementiert |
| **Referenzdokument** | `xsd2table.pdf` (Version 2.1.0) |
| **Zielumgebung** | Python 3.10+ (`lxml`, `openpyxl`), S1000D Issue 6 XML Schemas |
| **Implementierung** | `xsd2table.py`, `test_xsd2table.py` |

---

## 1. Ausgangslage & Zielsetzung

Die vorliegende Spezifikation definiert das Werkzeug **`xsd2table`** zur Extraktion, Analyse und tabellarischen Konsolidierung von XML-Schema-Definitionen (XSD) über mehrere Schemadateien hinweg in standardisierte Excel-Arbeitsmappen und CSV-Matrizen.

### 1.1 Ausgangslage (Ist-Zustand gemäss PDF v2.1.0)
Das im Dokument `xsd2table.pdf` beschriebene Skript (Version 2.1.0) wies strukturelle und funktionale Einschränkungen auf:
1. **Single-Sheet-Ausgabe:** Sämtliche Elemente und Attribute wurden sequenziell in ein einziges Arbeitsblatt (`XSD Summary`) untereinander geschrieben, getrennt durch eine Leerzeile. Dies erforderte manuelle Nachbearbeitung zur Trennung von Elementen und Attributen.
2. **Binäre Heuristik ("OPT-wins"):** Bei mehrfachem Vorkommen eines Elements innerhalb desselben Schemas mit unterschiedlichen Kardinalitäten überschrieb ein einzelnes `minOccurs="0"` pauschal den Status zu `OPT`. Pflicht-Kontexte wurden dadurch unkenntlich gemacht.
3. **Unvollständige Attribut-Erfassung:** Attribute wurden mit "Last-occurrence-wins" überschrieben; zudem wurden Attribut-Referenzen (`<xs:attribute ref="...">`) ignoriert.
4. **Fehlendes Deckblatt (Cover Sheet):** Die Arbeitsmappe enthielt weder Metadaten (Zeitstempel, Toolversion, Quellpfade) noch Kennzahlen oder einheitliche Legenden.

### 1.2 Zielsetzung (Soll-Zustand Version 3.0.0)
- **Aufteilung in drei separate Tabellenblätter:** 
  1. `Cover` (Deckblatt mit Metadaten, Gesamtstatistiken, Legende und Projekt-Platzhaltern)
  2. `Elements` (Konsolidierte Element-Matrix)
  3. `Attributes` (Konsolidierte Attribut-Matrix)
- **Vierstufige Statuslogik:**
  - `MAND`: Element/Attribut ist an allen Verwendungsstellen im Schema verpflichtend.
  - `OPT`: Element/Attribut ist an allen Verwendungsstellen im Schema optional.
  - `MAND/OPT`: Element/Attribut tritt im selben Schema kontextabhängig sowohl als Pflicht- als auch als Optionsfeld auf.
  - `0`: Element/Attribut ist im jeweiligen Schema nicht vorhanden.
- **Partikel-Kardinalitätsextraktion:** Saubere Trennung zwischen reinen Vokabular-Definitionen auf Wurzelebene (`/xs:schema/xs:element`, `/xs:schema/xs:attribute`) und tatsächlichen Strukturverwendungen in Content-Modellen (`xs:complexType`, `xs:group`, `xs:sequence`, `xs:choice`), um Fehldiagnosen zu vermeiden.

### 1.3 Nicht-Ziele (Non-Goals)
Folgende Funktionen sind explizit **Out-of-Scope**:
- **Keine semantische XML-Instanz-Validierung:** Das Tool berechnet keine Erfüllbarkeitsbäume von `<xs:choice>`-Alternativen in Instanzdokumenten. Der Status spiegelt die syntaktisch deklarierte Kardinalität wider.
- **Kein Online-Netzwerkzugriff:** Externe Schemata werden nicht über HTTP/HTTPS nachgeladen; es werden ausschließlich lokale Dateien analysiert.
- **Keine Modifikation von Schemadateien:** Das Tool arbeitet strikt lesend.
- **Keine Web- oder GUI-Oberfläche:** Reine CLI-Ausführung.

---

## 2. Analyse des Ist-Zustands (`xsd2table.py` v2.1.0)

### 2.1 Ist-Architektur & Schwachstellen
Im PDF-Dokument `xsd2table.pdf` ist der Quellcode der Version 2.1.0 dokumentiert. Folgende Schwachstellen wurden identifiziert:

| Bereich | Ist-Zustand (v2.1.0) | Problem / Auswirkung |
| :--- | :--- | :--- |
| **Tabellenstruktur** | 1 Arbeitsblatt (`XSD Summary`) | Keine getrennte Filterung von Elementen und Attributen möglich. |
| **Element-Parsing** | Heuristik `"OPT-wins"` | Pflicht-Vorkommen werden bei Mischkontexten vollständig gelöscht. |
| **Attribut-Parsing** | XPath `.//xs:attribute[@name]` | Ignoriert `@ref`-Attribute; letztes Vorkommen überschreibt alle vorherigen. |
| **Wurzeldeklarationen** | XPath `.//xs:element` | Globale Definitionen unter `<xs:schema>` injizieren fehlerhafte Kardinalitäten. |
| **Deckblatt** | Nicht vorhanden | Fehlende Nachvollziehbarkeit bezüglich Erstellungsdatum, Toolversion und Kennzahlen. |

---

## 3. Fachliche und Funktionale Anforderungen

### FR-1: Arbeitsmappenstruktur mit 3 Tabellenblättern
- **Kurzbeschreibung:** Die Excel-Ausgabedatei besteht aus genau drei dedizierten Arbeitsblättern.
- **Struktur:**
  1. `Cover`: Metadaten, aggregierte Kennzahlen, Status-Legende und redaktionelle Projekt-Platzhalter.
  2. `Elements`: Alphabetische Matrix aller XML-Elemente über alle verarbeiteten Schemata.
  3. `Attributes`: Alphabetische Matrix aller XML-Attribute über alle verarbeiteten Schemata.
- **Akzeptanzkriterien:** Arbeitsmappe enthält genau die Blätter `Cover`, `Elements`, `Attributes`.

### FR-2: Tabellenlayout des Deckblatts (`Cover`)
- **Kurzbeschreibung:** Bietet einen normierten Einstiegspunkt für Audit und Qualitätssicherung in vier Abschnitten.
- **Abschnitte:**
  1. *Dokument-Metadaten:* Generierungszeitstempel (ISO), Toolversion, Schema-Pfad, Schema-Anzahl.
  2. *Statistische Kennzahlen:* Gesamtzahl eindeutiger Elemente und Attribute, aufgeschlüsselt nach `MAND`, `OPT` und `MAND/OPT` über alle Schemata hinweg.
  3. *Status-Klassifizierung & Legende:* Definition und visuelle Muster aller vier Statuswerte.
  4. *Redaktioneller Projektkontext:* Platzhalterfelder (`[ Issue 6.0 ]`, `[ Projektname ]`, `[ Freigabe ]`, `[ Author / Reviewer ]`, `[ Anmerkungen ]`).
- **Formatierung:** Spalte A Breite 44, Spalte B Breite 75. Titelblock in Dunkelblau (`#1F4E79`) mit weißem Text; Abschnittsüberschriften in Eisblau (`#D9E1F2`).

### FR-3: Vierstufige Statuslogik und Multi-Schema Rollup
- **Lokale Statuserfassung pro Schema $S$:**
  Für jedes gefundene Partikel-Vorkommen im Schema $S$ gilt:
  $$\text{Status}_{\text{lokal}}(E) = \begin{cases} \text{OPT}, & \text{falls } \text{minOccurs} = \text{"0"} \\ \text{MAND}, & \text{falls } \text{minOccurs} \ge 1 \text{ (Default 1)} \end{cases}$$
  $$\text{Status}_{\text{lokal}}(A) = \begin{cases} \text{MAND}, & \text{falls } \text{use} = \text{"required"} \\ \text{OPT}, & \text{falls } \text{use} \in \{\text{"optional"}, \text{None}\} \end{cases}$$

- **Entscheidungstabelle für Matrix-Zellen:**
  Für die beobachtete Zustandsmenge $\mathcal{M}(S)$:
  - $\mathcal{M}(S) = \emptyset \implies \mathbf{0}$
  - $\mathcal{M}(S) = \{\text{MAND}\} \implies \mathbf{MAND}$
  - $\mathcal{M}(S) = \{\text{OPT}\} \implies \mathbf{OPT}$
  - $\mathcal{M}(S) = \{\text{MAND}, \text{OPT}\} \implies \mathbf{MAND/OPT}$

- **Globaler Rollup für das Deckblatt:**
  Für ein Element bzw. Attribut über alle Schemata sei $\mathcal{S}_{\text{row}} = \{R(S) \mid R(S) \neq \text{'0'}\}$:
  - *Rein verpflichtend (MAND):* $\mathcal{S}_{\text{row}} = \{\text{'MAND'}\}$
  - *Rein optional (OPT):* $\mathcal{S}_{\text{row}} = \{\text{'OPT'}\}$
  - *Kontextabhängig gemischt (MAND/OPT):* $\text{'MAND/OPT'} \in \mathcal{S}_{\text{row}}$ oder $\{\text{'MAND'}, \text{'OPT'}\} \subseteq \mathcal{S}_{\text{row}}$

### FR-4: Partikel-Kardinalitätsextraktion & Namespace-Behandlung
- **Partikel-Filterung:**
  - *Attribute:* Nur `xs:attribute`-Knoten mit `not(parent::xs:schema)` analysieren. Top-Level-Attributdefinitionen sind reine Typdeklarationen und fließen nicht in die Kardinalität ein.
  - *Elemente:* Nur `xs:element`-Knoten mit `not(parent::xs:schema)` analysieren. Top-Level-Elemente unter `<xs:schema>` fließen nur dann als `MAND` ein, wenn sie echte Wurzelknoten sind (nie als Kindpartikel referenziert, z. B. `dmodule`).
- **Namespace-Präfixe:** Standardmäßig werden Präfixe (`rdf:`, `xlink:`, `lom:`, `dc:`) vor der Aggregation entfernt, um Vokabulare über alle S1000D-Schemata einheitlich abzubilden. Das CLI-Flag `--keep-prefixes` erlaubt die Beibehaltung qualifizierter Namen.

### FR-5: Ergonomie, Farbcodierung & CSV-Export
- **Excel-Formatierung:**
  - Header fixiert auf Zeile 1; Spalte A (Name) fixiert (Freeze Panes bei `B2`).
  - Auto-Filter über alle Spalten aktiviert.
  - Groß-/Kleinschreibungs-unabhängige Sortierung von Zeilen und Spalten.
  - Farbpalette:
    - `MAND`: Hellrot (`#FFD8D8`), dunkelroter Text (`#900000`), fett.
    - `OPT`: Hellgrün (`#D9EAD3`), dunkelgrüner Text (`#274E13`).
    - `MAND/OPT`: Helles Bernsteingelb (`#FFF2CC`), dunkelbrauner Text (`#7F6000`), fett.
    - `0`: Hellgrau (`#F2F2F2`), gedämpfter grauer Text (`#8C8C8C`).
- **CSV-Export:** Erzeugt zwei CSV-Dateien basierend auf dem Basenamen des Ausgabepfads:
  `<basename>_elements.csv` und `<basename>_attributes.csv`.

---

## 4. Evaluierte Alternativen (Alternatives Considered)

| Alternative | Evaluierte Option | Bewertung & Entscheidung |
| :--- | :--- | :--- |
| **Parsing-Engine** | SAX (`iterparse`) vs. DOM (`etree.parse`) | `etree.parse` gewählt: XSD-Dateien sind mit <5 MB klein; XPath-Ausdrücke für Partikel-Filterung (`not(parent::xs:schema)`) sind via DOM wartbarer und robuster. |
| **Tabellen-Bibliothek** | `xlsxwriter` vs. `openpyxl` | `openpyxl` gewählt: Breitere Verbreitung, keine binären C-Dependencies, exzellente Unterstützung für Freeze Panes und Tabellenblätter. |
| **Speichermodell** | Pandas DataFrame vs. Native Python Dictionaries | Native Dicts (`dict[str, dict[str, str]]`) gewählt: Erfordert keine schwere Pandas-Dependency, minimiert Startzeit und Speicherbedarf (<25 MB). |

---

## 5. Risiken, Grenzen & Schutzmaßnahmen (Risks & Mitigations)

1. **XXE-Angriffe (XML External Entity):**
   - *Risiko:* Bösartige oder manipulierte XML-Schemas könnten versuchen, externe Dateien über DTD/Entitäten nachzuladen.
   - *Maßnahme:* Der XML-Parser wird strikt gehärtet: `etree.XMLParser(resolve_entities=False, no_network=True)`.
2. **Speicherüberlauf bei großen Datenmengen:**
   - *Risiko:* Zuweisung neuer `PatternFill`- und `Font`-Objekte pro Zelle bei 70.000+ Zellen führt zu Speicheraufblähung.
   - *Maßnahme:* Wiederverwendung statischer Flyweight-Stilkonstanten (`FILL_MAND`, `FONT_MAND`, etc.) und inkrementelle Spaltenbreitenberechnung.

---

## 6. Technische Implementierung & CLI-Spezifikation

### 6.1 CLI-Schnittstelle
```
usage: xsd2table [-h] [-o OUTPUT] [--no-excel] [--no-csv] [--keep-prefixes] [-d] schema_folder

Positional Arguments:
  schema_folder          Pfad zum Verzeichnis mit .xsd Schemadateien

Optional Arguments:
  -h, --help             Hilfe anzeigen
  -o, --output OUTPUT    Pfad zur Excel-Ausgabedatei (Default: xsd_summary.xlsx)
  --no-excel             Überspringt die Erzeugung der Excel-Datei
  --no-csv               Überspringt die Erzeugung der CSV-Dateien
  --keep-prefixes        Namespace-Präfixe beibehalten (z. B. rdf:Description)
  -d, --debug            Verbose Debug-Logging aktivieren
```

- **Exit Codes:**
  - `0`: Erfolgreich abgeschlossen.
  - `1`: Ungültige Parameter, Verzeichnis nicht gefunden oder widersprüchliche Optionen (`--no-excel` und `--no-csv` gleichzeitig).
  - `2`: Schwerwiegender Fehler beim Parsen.

### 6.2 Phasenplan der Implementierung
- **Phase 1 (CLI & Logging):** Argument-Parsing, Validierung und Logging (`logs/xsd_parser.log`).
- **Phase 2 (Partikel-Parser):** Implementierung von `parse_xsd_file` mit Ausschluss von `parent::xs:schema`.
- **Phase 3 (Matrix-Aggregator):** Aggregation und Rollup-Berechnung.
- **Phase 4 (Excel-Generator):** Erzeugung der Blätter `Cover`, `Elements`, `Attributes` mit Styling und Freeze Panes.
- **Phase 5 (CSV-Generator):** Erzeugung von `<basename>_elements.csv` und `<basename>_attributes.csv`.
- **Phase 6 (Verifikation):** Automatisierte Unit- und Integrationstests (`test_xsd2table.py`).

---

## 7. Testplan und Verifikationsmatrix

| Test-ID | Testfall | Prüfkriterium |
| :--- | :--- | :--- |
| **T-01** | Status-Entscheidungstabelle | `resolve_status` mappt $\emptyset \to \text{'0'}$, `MAND` $\to \text{'MAND'}$, `OPT` $\to \text{'OPT'}$, `{MAND, OPT}` $\to \text{'MAND/OPT'}$. |
| **T-02** | Partikel-Filterung | Globale Elemente/Attribute unter `<xs:schema>` erzeugen keine fehlerhaften `MAND/OPT`-Status. |
| **T-03** | S1000D Integration | In `appliccrossreftable.xsd` ist `dmodule` $\to$ `MAND`, `language` $\to$ `MAND/OPT`, `Description` $\to$ `OPT`. |
| **T-04** | Excel-Struktur | Arbeitsmappe enthält `["Cover", "Elements", "Attributes"]`; Freeze Panes auf `B2`. |
| **T-05** | CSV-Generierung | Beide CSV-Dateien werden synchron und vollständig erzeugt. |
