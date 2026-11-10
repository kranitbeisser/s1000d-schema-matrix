# Technical & Functional Specification: XSD Schema to Table Converter (`xsd2table`)

| Metadata | Value |
| :--- | :--- |
| **Document Version** | **3.0.0 (Final / Implemented)** |
| **Date** | 2026-11-10 |
| **Status** | Approved & Implemented |
| **Reference Document** | `xsd2table.pdf` (Version 2.1.0) |
| **Target Environment** | Python 3.10+ (`lxml`, `openpyxl`), S1000D Issue 6 XML Schemas |
| **Implementation** | `xsd2table.py`, `test_xsd2table.py` |

---

## 1. Background & Objectives

This specification defines the **`xsd2table`** command-line tool, which analyzes XML Schema Definitions (XSD), extracts element and attribute occurrences across multiple schema files, and consolidates them into standardized multi-sheet Excel workbooks and CSV matrices.

### 1.1 Baseline (As-Is State per PDF v2.1.0)
The legacy script described in `xsd2table.pdf` (Version 2.1.0) presented several structural and functional limitations:
1. **Single-Sheet Output:** All elements and attributes were dumped sequentially into a single worksheet (`XSD Summary`) separated only by a blank row. This required manual post-processing to separate elements from attributes.
2. **Binary Heuristic ("OPT-wins"):** When an element occurred multiple times within the same schema with differing cardinalities, any occurrence with `minOccurs="0"` permanently marked the element as `OPT`. Mandatory usage contexts were erased.
3. **Incomplete Attribute Extraction:** Attributes used a "last-write-wins" overwrite strategy and completely omitted attribute references (`<xs:attribute ref="...">`).
4. **Missing Cover Sheet:** The workbook lacked execution metadata (timestamp, tool version, source path), aggregate statistics, and a standard legend.

### 1.2 Target Objectives (Version 3.0.0)
- **Three Dedicated Worksheets:**
  1. `Cover` (Metadata, multi-schema rollup metrics, legend, and editorial placeholders).
  2. `Elements` (Consolidated XML element occurrence matrix).
  3. `Attributes` (Consolidated XML attribute occurrence matrix).
- **Four-State Requirement Classification:**
  - `MAND`: Element/Attribute is mandatory across all occurrences in this schema.
  - `OPT`: Element/Attribute is optional across all occurrences in this schema.
  - `MAND/OPT`: Element/Attribute occurs as both mandatory and optional depending on context in this schema.
  - `0`: Element/Attribute is not present in this schema.
- **Particle-Level Cardinality Extraction:** Cleanly separates top-level schema definitions (`/xs:schema/xs:element`, `/xs:schema/xs:attribute`) from actual content model usages (`xs:complexType`, `xs:group`, `xs:sequence`, `xs:choice`), preventing false-positive requirement classifications.

### 1.3 Non-Goals
The following functions are explicitly **Out-of-Scope**:
- **No Semantic XML Instance Validation:** The tool does not calculate instance-level satisfiability trees for `<xs:choice>` branches in actual instance documents. Status values strictly reflect declared particle cardinalities in the schema.
- **No Remote Network Fetching:** External schemas are not downloaded over HTTP/HTTPS; only local `.xsd` files are evaluated.
- **No Schema Modification:** The tool operates in strict read-only mode.
- **No Web / GUI Interface:** Pure CLI execution.

---

## 2. As-Is vs. To-Be Analysis

| Area | Version 2.1.0 (PDF) | Version 3.0.0 (Implemented) | Operational Benefit |
| :--- | :--- | :--- | :--- |
| **Excel Structure** | Single sheet (`XSD Summary`) | **3 sheets (`Cover`, `Elements`, `Attributes`)** | Direct filtering, independent sorting, no manual slicing. |
| **Status Resolution** | Binary (`MAND` or `OPT` via "OPT-wins") | **4-state (`MAND`, `OPT`, `MAND/OPT`, `0`)** | Full visibility into context-dependent mandatory elements. |
| **Attribute References** | Ignored (`@name` only) | **Full support (`@name` and `@ref`)** | Captures global attributes (e.g. XLink, XML namespaces). |
| **Schema Definitions** | Top-level elements evaluated naively | **Top-level definitions excluded from particles** | Eliminates false-positive `MAND/OPT` classifications. |
| **Cover Sheet** | Not present | **Metadata, metrics, legend, editorial notes** | Audit traceability, documentation context, and review tracking. |
| **Usability / Styling** | Unstyled table, no freeze panes | **Frozen headers & name columns (`B2`), auto-filter, soft palette** | Ergonomic browsing across 33+ schema columns and 1,400+ rows. |
| **CSV Output** | Single mixed file with blank row | **Two dedicated matrix CSVs (`_elements`, `_attributes`)** | Direct pipeline ingestion into databases or downstream tools. |

---

## 3. Functional Requirements

### FR-1: 3-Sheet Workbook Structure
The generated Excel file contains exactly three worksheets:
1. `Cover`: Execution metadata, summary rollup counts, status legend, and project context.
2. `Elements`: Alphabetical matrix of all XML elements across all processed schemas.
3. `Attributes`: Alphabetical matrix of all XML attributes across all processed schemas.

### FR-2: Cover Sheet Layout & Metrics
- **Section 1: Document Metadata:** ISO generation timestamp, tool version, source directory, schema count.
- **Section 2: Summary Metrics (Multi-Schema Rollup):** Total unique elements and attributes, broken down into Pure MAND, Pure OPT, and Context-Dependent Mixed (MAND/OPT).
- **Section 3: Requirement Classification & Legend:** Clear definitions and sample-styled cells for `MAND`, `OPT`, `MAND/OPT`, and `0`.
- **Section 4: Project & Editorial Context:** Standardized placeholders (`[ Issue 6.0 ]`, `[ Project Name ]`, `[ Approval Stage ]`, `[ Author / Reviewer ]`, `[ Remarks ]`).

