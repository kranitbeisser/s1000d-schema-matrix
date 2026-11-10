#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xsd2table.py - XML Schema to Multi-Sheet Excel & CSV Summary Matrix Converter
Version: 3.0.0
Author: Google Antigravity / EGM Architecture

Parses a directory of W3C XML Schema Definition (XSD) files (e.g. S1000D Issue 6)
and generates a consolidated summary in Excel and CSV formats.
Features:
  - 3-Sheet Excel workbook: Cover (Metadata/Stats), Elements (Matrix), Attributes (Matrix)
  - 4-State requirement classification: MAND, OPT, MAND/OPT, 0
  - Particle-level cardinality extraction (excludes top-level schema definitions)
  - Memory-efficient styling with reusable styles and freeze panes
  - Automatic column width calculation and auto-filters
"""

import os
import sys
import argparse
import logging
import csv
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

try:
    from lxml import etree
except ImportError:
    print("Error: 'lxml' library not found. Please install it using 'pip install lxml'")
    sys.exit(1)

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    Workbook = None

# --- Constants & Configuration ---
TOOL_NAME = "xsd2table"
TOOL_VERSION = "3.0.0"
XS_NAMESPACE = "http://www.w3.org/2001/XMLSchema"
NS_MAP = {'xs': XS_NAMESPACE}
LOGS_DIR = "logs"
LOG_FILE = os.path.join(LOGS_DIR, "xsd_parser.log")

# Excel Palette (Soft Tone / Business High-Contrast)
FILL_TITLE = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
FONT_TITLE = Font(name="Segoe UI", size=14, bold=True, color="FFFFFF")

FILL_SECTION = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
FONT_SECTION = Font(name="Segoe UI", size=11, bold=True, color="1F4E79")

FILL_HEADER = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
FONT_HEADER = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")

FILL_MAND = PatternFill(start_color="FFD8D8", end_color="FFD8D8", fill_type="solid")
FONT_MAND = Font(name="Segoe UI", size=10, bold=True, color="900000")

FILL_OPT = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid")
FONT_OPT = Font(name="Segoe UI", size=10, bold=False, color="274E13")

FILL_MAND_OPT = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
FONT_MAND_OPT = Font(name="Segoe UI", size=10, bold=True, color="7F6000")

FILL_ZERO = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
FONT_ZERO = Font(name="Segoe UI", size=10, bold=False, color="8C8C8C")

FONT_REGULAR = Font(name="Segoe UI", size=10)
FONT_BOLD = Font(name="Segoe UI", size=10, bold=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")

THIN_BORDER_SIDE = Side(border_style="thin", color="D9D9D9")
BORDER_CELL = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, top=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE)


# --- Data Models ---
@dataclass
class SchemaAnalysisResult:
    schema_name: str
    elements: dict[str, set[str]] = field(default_factory=dict)     # clean_name -> {'MAND', 'OPT'}
    attributes: dict[str, set[str]] = field(default_factory=dict)   # clean_name -> {'MAND', 'OPT'}


# --- Logging Setup ---
def setup_logging(debug_mode: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug_mode else logging.INFO
    os.makedirs(LOGS_DIR, exist_ok=True)
    logger = logging.getLogger(TOOL_NAME)
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()

    # File Handler
    fh = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(ch)

    return logger


# --- Core Parsing Logic ---
def parse_xsd_file(filepath: Path, strip_prefixes: bool = True, logger: logging.Logger = None) -> SchemaAnalysisResult:
    """
    Parses a single XSD file to extract element and attribute occurrences.
    Applies particle extraction boundary:
      - Ignores top-level /xs:schema/xs:attribute declarations (dictionary only).
      - Ignores top-level /xs:schema/xs:element declarations UNLESS they are genuine
        unreferenced root envelopes (like dmodule).
      - Evaluates local particle occurrences inside complexTypes and model groups.
    """
    schema_name = filepath.stem
    if logger:
        logger.debug(f"Parsing schema: {schema_name}")

    result = SchemaAnalysisResult(schema_name=schema_name)
    parser = etree.XMLParser(resolve_entities=False, no_network=True)

    try:
        tree = etree.parse(str(filepath), parser=parser)
        root = tree.getroot()
    except Exception as e:
        if logger:
            logger.error(f"Failed to parse XSD '{filepath}': {e}")
        return result

    # 1. Extract Local Elements (inside complexTypes, groups, choices, sequences)
    local_elements = root.xpath('.//xs:element[not(parent::xs:schema)]', namespaces=NS_MAP)
    all_referenced_element_names = set()

    for elem in local_elements:
        raw_name = elem.get('ref') or elem.get('name')
        if not raw_name:
            continue
        all_referenced_element_names.add(raw_name)
        clean_name = raw_name.split(':')[-1] if strip_prefixes else raw_name

        min_occurs = elem.get('minOccurs', '1')
        status = 'OPT' if min_occurs == '0' else 'MAND'
        result.elements.setdefault(clean_name, set()).add(status)

    # 2. Extract Genuine Root Elements
    # In S1000D, the document envelope (e.g. 'dmodule') is declared at /xs:schema/xs:element
    # and is NEVER referenced as a child particle in that schema.
    top_elements = root.xpath('/xs:schema/xs:element', namespaces=NS_MAP)
    for top_elem in top_elements:
        raw_name = top_elem.get('name')
        if not raw_name:
            continue
        # If never referenced as a child particle, it is a primary root element (MAND)
        if raw_name not in all_referenced_element_names:
            clean_name = raw_name.split(':')[-1] if strip_prefixes else raw_name
            result.elements.setdefault(clean_name, set()).add('MAND')

    # 3. Extract Local Attributes (inside complexTypes or attributeGroups)
    local_attrs = root.xpath('.//xs:attribute[not(parent::xs:schema)]', namespaces=NS_MAP)
    for attr in local_attrs:
        raw_name = attr.get('ref') or attr.get('name')
        if not raw_name:
            continue
        clean_name = raw_name.split(':')[-1] if strip_prefixes else raw_name
        use = attr.get('use', 'optional')
        status = 'MAND' if use == 'required' else 'OPT'
        result.attributes.setdefault(clean_name, set()).add(status)

    return result


def resolve_status(status_set: set[str]) -> str:
    """
    Maps observed occurrence states to the 4-state matrix value.
    """
    if not status_set:
        return '0'
    if 'MAND' in status_set and 'OPT' in status_set:
        return 'MAND/OPT'
    if 'MAND' in status_set:
        return 'MAND'
    if 'OPT' in status_set:
        return 'OPT'
    return '0'


def calculate_global_rollup(item_dict: dict[str, dict[str, str]]) -> tuple[int, int, int]:
    """
    Calculates multi-schema rollup statistics (Pure MAND, Pure OPT, Mixed MAND/OPT)
    for an aggregated dictionary: item_name -> {schema_name -> resolved_status}.
    """
    pure_mand, pure_opt, mixed = 0, 0, 0
    for item_name, schemas in item_dict.items():
        non_zero = set(st for st in schemas.values() if st != '0')
        if not non_zero:
            continue
        if non_zero == {'MAND'}:
            pure_mand += 1
        elif non_zero == {'OPT'}:
            pure_opt += 1
        else:
            mixed += 1
    return pure_mand, pure_opt, mixed


def process_schemas(
    schema_dir: Path,
    strip_prefixes: bool = True,
    logger: logging.Logger = None
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]], list[str]]:
    """
    Processes all .xsd files in the schema directory in parallel and builds
    the consolidated matrices.
    """
    xsd_files = sorted([f for f in schema_dir.glob("*.xsd") if f.is_file()])
    if not xsd_files:
        if logger:
            logger.error(f"No .xsd files found in directory '{schema_dir}'")
        return {}, {}, []

    if logger:
        logger.info(f"Discovered {len(xsd_files)} XSD files in '{schema_dir}'")

    results: list[SchemaAnalysisResult] = []
    with ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 4) * 2)) as executor:
        futures = {executor.submit(parse_xsd_file, f, strip_prefixes, logger): f for f in xsd_files}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)

    schema_names = sorted([r.schema_name for r in results], key=lambda s: (s.lower(), s))

    # Build matrix dictionaries
    # element_matrix: elem_name -> {schema_name -> status}
    raw_elements: dict[str, dict[str, set[str]]] = {}
    raw_attributes: dict[str, dict[str, set[str]]] = {}

    for res in results:
        for elem_name, s_set in res.elements.items():
            raw_elements.setdefault(elem_name, {})[res.schema_name] = s_set
        for attr_name, s_set in res.attributes.items():
            raw_attributes.setdefault(attr_name, {})[res.schema_name] = s_set

    element_matrix: dict[str, dict[str, str]] = {}
    for elem_name, s_map in raw_elements.items():
        element_matrix[elem_name] = {s: resolve_status(s_map.get(s, set())) for s in schema_names}

    attribute_matrix: dict[str, dict[str, str]] = {}
    for attr_name, s_map in raw_attributes.items():
        attribute_matrix[attr_name] = {s: resolve_status(s_map.get(s, set())) for s in schema_names}

    return element_matrix, attribute_matrix, schema_names


# --- Excel Generation ---
def generate_excel_workbook(
    element_matrix: dict[str, dict[str, str]],
    attribute_matrix: dict[str, dict[str, str]],
    schema_names: list[str],
    source_dir: Path,
    output_file: Path,
    logger: logging.Logger = None
) -> None:
    """
    Generates a 3-sheet Excel workbook with Cover, Elements, and Attributes sheets.
    """
    if Workbook is None:
        if logger:
            logger.error("openpyxl library not installed; cannot generate Excel output.")
        return

    if logger:
        logger.info(f"Generating Excel workbook: {output_file}")

    wb = Workbook()

    # Pre-calculate global rollups
    elem_mand, elem_opt, elem_mixed = calculate_global_rollup(element_matrix)
    attr_mand, attr_opt, attr_mixed = calculate_global_rollup(attribute_matrix)

    # -------------------------------------------------------------
    # TAB 1: COVER SHEET
    # -------------------------------------------------------------
    ws_cover = wb.active
    ws_cover.title = "Cover"
    ws_cover.views.sheetView[0].showGridLines = True

    cover_rows = [
        # Title
        ("S1000D XML SCHEMA SUMMARY & ATTRIBUTE MATRIX", ""),
        # Metadata Section
        ("1. Document Metadata", ""),
        ("   Generation Timestamp:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("   Tool & Version:", f"{TOOL_NAME} v{TOOL_VERSION}"),
        ("   Source Schema Directory:", str(source_dir.resolve())),
        ("   Processed Schema Files Count:", len(schema_names)),
        # Statistics Section
        ("2. Summary Metrics (Multi-Schema Rollup)", ""),
        ("   Total Unique XML Elements:", len(element_matrix)),
        ("     - Mandatory Only (MAND):", elem_mand),
        ("     - Optional Only (OPT):", elem_opt),
        ("     - Context-Dependent Mixed (MAND/OPT):", elem_mixed),
        ("   Total Unique XML Attributes:", len(attribute_matrix)),
        ("     - Mandatory Only (MAND):", attr_mand),
        ("     - Optional Only (OPT):", attr_opt),
        ("     - Context-Dependent Mixed (MAND/OPT):", attr_mixed),
        # Legend Section
        ("3. Requirement Classification & Legend", ""),
        ("   MAND", "Element/Attribute is mandatory across all occurrences in this schema"),
        ("   OPT", "Element/Attribute is optional across all occurrences in this schema"),
        ("   MAND/OPT", "Element/Attribute occurs as both mandatory and optional depending on context in this schema"),
        ("   0", "Element/Attribute is not present in this schema"),
        # Editorial Context Placeholder Section
        ("4. Project & Editorial Context (Placeholder)", ""),
        ("   S1000D Issue / Specification:", "[ Issue 6.0 ]"),
        ("   Project / Organization:", "[ Project Name / Organization ]"),
        ("   Status / Approval Stage:", "[ In Work / Approved ]"),
        ("   Authors / Reviewers:", "[ Schema Analyst / Editorial Team ]"),
        ("   Remarks / Business Rules Context:", "[ Free-text notes for project-specific business rules / BRDP mappings ]")
    ]

    for row_idx, (col_a, col_b) in enumerate(cover_rows, start=1):
        c1 = ws_cover.cell(row=row_idx, column=1, value=col_a)
        c2 = ws_cover.cell(row=row_idx, column=2, value=col_b)

        # Style Title
        if row_idx == 1:
            c1.fill = FILL_TITLE
            c1.font = FONT_TITLE
            c2.fill = FILL_TITLE
            ws_cover.row_dimensions[row_idx].height = 28
        # Style Section Headers
        elif col_a.startswith(("1.", "2.", "3.", "4.")):
            c1.fill = FILL_SECTION
            c1.font = FONT_SECTION
            c2.fill = FILL_SECTION
            ws_cover.row_dimensions[row_idx].height = 20
        # Style Legend Entries
        elif col_a.strip() in ("MAND", "OPT", "MAND/OPT", "0"):
            c1.font = FONT_BOLD
            c1.alignment = ALIGN_CENTER
            c1.border = BORDER_CELL
            c2.font = FONT_REGULAR
            c2.border = BORDER_CELL
            if col_a.strip() == "MAND":
                c1.fill = FILL_MAND
                c1.font = FONT_MAND
            elif col_a.strip() == "OPT":
                c1.fill = FILL_OPT
                c1.font = FONT_OPT
            elif col_a.strip() == "MAND/OPT":
                c1.fill = FILL_MAND_OPT
                c1.font = FONT_MAND_OPT
            elif col_a.strip() == "0":
                c1.fill = FILL_ZERO
                c1.font = FONT_ZERO
        else:
            c1.font = FONT_REGULAR
            c2.font = FONT_REGULAR

    ws_cover.column_dimensions['A'].width = 44
    ws_cover.column_dimensions['B'].width = 75

    # -------------------------------------------------------------
    # TAB 2 & 3: MATRIX SHEETS (Elements & Attributes)
    # -------------------------------------------------------------
    def populate_matrix_sheet(ws, title: str, name_header: str, matrix_data: dict[str, dict[str, str]]):
        ws.title = title
        ws.views.sheetView[0].showGridLines = True

        # Header Row
        headers = [name_header] + schema_names
        ws.append(headers)
        ws.row_dimensions[1].height = 24

        col_widths = {1: len(name_header) + 4}
        for idx, s in enumerate(schema_names, start=2):
            col_widths[idx] = max(len(s) + 3, 14)

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = FILL_HEADER
            cell.font = FONT_HEADER
            cell.alignment = ALIGN_CENTER
            cell.border = BORDER_CELL

        # Sort matrix items case-insensitively
        sorted_items = sorted(matrix_data.keys(), key=lambda s: (s.lower(), s))

        for row_idx, item_name in enumerate(sorted_items, start=2):
            c_name = ws.cell(row=row_idx, column=1, value=item_name)
            c_name.font = FONT_BOLD
            c_name.alignment = ALIGN_LEFT
            c_name.border = BORDER_CELL
            if len(item_name) + 4 > col_widths[1]:
                col_widths[1] = min(len(item_name) + 4, 60)

            schema_dict = matrix_data[item_name]
            for col_idx, s_name in enumerate(schema_names, start=2):
                val = schema_dict.get(s_name, '0')
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.alignment = ALIGN_CENTER
                cell.border = BORDER_CELL

                if val == 'MAND':
                    cell.fill = FILL_MAND
                    cell.font = FONT_MAND
                elif val == 'OPT':
                    cell.fill = FILL_OPT
                    cell.font = FONT_OPT
                elif val == 'MAND/OPT':
                    cell.fill = FILL_MAND_OPT
                    cell.font = FONT_MAND_OPT
                else:  # '0'
                    cell.fill = FILL_ZERO
                    cell.font = FONT_ZERO

        # Freeze Panes at B2 (Header row & Item name column frozen)
        ws.freeze_panes = 'B2'

        # Auto-filter over all populated columns
        last_col_letter = get_column_letter(len(headers))
        ws.auto_filter.ref = f"A1:{last_col_letter}{len(sorted_items) + 1}"

        # Apply Column Widths
        for col_idx, width in col_widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws_elements = wb.create_sheet("Elements")
    populate_matrix_sheet(ws_elements, "Elements", "Element Name", element_matrix)

    ws_attributes = wb.create_sheet("Attributes")
    populate_matrix_sheet(ws_attributes, "Attributes", "Attribute Name", attribute_matrix)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_file))
    if logger:
        logger.info(f"Successfully created Excel workbook: {output_file.resolve()}")


# --- CSV Generation ---
def generate_csv_outputs(
    element_matrix: dict[str, dict[str, str]],
    attribute_matrix: dict[str, dict[str, str]],
    schema_names: list[str],
    output_excel_path: Path,
    logger: logging.Logger = None
) -> None:
    """
    Generates two structured CSV files:
      - <stem>_elements.csv
      - <stem>_attributes.csv
    """
    stem = output_excel_path.stem
    parent_dir = output_excel_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    elem_csv_path = parent_dir / f"{stem}_elements.csv"
    attr_csv_path = parent_dir / f"{stem}_attributes.csv"

    def write_csv(path: Path, name_header: str, matrix_data: dict[str, dict[str, str]]):
        if logger:
            logger.info(f"Generating CSV: {path}")
        sorted_items = sorted(matrix_data.keys(), key=lambda s: (s.lower(), s))
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([name_header] + schema_names)
            for item in sorted_items:
                row = [item] + [matrix_data[item].get(s, '0') for s in schema_names]
                writer.writerow(row)

    write_csv(elem_csv_path, "Element Name", element_matrix)
    write_csv(attr_csv_path, "Attribute Name", attribute_matrix)


# --- Main CLI Entrypoint ---
def main():
    parser = argparse.ArgumentParser(
        prog="xsd2table",
        description="Convert a folder of XSD schemas into a 3-sheet Excel matrix (Cover, Elements, Attributes) and CSVs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("schema_folder", help="Path to the directory containing .xsd schema files.")
    parser.add_argument("-o", "--output", default="xsd_summary.xlsx", help="Path to output Excel file.")
    parser.add_argument("--no-excel", action="store_true", help="Skip generation of the Excel file.")
    parser.add_argument("--no-csv", action="store_true", help="Skip generation of CSV matrix files.")
    parser.add_argument("--keep-prefixes", action="store_true", help="Keep XML namespace prefixes (e.g. rdf:Description).")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable verbose debug logging.")

    args = parser.parse_args()
    logger = setup_logging(debug_mode=args.debug)

    if args.no_excel and args.no_csv:
        logger.error("Both --no-excel and --no-csv are enabled; nothing to generate.")
        sys.exit(1)

    schema_dir = Path(args.schema_folder)
    if not schema_dir.is_dir():
        logger.error(f"Schema folder does not exist or is not a directory: '{schema_dir}'")
        sys.exit(1)

    output_path = Path(args.output)
    strip_prefixes = not args.keep_prefixes

    logger.info(f"Starting {TOOL_NAME} v{TOOL_VERSION} on '{schema_dir}'...")
    element_matrix, attribute_matrix, schema_names = process_schemas(
        schema_dir=schema_dir,
        strip_prefixes=strip_prefixes,
        logger=logger
    )

    if not schema_names:
        logger.error("Execution terminated: No schemas processed.")
        sys.exit(1)

    if not args.no_excel:
        generate_excel_workbook(
            element_matrix=element_matrix,
            attribute_matrix=attribute_matrix,
            schema_names=schema_names,
            source_dir=schema_dir,
            output_file=output_path,
            logger=logger
        )

    if not args.no_csv:
        generate_csv_outputs(
            element_matrix=element_matrix,
            attribute_matrix=attribute_matrix,
            schema_names=schema_names,
            output_excel_path=output_path,
            logger=logger
        )

    logger.info("xsd2table processing completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()
