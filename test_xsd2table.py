#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_xsd2table.py - Test Suite for xsd2table v3.0.0
Covers:
  - Unit tests for resolve_status and calculate_global_rollup
  - Particle extraction filtering (excluding /xs:schema definitions)
  - End-to-end integration test against S1000D xml_schema_flat
  - Excel workbook sheet structure and freeze panes verification
  - CSV output verification
"""

import os
import sys
import unittest
from pathlib import Path
from lxml import etree
import openpyxl

import xsd2table

SCHEMA_DIR = Path(r"S1000D Issue 6 XML Schema Package\xml_schema_flat")
TEST_OUTPUT_XLSX = Path("test_output_summary.xlsx")
TEST_ELEM_CSV = Path("test_output_summary_elements.csv")
TEST_ATTR_CSV = Path("test_output_summary_attributes.csv")


class TestXsd2Table(unittest.TestCase):

    def tearDown(self):
        for p in [TEST_OUTPUT_XLSX, TEST_ELEM_CSV, TEST_ATTR_CSV]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    def test_01_resolve_status_truth_table(self):
        """Tests the 4-state status resolution logic."""
        self.assertEqual(xsd2table.resolve_status(set()), '0')
        self.assertEqual(xsd2table.resolve_status({'MAND'}), 'MAND')
        self.assertEqual(xsd2table.resolve_status({'OPT'}), 'OPT')
        self.assertEqual(xsd2table.resolve_status({'MAND', 'OPT'}), 'MAND/OPT')
        self.assertEqual(xsd2table.resolve_status({'OPT', 'MAND'}), 'MAND/OPT')

    def test_02_global_rollup_calculation(self):
        """Tests row-level multi-schema rollup calculation."""
        sample_matrix = {
            "elem_pure_mand": {"s1": "MAND", "s2": "MAND", "s3": "0"},
            "elem_pure_opt": {"s1": "OPT", "s2": "0", "s3": "OPT"},
            "elem_mixed_1": {"s1": "MAND/OPT", "s2": "0", "s3": "0"},
            "elem_mixed_2": {"s1": "MAND", "s2": "OPT", "s3": "0"},
            "elem_absent": {"s1": "0", "s2": "0", "s3": "0"},
        }
        pure_mand, pure_opt, mixed = xsd2table.calculate_global_rollup(sample_matrix)
        self.assertEqual(pure_mand, 1)
        self.assertEqual(pure_opt, 1)
        self.assertEqual(mixed, 2)

    def test_03_particle_filtering_excludes_top_level_definitions(self):
        """
        Tests that top-level /xs:schema/xs:element and /xs:schema/xs:attribute
        do not inject spurious MAND or OPT into particle sets.
        """
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
            <!-- Top-level definitions: should not be counted as particle occurrences -->
            <xs:element name="myOptionalElement" type="xs:string"/>
            <xs:attribute name="myRequiredAttr" type="xs:string"/>

            <!-- Root document envelope: unreferenced, should be counted as MAND root -->
            <xs:element name="myRootEnvelope">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element ref="myOptionalElement" minOccurs="0"/>
                    </xs:sequence>
                    <xs:attribute ref="myRequiredAttr" use="required"/>
                </xs:complexType>
            </xs:element>
        </xs:schema>
        """
        temp_file = Path("temp_test_schema.xsd")
        temp_file.write_text(xml_content, encoding="utf-8")
        try:
            result = xsd2table.parse_xsd_file(temp_file, strip_prefixes=True)

            # myOptionalElement should only have 'OPT' (NOT {'MAND', 'OPT'})
            self.assertEqual(result.elements.get("myOptionalElement"), {'OPT'})

            # myRequiredAttr should only have 'MAND' (NOT {'OPT', 'MAND'})
            self.assertEqual(result.attributes.get("myRequiredAttr"), {'MAND'})

            # myRootEnvelope should be recognized as root envelope 'MAND'
            self.assertEqual(result.elements.get("myRootEnvelope"), {'MAND'})
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_04_integration_s1000d_appliccrossreftable(self):
        """Verifies parsing of S1000D flat appliccrossreftable.xsd."""
        schema_file = SCHEMA_DIR / "appliccrossreftable.xsd"
        if not schema_file.exists():
            self.skipTest("S1000D flat schema folder not found.")

        result = xsd2table.parse_xsd_file(schema_file, strip_prefixes=True)

        # dmodule must be MAND
        self.assertEqual(result.elements.get("dmodule"), {'MAND'})

        # language occurs as both minOccurs=1 and minOccurs=0 -> MAND and OPT
        self.assertIn("language", result.elements)
        self.assertEqual(result.elements["language"], {'MAND', 'OPT'})
        self.assertEqual(xsd2table.resolve_status(result.elements["language"]), "MAND/OPT")

        # Description (rdf:Description) should be OPT
        self.assertEqual(result.elements.get("Description"), {'OPT'})

    def test_05_workbook_and_csv_generation(self):
        """Tests full processing and workbook generation."""
        if not SCHEMA_DIR.exists():
            self.skipTest("S1000D flat schema folder not found.")

        element_matrix, attribute_matrix, schema_names = xsd2table.process_schemas(
            schema_dir=SCHEMA_DIR,
            strip_prefixes=True
        )

        self.assertEqual(len(schema_names), 33)
        self.assertEqual(len(element_matrix), 1396)
        self.assertEqual(len(attribute_matrix), 623)

        xsd2table.generate_excel_workbook(
            element_matrix=element_matrix,
            attribute_matrix=attribute_matrix,
            schema_names=schema_names,
            source_dir=SCHEMA_DIR,
            output_file=TEST_OUTPUT_XLSX
        )
        self.assertTrue(TEST_OUTPUT_XLSX.exists())

        wb = openpyxl.load_workbook(str(TEST_OUTPUT_XLSX))
        self.assertEqual(wb.sheetnames, ["Cover", "Elements", "Attributes"])

        # Check Freeze Panes
        self.assertEqual(wb["Elements"].freeze_panes, "B2")
        self.assertEqual(wb["Attributes"].freeze_panes, "B2")

        # Generate CSVs
        xsd2table.generate_csv_outputs(
            element_matrix=element_matrix,
            attribute_matrix=attribute_matrix,
            schema_names=schema_names,
            output_excel_path=TEST_OUTPUT_XLSX
        )
        self.assertTrue(TEST_ELEM_CSV.exists())
        self.assertTrue(TEST_ATTR_CSV.exists())


if __name__ == "__main__":
    unittest.main()
