from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from pipelines.features.nijz_obcina_weekly import (
    build_obcina_weekly_epidemiology,
    verify_obcina_weekly_epidemiology,
    write_obcina_weekly_epidemiology,
)


class NijzWeeklyEpidemiologyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.reference_path = self.temp_path / "municipalities.csv"
        self.lyme_path = self.temp_path / "lyme.xlsx"
        self.kme_path = self.temp_path / "kme.xlsx"
        self.output_path = self.temp_path / "epidemiology.csv"
        self.manifest_path = self.temp_path / "epidemiology_manifest.json"

        self.reference_path.write_text(
            "\n".join(
                [
                    "obcina_sifra,obcina_naziv",
                    "1,Ajdovščina",
                    "204,Sveta Trojica v Slovenskih goricah",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        self._write_workbook(
            self.lyme_path,
            rows=[
                {"B": "Občina bivališča / Obolenja po tednih", "E": "2020-01", "F": "2020-53", "G": "SKUPAJ"},
                {"B": "AJDOVŠČINA", "E": 1, "F": "", "G": 1},
                {"B": "SV. TROJICA V SLOV. GORICAH", "E": "", "F": 2, "G": 2},
                {"B": "SKUPAJ", "E": 1, "F": 2, "G": 3},
            ],
        )
        self._write_workbook(
            self.kme_path,
            rows=[
                {"B": "Občina bivališča / Obolenja po tednih", "E": "2020-01", "F": "2020-53", "G": "SKUPAJ"},
                {"B": "AJDOVŠČINA", "E": "", "F": 1, "G": 1},
                {"B": "SV. TROJICA V SLOV. GORICAH", "E": 3, "F": "", "G": 3},
                {"B": "SKUPAJ", "E": 3, "F": 1, "G": 4},
            ],
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_pipeline_builds_join_ready_weekly_rows(self) -> None:
        tables = build_obcina_weekly_epidemiology(
            lyme_input=self.lyme_path,
            kme_input=self.kme_path,
            municipality_reference=self.reference_path,
        )

        self.assertEqual(len(tables.rows), 4)

        first_week = [row for row in tables.rows if row["week_start"] == "2019-12-30"]
        self.assertEqual(len(first_week), 2)

        ajdovscina_first = next(row for row in first_week if row["obcina_sifra"] == "1")
        self.assertEqual(ajdovscina_first["obcina_naziv"], "Ajdovščina")
        self.assertEqual(ajdovscina_first["iso_year"], 2020)
        self.assertEqual(ajdovscina_first["iso_week"], 1)
        self.assertEqual(ajdovscina_first["lyme_cases"], 1)
        self.assertEqual(ajdovscina_first["kme_cases"], 0)
        self.assertEqual(ajdovscina_first["tick_borne_cases_total"], 1)

        trojica_first = next(row for row in first_week if row["obcina_sifra"] == "204")
        self.assertEqual(trojica_first["obcina_naziv"], "Sveta Trojica v Slovenskih goricah")
        self.assertEqual(trojica_first["lyme_cases"], 0)
        self.assertEqual(trojica_first["kme_cases"], 3)
        self.assertEqual(trojica_first["tick_borne_cases_total"], 3)

        last_week = [row for row in tables.rows if row["week_start"] == "2020-12-28"]
        self.assertEqual(len(last_week), 2)
        self.assertEqual(tables.manifest["lyme_case_total"], 3)
        self.assertEqual(tables.manifest["kme_case_total"], 4)
        self.assertEqual(
            tables.manifest["name_aliases_applied"],
            [
                {
                    "raw_name": "SV. TROJICA V SLOV. GORICAH",
                    "matched_name": "Sveta Trojica v Slovenskih goricah",
                }
            ],
        )

    def test_writer_emits_expected_csv_columns(self) -> None:
        tables = build_obcina_weekly_epidemiology(
            lyme_input=self.lyme_path,
            kme_input=self.kme_path,
            municipality_reference=self.reference_path,
        )
        write_obcina_weekly_epidemiology(
            tables,
            output_path=self.output_path,
            manifest_output=self.manifest_path,
        )

        with self.output_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            self.assertEqual(
                reader.fieldnames,
                [
                    "week_start",
                    "week_end",
                    "iso_year",
                    "iso_week",
                    "obcina_sifra",
                    "obcina_naziv",
                    "lyme_cases",
                    "kme_cases",
                    "tick_borne_cases_total",
                ],
            )
            rows = list(reader)
        self.assertEqual(len(rows), 4)
        self.assertTrue(self.manifest_path.exists())

    def test_verifier_accepts_matching_csv(self) -> None:
        tables = build_obcina_weekly_epidemiology(
            lyme_input=self.lyme_path,
            kme_input=self.kme_path,
            municipality_reference=self.reference_path,
        )
        write_obcina_weekly_epidemiology(
            tables,
            output_path=self.output_path,
            manifest_output=self.manifest_path,
        )

        result = verify_obcina_weekly_epidemiology(
            csv_path=self.output_path,
            lyme_input=self.lyme_path,
            kme_input=self.kme_path,
            municipality_reference=self.reference_path,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.report["csv_row_issues"], [])
        self.assertEqual(result.report["value_mismatches"], [])
        self.assertEqual(result.report["missing_csv_keys"], [])
        self.assertEqual(result.report["unexpected_csv_keys"], [])
        self.assertEqual(result.report["municipality_row_total_mismatches"], [])
        self.assertEqual(result.report["aggregated_total_mismatches"]["lyme_cases"], [])
        self.assertEqual(result.report["aggregated_total_mismatches"]["kme_cases"], [])

    def _write_workbook(self, path: Path, *, rows: list[dict[str, object]]) -> None:
        sheet_rows = []
        for index, row in enumerate(rows, start=1):
            cells = []
            for column, value in row.items():
                reference = f"{column}{index}"
                if isinstance(value, str):
                    cells.append(
                        f'<c r="{reference}" t="inlineStr"><is><t>{self._escape_xml(value)}</t></is></c>'
                    )
                else:
                    cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            sheet_rows.append(f'<row r="{index}">{"".join(cells)}</row>')

        worksheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(sheet_rows)}</sheetData>"
            "</worksheet>"
        )
        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="2020" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>"
        )
        workbook_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            "</Relationships>"
        )
        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>"
        )
        root_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            "</Relationships>"
        )

        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("[Content_Types].xml", content_types_xml)
            archive.writestr("_rels/.rels", root_rels_xml)
            archive.writestr("xl/workbook.xml", workbook_xml)
            archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
            archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml)

    @staticmethod
    def _escape_xml(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )


if __name__ == "__main__":
    unittest.main()
