# S1000D Schema Matrix (`xsd2table`)

A high-performance Python utility to parse W3C XML Schema Definition (XSD) suites—optimized for **S1000D Issue 6**—and generate consolidated, multi-sheet Excel workbooks and CSV requirement matrices.

---

## Overview

In complex XML schema suites like S1000D, elements and attributes are reused across dozens of document schemas (`descript.xsd`, `proced.xsd`, `appliccrossreftable.xsd`, `brex.xsd`, etc.). Depending on the structural context, an element or attribute may be mandatory in one branch and optional in another.

`xsd2table` parses all schemas in a target folder, evaluates particle-level occurrences, and produces a consolidated view clearly indicating whether each item is mandatory (`MAND`), optional (`OPT`), mixed (`MAND/OPT`), or absent (`0`).

---

## Key Features

- **3-Sheet Excel Workbook:**
  - `Cover`: Execution metadata, multi-schema rollup counts, visual legend, and editable project information fields.
  - `Elements`: Complete element occurrence matrix across all schemas (frozen panes, auto-filters).
  - `Attributes`: Complete attribute occurrence matrix across all schemas (frozen panes, auto-filters).
- **4-State Requirement Classification:**
  - `MAND`: Mandatory across all occurrences in the schema.
  - `OPT`: Optional across all occurrences in the schema.
  - `MAND/OPT`: Context-dependent (both mandatory and optional in different positions within the same schema).
  - `0`: Not present in the schema.
- **Particle-Aware Extraction:** Decouples top-level dictionary definitions (`/xs:schema/xs:element`, `/xs:schema/xs:attribute`) from local content model usages, eliminating false-positive requirement classifications.
- **Multi-Schema Global Rollup:** Summarizes global counts for elements and attributes across all processed schemas on the Cover sheet.
- **Dual Output:** Generates formatted Excel (`.xlsx`) and structured CSV matrices (`_elements.csv`, `_attributes.csv`).
- **Parallel Processing:** Uses multi-threaded parsing for sub-second execution on large schema sets.

---

## Empirical S1000D Issue 6 Summary

When run against the 33 flat schemas of S1000D Issue 6, the tool extracts:

| Metric | Total Unique | Pure Mandatory (`MAND`) | Pure Optional (`OPT`) | Context-Dependent (`MAND/OPT`) |
| :--- | :---: | :---: | :---: | :---: |
| **XML Elements** | **1,396** | 646 | 642 | **108** |
| **XML Attributes** | **623** | 150 | 432 | **41** |

---

## Installation

### Prerequisites
- Python 3.10+
- `pip`

### Install Dependencies
```bash
pip install -r requirements.txt
```

*(Dependencies: `lxml>=5.0.0`, `openpyxl>=3.1.0`)*

---

## Usage

### Basic CLI Execution
```bash
python xsd2table.py "path/to/schemas" -o "output_matrix.xlsx"
```

### Example with S1000D Schemas
```bash
python xsd2table.py "S1000D Issue 6 XML Schema Package/xml_schema_flat" -o "S1000D_Issue_6_Schema_Elements_and_Attributes_Matrix.xlsx"
```

This generates:
1. `S1000D_Issue_6_Schema_Elements_and_Attributes_Matrix.xlsx`
2. `S1000D_Issue_6_Schema_Elements_and_Attributes_Matrix_elements.csv`
3. `S1000D_Issue_6_Schema_Elements_and_Attributes_Matrix_attributes.csv`

### Command-Line Arguments

| Argument | Flag | Description | Default |
| :--- | :---: | :--- | :--- |
| `schema_folder` | - | Directory containing `.xsd` schema files (Positional, required) | - |
| `--output` | `-o` | Destination path for the generated Excel file | `xsd_summary.xlsx` |
| `--no-excel` | - | Skip generation of the Excel workbook | `False` |
| `--no-csv` | - | Skip generation of CSV matrix files | `False` |
| `--keep-prefixes` | - | Retain namespace prefixes (e.g. `rdf:Description`) | `False` (prefixes stripped) |
| `--debug` | `-d` | Enable verbose debug logging to console and log file | `False` |

---

## Running Automated Tests

Run the test suite using `unittest`:
```bash
python test_xsd2table.py
```

The test suite validates:
- Status resolution logic (truth table)
- Multi-schema global rollup mathematical calculations
- Particle extraction filtering (excluding global declarations)
- S1000D integration on `appliccrossreftable.xsd`
- Workbook structure, sheet names, freeze panes, and CSV outputs

---

## Repository Structure

```
├── xsd2table.py                  # Core CLI converter and parsing engine
├── test_xsd2table.py             # Automated unit and integration test suite
├── TOOL_SPECIFICATION_xsd2table_EN.md # English technical specification
├── TOOL_SPECIFICATION_xsd2table.md    # German technical specification
├── requirements.txt              # Python package dependencies
├── pyproject.toml                # Project metadata and packaging config
└── .gitignore                    # Git exclusions
```

---

## License

This project is licensed under the MIT License.
