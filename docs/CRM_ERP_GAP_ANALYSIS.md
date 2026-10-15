# GLC Zone CRM + ERP: kya hai, kya kam hai (gap analysis)

Yeh report CRM ke poore code ko padhkar aur CRM/ERP ke market ke common features se milakar banayi gayi hai. CRM chalakar nahi dekha gaya, isliye jo "hai" ya "nahi hai" likha hai woh code padhkar likha hai.
Status: **Hai** = kaam karta hai. **Adhura** = hai par kuch kam. **Nahi** = bilkul nahi hai.
Priority: **P1** abhi (paisa/data/security ka khatra), **P2** agle (roz ka kaam tez karta hai), **P3** baad mein (achha hota hai).
Mehnat: **S** 1 din tak, **M** 2 se 4 din, **L** 1 hafta ya zyada.

**Update (15 Oct 2026):** neeche **Hua** wale kaam ho chuke hain aur server par chal rahe hain (PR #20 se #27). Ye sab in-memory database wale tests aur code padhkar check hue hain, asli data par har ek screen nahi chalayi gayi. Jo Adhura/Nahi hai woh abhi baaki hai.

## 0. Pehle sabse zaroori (P1)

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 0.1 | 2FA ke baad ka temporary token asli login token jaisa chalta hai, 2FA bypass | **Hua** | S |
| 0.2 | Server par role ki jaanch nahi: telecaller bhi withdrawal approve, payroll dekhna, delete kar sakta hai | **Hua** | M |
| 0.3 | `/users` sabko 2FA secrets ke saath dikhata hai | **Hua** | S |
| 0.4 | `JWT_SECRET` na ho to server code ka default secret use karta hai; login 7 din chalta hai | **Hua** (server par `JWT_SECRET` set hai; `REQUIRE_JWT_SECRET=1` abhi on karna baaki) | S |
| 0.5 | Login, OTP, PIN par brute-force rok (lock) nahi | **Hua** (login par; OTP/PIN par alag se dekhna) | S |
| 0.6 | Update routes poori body seedha database mein likhte hain (status, total badal sakte hain) | **Hua** (sab update routes ka safe_fields; naye route banate waqt dhyan rakhna) | M |
| 0.7 | Upload ki hui HTML file CRM ke andar chal sakti hai | **Hua** | S |
| 0.8 | Search mein `+91` ya `(` likho to server error; page khaali dikhta hai | **Hua** | S |
| 0.9 | "Cancel" likhne wala customer chupchap opt-out ho jaata hai | **Hua** | S |
| 0.10 | Database mein koi index nahi | **Hua** | S |

## 1. Logs, audit aur nigrani

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 1.1 | Audit Log: har badlav (kisne, kya, kis item par, safal ya fail, kis IP se). Pehle sirf 21 jagah likha jaata tha, user ka naam nahi dikhta tha, filter ya paging nahi thi | **Is PR mein** | done |
| 1.2 | Badlav se pehle aur baad ki value (kis field ko kya se kya kiya) | Nahi | M |
| 1.3 | Login history: kaun kab kahan se aaya, fail hue login, naye device ka alert | Adhura (fail login log hota hai; login history ka screen nahi) | S |
| 1.4 | Delete karne par recycle bin (galti se delete hua to wapas) | Nahi | M |
| 1.5 | Error aur background kaam (WhatsApp send fail, website sync fail) ka ek "System health" page | Nahi | M |
| 1.6 | Purane log ka safaya aur archive (jaise 1 saal baad) | Nahi | S |

## 2. Leads aur sales (CRM ka dil)

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 2.1 | Follow-up: aaj ke, overdue, next date, har lead par note aur call ka result. Abhi `followUpDate` save hota hai par screen par nahi dikhta | **Hua** | M |
| 2.2 | Lead ki detail aur timeline (kab aaya, kisne call kiya, kya kaha) aur edit ka button | **Hua** (timeline aur edit; lead detail ka alag poora page nahi) | M |
| 2.3 | Duplicate rokna (same phone/email par lead ya customer) aur merge | **Hua** (rokna; merge nahi) | M |
| 2.4 | Lead ko apne aap bantna (round robin), "My leads" filter | Adhura (My follow-ups hai; auto round-robin nahi) | M |
| 2.5 | Lead score (kitna garam lead hai) | Adhura (score field hai, hisaab nahi) | M |
| 2.6 | Pipeline mein Lost ka column aur lost ka karan | **Hua** (Lost ke liye karan zaroori) | S |
| 2.7 | Sab tables mein sort, filter, bulk action (ek saath assign/close/delete) aur Excel export | Adhura (Leads par filter/sort hai; bulk aur Excel nahi) | M |
| 2.8 | Sab lists mein 50 se zyada rows ka paging | Adhura (Leads, Audit Log par paging hai; baaki lists par nahi) | S |
| 2.9 | Subah ka digest (aaj ke follow-up WhatsApp/notification par) | Nahi | M |
| 2.10 | Quotation: follow-up reminder, accept/reject link customer ke liye | Adhura | M |

## 3. WhatsApp aur inbox

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 3.1 | Send fail (24 ghante ka rule, opt-out) agent ko saaf dikhana, aur window band hone par seedha template bhejna | Adhura (fail "bhej diya" jaisa dikhta hai) | M |
| 3.2 | Photo, PDF, voice bhejna aur dikhana | **Hua** (customer ki photo/voice/document chat mein khulti hai; agent se bhejna abhi nahi) | M |
| 3.3 | Zara wapas on karna (staff ke jawab ke baad AI hamesha band rehta hai) | Nahi | S |
| 3.4 | Chat ke saath lead, customer, orders, tickets ek panel mein, aur chat se lead/ticket banana | Nahi | M |
| 3.5 | Telecaller ke role ko Inbox ka access | Nahi | S |
| 3.6 | Phone number se chat search, 24 ghante ka countdown, opt-out ka nishan | Nahi | S |
| 3.7 | Saved replies (quick replies) ki list aur chat ka tag | Adhura | S |
| 3.8 | Sabse pehle jawab dene ka SLA aur late chats ki list | Nahi | M |
| 3.9 | Live updates (abhi har 4-6 second poll karta hai) | Adhura | M |
| 3.10 | Opt-out ke shabdon ki sahi list aur customer ko "unsubscribe ho gaye" ka message | **Hua** | S |

## 4. Orders, invoices, stock, purchase (ERP)

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 4.1 | Document ke number (quotation, order, PO, ticket) `count + 1` se bante hain: ek jaisa number ya delete ke baad repeat. Invoice ka number sahi hai | **Hua** | S |
| 4.2 | Stock: negative na jaye, cancel/return/credit note par wapas aaye, har badlav ka stock ledger | Adhura (negative nahi jata, cancel aur credit note par wapas aata hai; stock ledger nahi) | M |
| 4.3 | Double click par do invoice, do customer, do payment | **Hua** | S |
| 4.4 | Batch aur expiry (FEFO: jo pehle expire hoga woh pehle jaye), expiry ke 30, 15, 7 din pehle alert. Grocery ke liye zaroori | Nahi | L |
| 4.5 | Kai godown ke beech stock transfer aur har godown ka alag stock | Adhura (stock row hai, transfer nahi) | M |
| 4.6 | Reorder point (stock kam ho to apne aap PO ka suggestion) | Adhura (low stock ginti hai) | M |
| 4.7 | Customer ki udhaari: outstanding aur credit limit (abhi hamesha 0) | Nahi | M |
| 4.8 | Supplier ka payable, payment aur ageing | Adhura | M |
| 4.9 | Sales return (customer se saman wapas) ka poora flow | Adhura (credit note stock wapas karta hai; poora return flow nahi) | M |
| 4.10 | Barcode scan (billing aur stock ke liye) | Nahi | M |

## 5. India ke hisaab se (GST, payroll)

Neeche ke points internet research se hain (vendor blogs, isliye lagu hone se pehle GST portal ya CA se confirm karo).

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 5.1 | E-invoice: IRN aur QR code, GST portal par bhejna (turnover ki seema par depend karta hai, CA se poochho) | Nahi | L |
| 5.2 | E-way bill (IRN se banta hai) | Nahi | L |
| 5.3 | GSTR-1 aur GSTR-3B ka draft | Hai | |
| 5.4 | GSTR-2B se purchase ka milan (reconciliation) | Nahi | L |
| 5.5 | GSTIN ki jaanch customer/supplier save karte waqt (function hai par laga nahi) | Adhura | S |
| 5.6 | GST report abhi UTC date par chalti hai: raat 12 se subah 5:30 ke bech ki sales galat mahine mein ginti hai | **Hua** | S |
| 5.7 | Payroll: PF, ESI aur TDS ke rate code mein fixed hain, aur attendance/leave se jude nahi (LOP nahi katta) | Adhura (LOP, PF ceiling, ESI limit lag gaye; TDS sirf andaza; rates abhi code mein) | M |
| 5.8 | Payslip (PDF) aur salary ka "paid" status aur journal | Nahi | M |
| 5.9 | Leave ka balance aur overlap ki rok | Nahi | M |

## 6. Reports aur dashboard

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 6.1 | Dashboard ke kuch numbers galat: vertical filter na lagna, LOST ka ginna, mahine ka hisaab | Adhura (mahine ka hisaab IST par theek hua; baaki dekhna) | S |
| 6.2 | Telecaller ki report: kitne call, kitne convert, kitni der mein jawab | Nahi | M |
| 6.3 | Lead source ki report (website, WhatsApp, career): kahan se kitne aur kitne bik gaye | Nahi | M |
| 6.4 | Franchise ki report (kitna purchase, kitna commission) CRM mein | Nahi | M |
| 6.5 | Report ko Excel/PDF mein nikalna aur mail par schedule karna | Nahi | M |
| 6.6 | Dashboard khud refresh ho (abhi "real-time" likha hai par nahi hota) | Adhura | S |

## 7. UI aur UX

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 7.1 | Load fail hone par "No leads yet" dikhta hai, error aur Retry nahi | Adhura (Leads par error aur Retry hai; baaki pages par nahi) | S |
| 7.2 | Phone par Inbox (list aur chat alag screen) aur Pipeline (touch par drag nahi chalta) | Adhura | M |
| 7.3 | Form ki jaanch (phone, email, GSTIN ka format) aur saaf error message | Adhura | S |
| 7.4 | Role ke hisaab se button chhupana (delete sabko dikhta hai) | Adhura | S |
| 7.5 | Hindi/English ka option (abhi sirf English, lead ke notes Hinglish mein hain) | Nahi | M |
| 7.6 | Keyboard aur screen reader (aria label, focus) | Adhura | M |
| 7.7 | Tickets mein SLA (subtitle mein likha hai par field nahi) | Nahi | M |
| 7.8 | Kaam ka board (tasks) mein assignee chunna aur due date ki yaad | Adhura | S |
| 7.9 | 401 par `/login` par bhejta hai jabki app `/crm` ke andar hai | **Hua** | S |

## 8. Jodna (integrations) aur automation

| # | Kya | Status | Mehnat |
|---|---|---|---|
| 8.1 | Website ke saath: order, lead, ticket, career hai. Franchise aur grocery ke events CRM mein nahi | Adhura | M |
| 8.2 | Automation rules ("lead 2 din se untouched hai to manager ko batao", "invoice 7 din se unpaid") | Nahi | L |
| 8.3 | Email aur SMS (SMS ke liye DLT register chahiye) | Adhura | L |
| 8.4 | Payment gateway ka link invoice par (UPI/Razorpay) aur auto reconcile | Nahi | L |
| 8.5 | Backup: database ka roz ka backup aur restore ka test | Maloom nahi (server par dekho) | S |
| 8.6 | Mobile app ya PWA (telecaller phone par call/WhatsApp se jude) | Nahi | L |

## Salah: kis kram mein

1. **Phase 1 (P1, 1 hafta):** 0.1 se 0.10 aur 4.1, 4.3, 5.6. Security aur paise ka khatra pehle.
2. **Phase 2 (telecaller ka kaam):** 2.1 se 2.4, 2.7, 2.8, 3.1, 3.3 se 3.5, 7.1. Isse team ka roz ka kaam sabse zyada tez hoga.
3. **Phase 3 (ERP ka hisaab):** 4.2, 4.4 se 4.7, 5.5, 5.7 se 5.9, 6.x.
4. **Phase 4:** e-invoice aur e-way bill (CA se pehle baat), automation, mobile.

## Sources (research)
- [E-invoicing for small businesses in India (2026)](https://www.lendingkart.com/blog/what-is-e-invoicing-benefits-rules-applicability-small-businesses-india/)
- [How to generate e-invoice under GST (2026)](https://www.logicerp.com/blog/how-to-generate-e-invoice-under-gst-in-india-2026-complete-guide-with-process-format-software/)
- [Lead routing software: features and setup](https://www.kixie.com/sales-blog/lead-routing-software/)
- [How to route leads automatically](https://databar.ai/blog/article/how-to-route-leads-automatically-lead-assignment-best-practices)
- [CRM for lead management (Vtiger)](https://www.vtiger.com/blog/crm-for-lead-management/)
- [The 24-hour rule for WhatsApp](https://timelines.ai/24-hour-rule-whatsapp)
- [WhatsApp 24-hour window explained for developers](https://kapso.ai/blog/whatsapp-24-hour-rule-service-window)
- [Supermarket ERP inventory features](https://www.logicerp.com/blog/top-inventory-management-features-every-supermarket-erp-software-should-have/)
- [How food distributors track expiry across warehouses](https://www.vai.net/resources/blog/how-food-distributors-track-expiration-dates-across-multiple-warehouses)

Yeh zyadatar vendor ke blog hain, isliye unke daave "market kya maanta hai" ke roop mein lo, pakki salah ke roop mein nahi. GST ki seema aur niyam GST portal ya CA se confirm karo.
