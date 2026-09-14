frappe.ui.form.on("Pesangon", {
    refresh(frm) {
        frm.set_query("exit_interview", function() {
            return {
                filters: {
                    docstatus: 1
                }
            };
        });
    },

    exit_interview(frm) {
        if (frm.doc.exit_interview) {
            frappe.db.get_doc("Exit Interview", frm.doc.exit_interview)
            .then(exit => {

                if (exit.employee) {
                    frm.set_value("employee", exit.employee);
                }

                if (exit.employee_name) {
                    frm.set_value("employee_name", exit.employee_name);
                }

                if (exit.relieving_date) {
                    frm.set_value("relieving_date", exit.relieving_date);

                    let rel_date = frappe.datetime.str_to_obj(exit.relieving_date);
                    let next_month = new Date(rel_date.getFullYear(), rel_date.getMonth() + 1, 1);
                    frm.set_value("applicable_date", frappe.datetime.obj_to_str(next_month));
                }

            });
        }
    },

    employee(frm) {
        if (!frm.doc.employee) return;

        frappe.db.get_value(
            "Perhitungan Kompensasi PHK",
            {
                employee: frm.doc.employee,
                docstatus: 1
            },
            "grand_total"
        ).then(r => {

            if (r.message && r.message.grand_total != null) {

                frm.set_value("grand_total", r.message.grand_total);

            } else {

                frm.set_value("grand_total", 0);

                frappe.msgprint({
                    title: "Data Tidak Ditemukan",
                    message: "Perhitungan Kompensasi PHK tidak ditemukan untuk employee ini",
                    indicator: "red"
                });

            }

        });
    }
});