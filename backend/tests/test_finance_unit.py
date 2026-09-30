"""Unit tests for glc_finance (pure logic, no database or network). Run: python -m pytest -p no:cacheprovider -o addopts="" tests/test_finance_unit.py"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import glc_finance as gf  # noqa: E402


# ---------- GSTIN / state ----------
def test_company_gstin_is_valid_and_bihar():
    assert gf.valid_gstin("10FZTPA0354J1ZJ")
    assert gf.COMPANY_STATE_CODE == "10"


@pytest.mark.parametrize("g", ["", "10FZTPA0354J1ZX", "99ABCDE1234F1Z5", "short"])
def test_invalid_gstin(g):
    assert not gf.valid_gstin(g)


@pytest.mark.parametrize("text,code", [("Bihar", "10"), ("BR", "10"), ("bihar ", "10"), ("Delhi", "07"), ("DL", "07"),
                                       ("Jammu & Kashmir", "01"), ("29", "29"), ("Odisha", "21"), ("", None), ("Atlantis", None)])
def test_state_code(text, code):
    assert gf.state_code(text) == code


def test_intra_state_defaults_to_company_state():
    assert gf.is_intra_state(None, None)                       # unknown -> local sale
    assert gf.is_intra_state(None, "Bihar")                    # Bihar customer is intra-state (was wrongly IGST before)
    assert not gf.is_intra_state(None, "Delhi")                # Delhi customer is inter-state (was wrongly CGST+SGST before)
    assert gf.is_intra_state("07AAACH7409R1ZZ", "Bihar")       # invalid GSTIN checksum -> falls back to the state given


def test_registered_buyer_uses_gstin_state():
    assert gf.place_of_supply("10FZTPA0354J1ZJ", "Delhi") == "10"  # GSTIN wins over the free-text state


# ---------- tax maths ----------
def test_exclusive_line_intra():
    r = gf.calc_gst([{"qty": 2, "rate": 100, "gstRate": 18}], intra_state=True)
    assert (r["subtotal"], r["cgst"], r["sgst"], r["igst"], r["total"]) == (200, 18, 18, 0, 236)


def test_exclusive_line_inter():
    r = gf.calc_gst([{"qty": 1, "rate": 1000, "gstRate": 12}], intra_state=False)
    assert (r["subtotal"], r["cgst"], r["igst"], r["total"]) == (1000, 0, 120, 1120)


def test_inclusive_line_extracts_tax():
    r = gf.calc_gst([{"qty": 1, "rate": 118, "gstRate": 18, "taxInclusive": True}], intra_state=True)
    assert (r["subtotal"], r["cgst"], r["sgst"], r["total"]) == (100, 9, 9, 118)


def test_discount_percent_and_amount():
    r = gf.calc_gst([{"qty": 2, "rate": 100, "discount": 10, "discountAmount": 5, "gstRate": 5}], True)
    assert r["subtotal"] == 175 and r["total"] == round(175 * 1.05, 2)


def test_odd_paisa_tax_is_split_without_losing_a_paisa():
    l = gf.split_line({"qty": 1, "rate": 0.5, "gstRate": 18}, True)   # tax 0.09 -> 0.04 + 0.05
    assert round(l["cgst"] + l["sgst"], 2) == l["tax"] == 0.09


def test_zero_rated_produce_has_no_tax():
    r = gf.calc_gst([{"qty": 3, "rate": 8, "gstRate": 0}], True)
    assert r["total"] == 24 and r["cgst"] == r["sgst"] == r["igst"] == 0


def test_round_off_and_totals():
    r = gf.calc_gst([{"qty": 1, "rate": 100.4, "gstRate": 0}], True, round_off=True)
    assert r["total"] == 100 and r["roundOff"] == -0.4


# ---------- website order -> invoice items ----------
def test_delivery_charge_becomes_taxable_line():
    order = {"glczoneItems": [{"name": "Raw Banana", "quantity": 1, "price": 4, "tax_percent": 0, "tax_amount": 0, "sub_total": 4}],
             "deliveryCharge": 20}
    items = gf.items_from_glczone(order)
    r = gf.calc_gst(items, True)
    assert r["total"] == 24                                    # what the customer actually paid
    d = [l for l in r["lines"] if l["isDelivery"]][0]
    assert d["taxable"] == 16.95 and d["tax"] == 3.05


def test_exclusive_website_pricing_detected():
    it = {"name": "Soap", "quantity": 2, "price": 100, "tax_percent": 18, "tax_amount": 36, "sub_total": 236}
    r = gf.calc_gst(gf.items_from_glczone({"glczoneItems": [it]}), True)
    assert (r["subtotal"], r["total"]) == (200, 236)


def test_inclusive_website_pricing_detected():
    it = {"name": "Soap", "quantity": 2, "price": 100, "tax_percent": 18, "tax_amount": 30.51, "sub_total": 200}
    r = gf.calc_gst(gf.items_from_glczone({"glczoneItems": [it]}), True)
    assert r["total"] == 200 and abs(r["cgst"] + r["sgst"] - 30.51) < 0.02


def test_cancelled_items_are_left_out():
    order = {"glczoneItems": [{"name": "A", "quantity": 1, "price": 10, "status": "cancelled"}, {"name": "B", "quantity": 1, "price": 5}]}
    assert [i["name"] for i in gf.items_from_glczone(order)] == ["B"]


# ---------- numbering ----------
def test_financial_year_and_number():
    assert gf.fy_short(date(2026, 3, 31)) == "25-26"
    assert gf.fy_short(date(2026, 4, 1)) == "26-27"
    assert gf.doc_number("INV", 7, date(2026, 9, 30)) == "INV/26-27/00007"
    assert len(gf.doc_number("INV", 99999, date(2026, 9, 30))) <= 16
    assert gf.counter_key("INV", date(2026, 9, 30)) != gf.counter_key("INV", date(2027, 4, 1))


# ---------- journals ----------
def _inv(items, intra=True, delivery=0):
    all_items = list(items) + ([gf.delivery_item(delivery)] if delivery else [])
    t = gf.calc_gst(all_items, intra, round_off=True)
    return {**t, "customerGst": "", "customerState": "", "items": all_items, "status": "UNPAID", "invoiceNo": "INV/26-27/00001",
            "invoiceDate": "2026-09-15T10:00:00", "dueDate": "2026-09-30T10:00:00", "customerName": "A", "dueAmount": t["total"]}


def test_invoice_journal_balances():
    inv = _inv([{"qty": 1, "rate": 100.4, "gstRate": 18, "hsn": "1234"}], True, delivery=20)
    e = gf.journal_for_invoice(inv)
    assert gf.check_balanced(e)
    assert {x["accountCode"] for x in e} >= {"1300", "4100", "4300", "2210", "2220"}


def test_credit_note_and_purchase_and_payment_journals_balance():
    inv = _inv([{"qty": 2, "rate": 100, "gstRate": 12}], False)
    cn_items = gf.credit_note_items(inv, [{"index": 0, "qty": 1}])
    cn = gf.calc_gst(cn_items, False)
    cn["lines"] = cn["lines"]
    assert gf.check_balanced(gf.journal_for_credit_note(cn))
    assert cn["total"] == 112 and cn["igst"] == 12
    assert gf.check_balanced(gf.journal_for_payment(50, "UPI"))
    po = {**gf.calc_gst([{"qty": 10, "rate": 50, "gstRate": 5}], True), "itcEligible": True}
    assert gf.check_balanced(gf.journal_for_purchase(po))
    assert gf.check_balanced(gf.journal_for_purchase({**po, "itcEligible": False}))


def test_credit_note_cannot_exceed_invoiced_qty():
    inv = _inv([{"qty": 1, "rate": 100, "gstRate": 5}])
    with pytest.raises(ValueError):
        gf.credit_note_items(inv, [{"index": 0, "qty": 2}])


def test_credit_note_keeps_line_discount():
    inv = _inv([{"qty": 2, "rate": 100, "discount": 10, "gstRate": 0}])
    cn = gf.calc_gst(gf.credit_note_items(inv, [{"index": 0, "qty": 2}]), True)
    assert cn["total"] == inv["total"] == 180


def test_trial_balance_and_ledger():
    accts = [{"id": "a", "code": "1300", "name": "AR", "type": "ASSET"}, {"id": "b", "code": "4100", "name": "Sales", "type": "INCOME"}]
    j = [{"date": "2026-09-01", "narration": "x", "entries": [{"accountId": "a", "debit": 100, "credit": 0}, {"accountId": "b", "debit": 0, "credit": 100}]},
         {"date": "2026-09-02", "narration": "y", "entries": [{"accountId": "a", "debit": 0, "credit": 40}, {"accountId": "b", "debit": 40, "credit": 0}]}]
    tb = gf.trial_balance(accts, j)
    assert tb["balanced"] and tb["rows"][0]["balance"] == 60 and tb["rows"][1]["balance"] == 60
    assert gf.ledger(accts[0], j)["closing"] == 60


# ---------- reports ----------
def test_gstr1_sections_and_hsn():
    b2b = _inv([{"qty": 1, "rate": 1000, "gstRate": 18, "hsn": "8471"}])
    b2b.update({"customerGst": "10FZTPA0354J1ZJ", "invoiceNo": "INV/26-27/00001"})
    b2c = _inv([{"qty": 2, "rate": 50, "gstRate": 5, "hsn": "1905"}, {"qty": 1, "rate": 30, "gstRate": 0, "hsn": "0803"}])
    b2c["invoiceNo"] = "INV/26-27/00002"
    cn_t = gf.calc_gst(gf.credit_note_items(b2c, [{"index": 0, "qty": 1}]), True)
    cn = {**cn_t, "noteNo": "CN/26-27/00001", "invoiceNo": b2c["invoiceNo"], "noteDate": "2026-09-20", "customerGst": ""}
    r = gf.gstr1([b2b, b2c], [cn])
    assert len(r["b2b"]) == 1 and r["b2b"][0]["gstin"] == "10FZTPA0354J1ZJ"
    rates = {(x["pos"], x["rate"]): x for x in r["b2cs"]}
    assert ("10-Bihar", 5.0) in rates and ("10-Bihar", 0.0) in rates
    h1905 = [h for h in r["hsn"] if h["hsn"] == "1905"][0]
    assert h1905["qty"] == 1 and h1905["taxable"] == 50     # 2 sold - 1 credited
    assert r["totals"]["taxable"] == round(b2b["subtotal"] + b2c["subtotal"] - cn["subtotal"], 2)
    assert r["documents"]["from"] == "INV/26-27/00001" and r["documents"]["creditNotes"] == 1


def test_gstr3b_itc_utilisation():
    sale = _inv([{"qty": 1, "rate": 1000, "gstRate": 18}], True)        # output CGST 90 + SGST 90
    buy_local = {**gf.calc_gst([{"qty": 1, "rate": 500, "gstRate": 18}], True), "status": "RECEIVED", "supplierGst": "10FZTPA0354J1ZJ"}
    buy_inter = {**gf.calc_gst([{"qty": 1, "rate": 100, "gstRate": 18}], False), "status": "RECEIVED", "supplierGst": "10FZTPA0354J1ZJ"}
    no_gst = {**gf.calc_gst([{"qty": 1, "rate": 100, "gstRate": 18}], True), "status": "RECEIVED", "supplierGst": ""}
    r = gf.gstr3b([sale], [], [buy_local, buy_inter, no_gst])
    assert r["outward"]["cgst"] == 90 and r["itcDocuments"] == 2
    assert r["itcAvailable"] == {"cgst": 45.0, "sgst": 45.0, "igst": 18.0}
    # IGST credit 18 pays CGST first, then CGST 45 -> 90-18-45=27, SGST 45 -> 90-45=45
    assert r["netPayableCash"]["cgst"] == 27 and r["netPayableCash"]["sgst"] == 45 and r["netPayableCash"]["total"] == 72


def test_ageing_buckets():
    invs = [{"customerName": "A", "dueAmount": 100, "dueDate": "2026-09-29T00:00:00", "status": "UNPAID"},
            {"customerName": "A", "dueAmount": 50, "dueDate": "2026-08-01T00:00:00", "status": "PARTIAL"},
            {"customerName": "B", "dueAmount": 10, "dueDate": "2026-12-01T00:00:00", "status": "UNPAID"},
            {"customerName": "C", "dueAmount": 0, "dueDate": "2026-01-01T00:00:00", "status": "PAID"}]
    r = gf.receivables_ageing(invs, date(2026, 9, 30))
    assert r["totals"]["1-30"] == 100 and r["totals"]["31-60"] == 50 and r["totals"]["notDue"] == 10 and r["totals"]["total"] == 160
