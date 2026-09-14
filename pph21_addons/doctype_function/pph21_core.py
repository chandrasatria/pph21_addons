import frappe
from frappe.utils import flt, getdate
from datetime import datetime
import math

def calculate_ptkp(pkp, pkp_status):
	# pkp = penghasilan bruto, pkp_status = TK0, dkk
	# pkp = calculate_ptkp((brutto_net - biaya_jabatan ),pkp_status)
	ptkp = {"TK0":54000000, "TK1":58500000, "TK2":63000000, "TK3":67500000,"K0":58500000,"K1":63000000,"K2":67500000,"K3":72000000}
	# frappe.throw("pkp before: {}, status: {}, ptkp: {}".format(pkp,pkp_status,ptkp[pkp_status]))
	# frappe.throw(str(pkp > ptkp[pkp_status]))
	if pkp > ptkp[pkp_status]:
		pkp = pkp - ptkp[pkp_status]
	else:
		pkp = 0

	return round(pkp,-3)


def calculate_pajak(pkp, use_npwp=True):
	# PPH21 jika mengunakan npwp, jika tidak outputnya di kali * 1.2
	# pajak = calculate_pajak(pkp)
	pajak = 0
	pkp = math.floor(pkp/1000) * 1000
	if pkp != 0:
		if pkp <= 60_000_000:
			pajak = pkp * 0.05
		else:
			if pkp <= 250_000_000:
				pajak = 3_000_000 + ((pkp - 60_000_000) * 0.15)
			else:
				if pkp <= 500_000_000:
					pajak = 31_500_000 + ((pkp - 250_000_000) * 0.25)
				else:
					pajak = 94_000_000 + ((pkp - 500_000_000) * 0.3)

			# frappe.msgprint("pajak 3: {}".format(pajak))
	else:
		return 0
	return math.ceil(pajak) if use_npwp else math.ceil(pajak)*1.2

def calculate_tarif_pajak_ter(golongan, brutto_gaji, month ,year, employee, year_to_date, doc, use_npwp=True):
	print(brutto_gaji)
	get_data_tarif = frappe.db.sql("""
		SELECT
			dter.tarif_pajak
		FROM `tabDetail TER` dter
		WHERE 
			dter.parent in (
				SELECT
					dgolter.parent 
				FROM `tabDetail Golongan TER` dgolter
				WHERE 
					dgolter.status_golongan = '{}'
			)
			AND dter.batas_bawah <= {}
			AND dter.batas_atas >= {}
		LIMIT 1
	""".format(golongan, brutto_gaji, brutto_gaji), as_dict=1)

	list_get_data_tarif = frappe.db.sql("""
		SELECT
			dter.tarif_pajak, dter.batas_bawah, dter.batas_atas
		FROM `tabDetail TER` dter
		WHERE 
			dter.parent in (
				SELECT
					dgolter.parent 
				FROM `tabDetail Golongan TER` dgolter
				WHERE 
					dgolter.status_golongan = '{}'
			)
	""".format(golongan, brutto_gaji, brutto_gaji), as_dict=1)
	
	tarif_pajak = get_data_tarif[0]['tarif_pajak']

	if(get_data_tarif and get_data_tarif[0]):
		pph21_ter_version = round(flt(brutto_gaji*(get_data_tarif[0]['tarif_pajak']/100) / ((100-get_data_tarif[0]['tarif_pajak'])/100)))

		bruto_baru = brutto_gaji + pph21_ter_version
		# perlu cek apakah ini luber ke tier berikutnya
		for row in list_get_data_tarif:
			if row.batas_bawah <= bruto_baru <= row.batas_atas:
				# cek tarif seharusnya
				if get_data_tarif[0]['tarif_pajak'] != row.tarif_pajak:
					# ini jadinya luber
					tarif_pajak = row.tarif_pajak
					pph21_ter_version = round(flt(brutto_gaji*(tarif_pajak/100) / ((100-tarif_pajak)/100)))

					print(pph21_ter_version)

		if (12 - month)==0:
			is_biaya_jabatan_akhir_tahun = frappe.get_value("Salary Structure Assignment", {"employee": doc.employee, "salary_structure":doc.salary_structure}, "biaya_jabatan_akhir_tahun")
			if(is_biaya_jabatan_akhir_tahun):
				year_to_date = flt(year_to_date * 0.05) if flt(year_to_date * 0.05)<6000000 else 6000000
			
			ptkp = calculate_ptkp(year_to_date, golongan)
			# if(ptkp==0):
			# 	return False

			pph21 = calculate_pajak(ptkp, use_npwp)

			get_pph21_ter_per_11 = frappe.db.sql("""
				SELECT 
					SUM(sd.amount)
				FROM 
					`tabSalary Detail` sd
				LEFT JOIN
					`tabSalary Slip` sp ON sd.parent = sp.name
				WHERE
					sp.employee = '{0}' AND sd.salary_component = 'PPH21 TER' 
				AND sp.end_date <= "{1}-11-30" and sp.end_date> "{1}-01-01" and sp.docstatus=1
			""".format(employee, year), as_list=1)

			pph_done=0
			for row in get_pph21_ter_per_11:
				pph_done=flt(row[0])

			if pph21:
				pph21_ter_version = pph21-pph_done

		return pph21_ter_version if use_npwp else pph21_ter_version*1.2

    # pph_21_ter = calculate_tarif_pajak_ter(emp['pkp_status'], flt(row.total_brutto+(row.bonus or 0)), self.month, row.pph_ytd)

