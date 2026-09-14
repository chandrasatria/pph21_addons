# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe

CUSTOM_FIELD = [
	"Salary Structure-pph21_ter_section",
	"Salary Structure-pph21_ter_component",
	"Salary Structure-column_break_pph21_ter",
	"Salary Structure-pph21_ter_gross_up_component",
]


def execute():
	"""Komponen PPh21 TER tidak lagi ditunjuk lewat custom field.

	Sekarang dicari dari tabel earnings/deductions milik Salary Structure,
	jadi keempat field ini tidak dipakai lagi. sync_customizations tidak
	membuang field yang hilang dari file, jadi dihapus di sini.
	"""
	for name in CUSTOM_FIELD:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True)

	frappe.clear_cache(doctype="Salary Structure")