### FR-3: 4-State Classification & Rollup Math
- **Local Occurrence Evaluation per Schema $S$:**
  $$\text{Status}_{\text{local}}(E) = \begin{cases} \text{OPT}, & \text{if declared } \text{minOccurs} = \text{"0"} \\ \text{MAND}, & \text{if declared } \text{minOccurs} \ge 1 \text{ (default 1)} \end{cases}$$
  $$\text{Status}_{\text{local}}(A) = \begin{cases} \text{MAND}, & \text{if } \text{use} = \text{"required"} \\ \text{OPT}, & \text{if } \text{use} \in \{\text{"optional"}, \text{None}\} \end{cases}$$

- **Matrix Cell Truth Table:**
  For the observed set of states $\mathcal{M}(S)$:
  - $\mathcal{M}(S) = \emptyset \implies \mathbf{0}$
  - $\mathcal{M}(S) = \{\text{MAND}\} \implies \mathbf{MAND}$
  - $\mathcal{M}(S) = \{\text{OPT}\} \implies \mathbf{OPT}$
  - $\mathcal{M}(S) = \{\text{MAND}, \text{OPT}\} \implies \mathbf{MAND/OPT}$

- **Multi-Schema Global Rollup Formula:**
  For any row item across all schemas, let non-zero statuses be $\mathcal{S}_{\text{row}} = \{R(S) \mid R(S) \neq \text{'0'}\}$:
  - *Mandatory Only (MAND):* $\mathcal{S}_{\text{row}} = \{\text{'MAND'}\}$
  - *Optional Only (OPT):* $\mathcal{S}_{\text{row}} = \{\text{'OPT'}\}$
  - *Context-Dependent Mixed (MAND/OPT):* $\text{'MAND/OPT'} \in \mathcal{S}_{\text{row}}$ or $\{\text{'MAND'}, \text{'OPT'}\} \subseteq \mathcal{S}_{\text{row}}$

### FR-4: Particle-Level Extraction & Prefix Handling
- **Particle Extraction Boundary:**
  - *Attributes:* Evaluates only `xs:attribute` nodes where `parent::xs:schema` is false.
  - *Elements:* Evaluates only `xs:element` nodes where `parent::xs:schema` is false. Unreferenced root document envelopes (`dmodule`) declared at top level are included as `MAND`.
- **Namespace Prefixes:** Stripped by default (`name.split(':')[-1]`) for clean cross-schema vocabulary alignment. Prefixes can be retained via `--keep-prefixes`.

### FR-5: Excel Formatting & CSV Output
- **Freeze Panes:** Frozen at `B2` on both matrix sheets (row 1 headers and column A names remain visible).
- **Auto-Filter:** Enabled across all populated columns.
- **Color Palette (Soft Business):**
  - `MAND`: Light red fill (`#FFD8D8`), dark red bold text (`#900000`).
  - `OPT`: Light green fill (`#D9EAD3`), dark green regular text (`#274E13`).
  - `MAND/OPT`: Soft amber fill (`#FFF2CC`), dark brown bold text (`#7F6000`).
  - `0`: Dimmed light gray fill (`#F2F2F2`), muted gray text (`#8C8C8C`).
- **CSV Output:** Emits `<basename>_elements.csv` and `<basename>_attributes.csv`.

---

## 4. CLI Specification

```
usage: xsd2table [-h] [-o OUTPUT] [--no-excel] [--no-csv] [--keep-prefixes] [-d] schema_folder

Convert a folder of XSD schemas into a 3-sheet Excel matrix (Cover, Elements, Attributes) and CSVs.

positional arguments:
  schema_folder          Path to the directory containing .xsd schema files.

options:
  -h, --help             show this help message and exit
  -o, --output OUTPUT    Path to output Excel file. (default: xsd_summary.xlsx)
  --no-excel             Skip generation of the Excel file.
  --no-csv               Skip generation of CSV matrix files.
  --keep-prefixes        Keep XML namespace prefixes (e.g. rdf:Description).
  -d, --debug            Enable verbose debug logging.
```

- **Exit Codes:**
  - `0`: Success.
  - `1`: Invalid arguments, missing folder, or conflicting options (`--no-excel` and `--no-csv` both active).
  - `2`: Fatal parsing failure.

---

## 5. Verification & Test Matrix

| Test ID | Test Target | Verification Criterion | Result |
| :---: | :--- | :--- | :---: |
| **T-01** | `resolve_status` | Truth table: $\emptyset \to \text{'0'}$, `MAND` $\to \text{'MAND'}$, `OPT` $\to \text{'OPT'}$, `{MAND, OPT}` $\to \text{'MAND/OPT'}$. | **PASS** |
| **T-02** | Global Rollup | Correct calculation of Pure MAND, Pure OPT, and Mixed items across schemas. | **PASS** |
| **T-03** | Particle Filtering | Top-level definitions under `<xs:schema>` do not inject false `MAND` or `OPT`. | **PASS** |
| **T-04** | S1000D Integration | In `appliccrossreftable.xsd`: `dmodule` $\to$ `MAND`, `language` $\to$ `MAND/OPT`, `Description` $\to$ `OPT`. | **PASS** |
| **T-05** | E2E Workbook & CSV | Creates sheets `Cover`, `Elements`, `Attributes`, freeze panes at `B2`, generates matching CSVs. | **PASS** |
