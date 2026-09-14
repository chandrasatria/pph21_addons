# Copyright (c) 2026, DAS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from dateutil.relativedelta import relativedelta
from frappe.utils import getdate


class Pesangon(Document):

	def validate(self):
		self.validate_exit_interview()
		self.set_grand_total_from_kompensasi()
		self.validate_grand_total_and_cicilan()
		self.set_default_applicable_date()
		self.generate_pesangon_periode()

		self.generate_pph21_detail()
		self.set_total_pph()

		self.validate_outstanding_amount()

	def validate_exit_interview(self):
		if not self.exit_interview:
			frappe.throw(_("Field Exit Interview wajib diisi"))

		exit_doc = frappe.get_doc("Exit Interview", self.exit_interview)

		if exit_doc.docstatus != 1:
			frappe.throw(_("Exit Interview harus sudah submitted"))

		self.employee = exit_doc.employee
		self.employee_name = exit_doc.employee_name
		self.relieving_date = exit_doc.relieving_date

	def validate_outstanding_amount(self):
		total_unpaid = 0

		for row in self.pesangon_periode:
			if not row.is_paid:
				total_unpaid += row.amount or 0

		self.outstanding_amount = total_unpaid

	def validate_grand_total_and_cicilan(self):

		if not self.grand_total or self.grand_total <= 0:
			frappe.throw(_("Grand Total harus lebih besar dari 0"))

		if self.opsi_bayar == "Dicicil":
			if not self.jumlah_bulan_cicilan or self.jumlah_bulan_cicilan <= 0:
				frappe.throw(_("Jumlah Bulan Cicilan harus lebih besar dari 0"))

			pembayaran_pertama = self.pembayaran_pertama or 0

			if pembayaran_pertama > self.grand_total:
				frappe.throw(_("Pembayaran pertama tidak boleh lebih besar dari Grand Total"))

			sisa_bulan = self.jumlah_bulan_cicilan - 1 if pembayaran_pertama > 0 else self.jumlah_bulan_cicilan

			if sisa_bulan <= 0 and self.grand_total > pembayaran_pertama:
				frappe.throw(_("Jumlah bulan cicilan terlalu kecil untuk sisa pembayaran"))

			if sisa_bulan > 0:
				self.pembayaran_per_bulan = (self.grand_total - pembayaran_pertama) / sisa_bulan
			else:
				self.pembayaran_per_bulan = 0
		else:
			self.pembayaran_per_bulan = 0

	def set_total_pph(self):
		total = 0

		for row in self.pph_21_detail:
			total += row.pph or 0

		self.total_pph21 = total

	@frappe.whitelist()
	def generate_pesangon_periode(self):
		self.set("pesangon_periode", [])

		start_date = getdate(self.applicable_date)
		start_date = start_date.replace(day=1) 

		if self.opsi_bayar != "Dicicil":
			self.append("pesangon_periode", {
				"periode": start_date,
				"amount": self.grand_total,
				"is_paid": 0
			})
			return

		pembayaran_pertama = self.pembayaran_pertama or 0

		if pembayaran_pertama > 0:
			self.append("pesangon_periode", {
				"periode": start_date,
				"amount": pembayaran_pertama,
				"is_paid": 0
			})

		sisa_bulan = self.jumlah_bulan_cicilan - 1 if pembayaran_pertama > 0 else self.jumlah_bulan_cicilan
		pembayaran_per_bulan = (self.grand_total - pembayaran_pertama) / sisa_bulan if sisa_bulan > 0 else 0

		for i in range(sisa_bulan):
			bulan_ke = i + 1 if pembayaran_pertama > 0 else i
			self.append("pesangon_periode", {
				"periode": start_date + relativedelta(months=bulan_ke),
				"amount": pembayaran_per_bulan,
				"is_paid": 0
			})

		return self

	def set_default_applicable_date(self):
		if not self.applicable_date and self.relieving_date:
			relieving = getdate(self.relieving_date)
			next_month_first = (relieving + relativedelta(months=1)).replace(day=1)
			self.applicable_date = next_month_first

	def set_grand_total_from_kompensasi(self):
		if not self.employee:
			return

		kompensasi = frappe.db.get_value(
			"Perhitungan Kompensasi PHK",
			{
				"employee": self.employee,
				"docstatus": 1
			},
			["name", "grand_total"],
			as_dict=True
		)

		if not kompensasi:
			frappe.throw(_("Perhitungan Kompensasi PHK tidak ditemukan untuk employee ini"))

		self.grand_total = kompensasi.grand_total

	def generate_pph21_detail(self):

		self.set("pph_21_detail", [])

		layers = get_pesangon_layers()

		akumulasi = 0
		prev_pph = 0

		def hitung_pph_bruto(bruto):
			pajak = 0
			for lower, upper, rate, _ in layers:
				if bruto > lower:
					kena = min(bruto, upper) - lower
					pajak += kena * rate
			return pajak

		for row in self.pesangon_periode:

			nilai = row.amount or 0
			start = akumulasi
			akumulasi += nilai

			total_pph = hitung_pph_bruto(akumulasi)
			pph_cicilan = total_pph - prev_pph

			for lower, upper, rate, nama in layers:

				overlap = min(akumulasi, upper) - max(start, lower)

				if overlap > 0:

					self.append("pph_21_detail", {
						"periode": row.periode,
						"nilai_akumulasi": akumulasi,
						"lapisan": nama,
						"pkp": overlap,
						"tarif": rate * 100,
						"pph": overlap * rate
					})

			prev_pph = total_pph