def create_salary_component_pph21_ter_gross_up():
	if(not frappe.db.exists("Salary Component", "PPH21 TER Gross Up")):
		doc = frappe.new_doc("Salary Component")
		doc.salary_component = "PPH21 TER Gross Up"
		doc.salary_component_abbr = "pphtergu"
		doc.type = "Earning"
		doc.depends_on_payment_days = 1
		doc.is_tax_applicable = 0		

		doc.save()
		frappe.db.commit()

def create_salary_component_pph21_ter():
	if(not frappe.db.exists("Salary Component", "PPH21 TER")):
		doc = frappe.new_doc("Salary Component")
		doc.salary_component = "PPH21 TER"
		doc.salary_component_abbr = "pphter"
		doc.type = "Deduction"
		doc.depends_on_payment_days = 0

		doc.save()
		frappe.db.commit()

def debug_pph21():
	doc = frappe.get_doc("Salary Slip","Sal Slip/HR-EMP-00906/00001")
	calculate_tax(doc,"validate")

def calculate_tax(self, method):

	if getattr(self, "tipe_salary", None) == "Pesangon":
		return

	date_obj = getdate(self.end_date)
	month_int = date_obj.month
	year_int=date_obj.year
	# bruto_gaji = self.gross_pay
	bruto_gaji=0
	for item in self.earnings:
		if item.is_tax_applicable==1:
			bruto_gaji=bruto_gaji+flt(item.amount)
	# bruto_gaji = sum(item['amount'] for item in self.earnings if item['is_tax_applicable'] == 1)

	if(not self.pkp_status):
		return 

	nominal_pph21_ter = calculate_tarif_pajak_ter(self.pkp_status, bruto_gaji, month_int,year_int, self.employee, self.year_to_date, self, self.npwp != "")	

	print(nominal_pph21_ter)
	# GROSS UP PPH21
	is_gross_up = frappe.get_value("Salary Structure Assignment", {"employee":self.employee, "salary_structure":self.salary_structure}, "pph_21_gross_up")
	if(is_gross_up):
		check_alredy_salary_component_pph21_earnings = any(d.get("salary_component") == 'PPH21 TER Gross Up' for d in self.earnings)
		if(not check_alredy_salary_component_pph21_earnings):
			create_salary_component_pph21_ter_gross_up()
			self.append("earnings", {
				"salary_component": "PPH21 TER Gross Up",
				"amount": 0
			})
		if(self.earnings):
			for i in self.earnings:
				if i.salary_component == 'PPH21 TER Gross Up':
					i.amount = nominal_pph21_ter

	
	check_alredy_salary_component_pph21 = any(d.get("salary_component") == 'PPH21 TER' for d in self.deductions)
	if(not check_alredy_salary_component_pph21):
		create_salary_component_pph21_ter()
		self.append("deductions", {
			"salary_component": "PPH21 TER",
			"amount": 0
		})
	if(self.deductions):
		for i in self.deductions:
			if i.salary_component == 'PPH21 TER':
				i.amount = nominal_pph21_ter
	
	# self.set_totals()
	

	# self.gross_pay = 0.0
	# if self.salary_slip_based_on_timesheet == 1:
	# 	self.calculate_total_for_salary_slip_based_on_timesheet()
	# else:
	# 	self.total_deduction = 0.0
	# 	if hasattr(self, "earnings"):
	# 		for earning in self.earnings:
	# 			if earning.do_not_include_in_total == 0:
	# 				self.gross_pay += flt(earning.amount, earning.precision("amount"))

	# 	if hasattr(self, "deductions"):
	# 		for deduction in self.deductions:
	# 			if deduction.do_not_include_in_total == 0:
	# 				self.total_deduction += flt(deduction.amount, deduction.precision("amount"))

	# 	self.net_pay = (
	# 		flt(self.gross_pay) - flt(self.total_deduction) - flt(self.get("total_loan_repayment"))
	# 	)
	# self.set_base_totals()

	# frappe.throw(str(nominal_pph21_ter))
	# frappe.throw(str())