### testing pph21 pesangon
def get_pesangon_layers():

    rows = frappe.get_all(
        "PPh21 Pesangon Layer",
        fields=["description", "percent", "from_amount", "to_amount"],
        order_by="from_amount asc"
    )

    layers = []

    for r in rows:
        upper = r.to_amount if r.to_amount else float("inf")

        layers.append((
            r.from_amount,
            upper,
            r.percent / 100,
            r.description
        ))

    return layers


def hitung_pph_pesangon(total_pesangon, cicilan, first_payment=None):

    layers = get_pesangon_layers()

    def hitung_pph_bruto(bruto):
        pajak = 0
        for lower, upper, rate, _ in layers:
            if bruto > lower:
                kena = min(bruto, upper) - lower
                pajak += kena * rate
        return pajak

    if not first_payment:
        first_payment = total_pesangon / cicilan

    sisa = total_pesangon - first_payment

    if cicilan > 1:
        per_cicilan = sisa / (cicilan - 1)
    else:
        per_cicilan = 0

    payments = [first_payment] + [per_cicilan] * (cicilan - 1)

    akumulasi = 0
    prev_pph = 0
    hasil = []

    for i, nilai in enumerate(payments, start=1):

        akumulasi += nilai

        total_pph = hitung_pph_bruto(akumulasi)
        pph_cicilan = total_pph - prev_pph

        start = akumulasi - nilai
        lapisan_detail = []

        for lower, upper, rate, nama in layers:

            overlap = min(akumulasi, upper) - max(start, lower)

            if overlap > 0:
                lapisan_detail.append({
                    "lapisan": nama,
                    "pkp": overlap,
                    "tarif": rate,
                    "pph": overlap * rate
                })

        hasil.append({
            "cicilan": i,
            "nilai_pesangon": nilai,
            "akumulasi": akumulasi,
            "detail": lapisan_detail,
            "pph_total_cicilan": pph_cicilan
        })

        prev_pph = total_pph

    return hasil

def test():

	data = hitung_pph_pesangon(
		210_266_665,
		5,
		first_payment=None
	)

	for row in data:
		print("\nCicilan", row["cicilan"])
		print("Nilai Pesangon:", round(row["nilai_pesangon"],0))
		print("Akumulasi:", round(row["akumulasi"],0))

		for d in row["detail"]:
			print(
				d["lapisan"],
				round(d["pkp"],0),
				f"{int(d['tarif']*100)}%",
				round(d["pph"],0)
			)