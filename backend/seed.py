"""Seed data for GLC Zone CRM+ERP."""
from datetime import datetime, timezone, timedelta
import bcrypt
import uuid
import random


def _id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


VERTICALS = [
    "GLC Fresh", "GLC Store", "GLC Garden", "GLC Hardwares",
    "Dhani Jewellers", "India Mandi", "GLC Property", "GLC Legal",
]


async def seed_all(db):
    # ---------- Users ----------
    if await db.users.count_documents({}) == 0:
        users = [
            {"id": _id(), "name": "Bishwajeet Kumar", "email": "bishwajeet@glczone.in", "password": _hash("Admin@123"),
             "role": "Super Admin", "department": "Leadership", "avatar": "https://api.dicebear.com/7.x/initials/svg?seed=BK",
             "isActive": True, "createdAt": _now_iso()},
            {"id": _id(), "name": "Riddhi Sharma", "email": "riddhi@glczone.in", "password": _hash("Admin@123"),
             "role": "Admin", "department": "Engineering", "avatar": "https://api.dicebear.com/7.x/initials/svg?seed=RS",
             "isActive": True, "createdAt": _now_iso()},
            {"id": _id(), "name": "Dev Kumar", "email": "dev@glczone.in", "password": _hash("Admin@123"),
             "role": "Manager", "department": "Backend", "avatar": "https://api.dicebear.com/7.x/initials/svg?seed=DK",
             "isActive": True, "createdAt": _now_iso()},
            {"id": _id(), "name": "Danish Ali", "email": "danish@glczone.in", "password": _hash("Admin@123"),
             "role": "Support Executive", "department": "QA", "avatar": "https://api.dicebear.com/7.x/initials/svg?seed=DA",
             "isActive": True, "createdAt": _now_iso()},
        ]
        await db.users.insert_many(users)

    # ---------- Company Settings ----------
    if not await db.settings.find_one({"key": "company"}):
        await db.settings.insert_one({"key": "company", "value": {
            "name": "GLC Zone Private Limited",
            "address": "GLC Zone HQ, New Delhi, India",
            "gst": "07AABCG1234H1Z5",
            "pan": "AABCG1234H",
            "email": "contact@glczone.in",
            "phone": "+91 98100 12345",
            "website": "https://glczone.in",
            "logo": None,
            "financialYearStart": "04-01",
            "financialYearEnd": "03-31",
            "invoicePrefix": "INV",
            "currency": "INR",
        }})

    # ---------- Warehouses ----------
    if await db.warehouses.count_documents({}) == 0:
        whs = [
            {"id": _id(), "name": "Main Warehouse - Delhi", "city": "New Delhi", "isDefault": True, "createdAt": _now_iso()},
            {"id": _id(), "name": "GLC Store Hub - Gurugram", "city": "Gurugram", "isDefault": False, "createdAt": _now_iso()},
            {"id": _id(), "name": "GLC Fresh Cold Storage", "city": "Noida", "isDefault": False, "createdAt": _now_iso()},
        ]
        await db.warehouses.insert_many(whs)

    default_wh = await db.warehouses.find_one({"isDefault": True}, {"_id": 0})

    # ---------- Products ----------
    if await db.products.count_documents({}) == 0:
        catalog = [
            ("GLC Fresh Basmati Rice 5kg", "GLC-FR-001", "Groceries", "1006", 5, 350, 480, 520, 100, "GLC Fresh"),
            ("Organic Turmeric Powder 500g", "GLC-FR-002", "Spices", "0910", 12, 120, 195, 220, 80, "GLC Fresh"),
            ("GLC Garden Ceramic Pot Set", "GLC-GD-011", "Garden", "6912", 18, 450, 899, 999, 40, "GLC Garden"),
            ("Neem Seedling (1ft)", "GLC-GD-012", "Garden", "0602", 5, 60, 149, 179, 60, "GLC Garden"),
            ("Bosch Cordless Drill", "GLC-HW-101", "Hardware", "8467", 18, 2800, 4499, 4999, 20, "GLC Hardwares"),
            ("Stainless Screw Set 500pc", "GLC-HW-102", "Hardware", "7318", 18, 220, 449, 499, 50, "GLC Hardwares"),
            ("22K Gold Bangle 8g", "DHN-JW-201", "Jewellery", "7113", 3, 42000, 58000, 62000, 5, "Dhani Jewellers"),
            ("Silver Anklet Pair", "DHN-JW-202", "Jewellery", "7113", 3, 4500, 7999, 8999, 15, "Dhani Jewellers"),
            ("Alphonso Mangoes (Dozen)", "IM-FR-301", "Fruits", "0804", 5, 550, 899, 999, 30, "India Mandi"),
            ("Kashmiri Kesar 2g", "IM-SP-302", "Spices", "0910", 5, 800, 1499, 1699, 20, "India Mandi"),
            ("GLC Store Cotton T-Shirt", "GLC-ST-401", "Apparel", "6109", 12, 220, 599, 699, 100, "GLC Store"),
            ("Wireless Bluetooth Earbuds", "GLC-ST-402", "Electronics", "8518", 18, 1200, 2499, 2999, 25, "GLC Store"),
            ("Legal Retainer Package", "GLC-LG-501", "Services", "9982", 18, 0, 25000, 25000, 0, "GLC Legal"),
            ("Property Advisory Fee", "GLC-PR-601", "Services", "9971", 18, 0, 15000, 15000, 0, "GLC Property"),
        ]
        prods = []
        stock_items = []
        for (name, sku, cat, hsn, gst, buy, sell, mrp, minstk, vertical) in catalog:
            pid = _id()
            prods.append({
                "id": pid, "name": name, "sku": sku, "category": cat, "hsn": hsn,
                "gstRate": gst, "unit": "PCS", "buyingPrice": buy, "sellingPrice": sell,
                "mrp": mrp, "minStock": minstk, "vertical": vertical,
                "image": f"https://api.dicebear.com/7.x/shapes/svg?seed={sku}",
                "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
            stock_items.append({
                "id": _id(), "productId": pid, "warehouseId": default_wh["id"],
                "qty": random.randint(minstk + 5, minstk * 8 + 10) if minstk > 0 else 0,
                "updatedAt": _now_iso(),
            })
        await db.products.insert_many(prods)
        await db.stock_items.insert_many(stock_items)

    # ---------- Customers ----------
    if await db.customers.count_documents({}) == 0:
        customers_seed = [
            ("Aarav Sharma", "aarav@techmail.in", "+91 99999 11111", "TechMail Pvt Ltd", "07AAACT1234A1Z2", "AAACT1234A", "WHOLESALE", "GLC Store", "Delhi"),
            ("Priya Reddy", "priya@homefoods.in", "+91 99999 22222", "HomeFoods Kitchens", "29AABCH5678K1Z1", "AABCH5678K", "DISTRIBUTOR", "GLC Fresh", "Karnataka"),
            ("Rohan Patel", "rohan@buildright.co", "+91 99999 33333", "BuildRight Constructions", "27AAACB9999B1Z3", "AAACB9999B", "WHOLESALE", "GLC Hardwares", "Maharashtra"),
            ("Meera Iyer", "meera@iyerandsons.in", "+91 99999 44444", "Iyer & Sons Jewellers", "33AAACI7777Q1Z5", "AAACI7777Q", "RETAIL", "Dhani Jewellers", "Tamil Nadu"),
            ("Karan Malhotra", "karan@urbanfarms.in", "+91 99999 55555", "Urban Farms Delhi", "07AAACU1122X1Z9", "AAACU1122X", "RETAIL", "GLC Garden", "Delhi"),
            ("Sneha Gupta", "sneha@retailmart.in", "+91 99999 66666", "RetailMart", "07AAACR3344Y1Z7", "AAACR3344Y", "RETAIL", "GLC Store", "Delhi"),
            ("Vikram Singh", "vikram@vsproperties.in", "+91 99999 77777", "VS Properties", "07AAACV5566Z1Z4", "AAACV5566Z", "RETAIL", "GLC Property", "Delhi"),
            ("Ananya Das", "ananya@lawgroup.in", "+91 99999 88888", "Das Law Group", "19AAACD7788T1Z2", "AAACD7788T", "RETAIL", "GLC Legal", "West Bengal"),
        ]
        docs = []
        for (n, e, p, c, gst, pan, typ, vert, state) in customers_seed:
            docs.append({
                "id": _id(), "name": n, "email": e, "phone": p, "company": c,
                "gst": gst, "pan": pan, "type": typ, "vertical": vert,
                "state": state, "city": state, "creditLimit": 500000,
                "outstanding": 0, "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
        await db.customers.insert_many(docs)

    # ---------- Leads ----------
    if await db.leads.count_documents({}) == 0:
        sources = ["WEBSITE", "REFERRAL", "WHATSAPP", "COLD_CALL", "SOCIAL", "CAMPAIGN"]
        statuses = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]
        names = [
            ("Arjun Verma", "Verma Retail Chain", "GLC Store"),
            ("Kavya Nair", "Nair Organic Foods", "GLC Fresh"),
            ("Rahul Bansal", "Bansal Hardware Hub", "GLC Hardwares"),
            ("Isha Kapoor", "Kapoor Jewels", "Dhani Jewellers"),
            ("Neel Joshi", "Joshi Greens", "GLC Garden"),
            ("Divya Menon", "Menon Farms", "India Mandi"),
            ("Aditya Rao", "Rao Realty", "GLC Property"),
            ("Simran Kaur", "Kaur & Associates Law", "GLC Legal"),
            ("Manoj Tiwari", "Tiwari Grocers", "GLC Store"),
            ("Pooja Shah", "Shah Fresh Foods", "GLC Fresh"),
            ("Aakash Mehta", "Mehta Traders", "GLC Store"),
            ("Sanjana Rao", "Rao Interiors", "GLC Garden"),
        ]
        leads = []
        for i, (name, company, vertical) in enumerate(names):
            leads.append({
                "id": _id(), "name": name, "company": company,
                "email": f"{name.split()[0].lower()}@{company.split()[0].lower()}.in",
                "phone": f"+91 9876 5{10000+i:05d}",
                "source": random.choice(sources),
                "status": random.choice(statuses),
                "score": random.randint(20, 95),
                "value": random.randint(15000, 500000),
                "vertical": vertical,
                "tags": random.sample(["hot", "priority", "premium", "referral", "repeat"], k=2),
                "notes": f"Interested in {vertical.split()[-1].lower()} solutions.",
                "activities": [
                    {"id": _id(), "type": "call", "text": "Initial discovery call", "by": "Riddhi", "at": _now_iso()},
                    {"id": _id(), "type": "email", "text": "Sent proposal deck", "by": "Riddhi", "at": _now_iso()},
                ],
                "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
        await db.leads.insert_many(leads)

    # ---------- Deals (pipeline) ----------
    if await db.deals.count_documents({}) == 0:
        stages = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON"]
        deals = []
        customers = await db.customers.find({}, {"_id": 0}).to_list(50)
        for i in range(12):
            c = random.choice(customers)
            deals.append({
                "id": _id(),
                "title": f"{c['company']} - Q1 Deal",
                "customerId": c["id"],
                "customerName": c["name"],
                "value": random.randint(50000, 800000),
                "probability": random.choice([20, 40, 60, 80, 90]),
                "stage": random.choice(stages),
                "vertical": c.get("vertical"),
                "expectedClose": (datetime.now(timezone.utc) + timedelta(days=random.randint(5, 60))).isoformat(),
                "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
        await db.deals.insert_many(deals)

    # ---------- Orders + Invoices ----------
    if await db.sales_orders.count_documents({}) == 0:
        customers = await db.customers.find({}, {"_id": 0}).to_list(50)
        products = await db.products.find({}, {"_id": 0}).to_list(50)
        for i in range(18):
            c = random.choice(customers)
            picks = random.sample(products, k=random.randint(1, 4))
            items = []
            subtotal = cgst = sgst = 0
            for p in picks:
                qty = random.randint(1, 6)
                items.append({
                    "productId": p["id"], "name": p["name"], "hsn": p.get("hsn"),
                    "qty": qty, "rate": p["sellingPrice"], "discount": 0, "gstRate": p["gstRate"],
                })
                line = qty * p["sellingPrice"]
                subtotal += line
                cgst += line * (p["gstRate"] / 200)
                sgst += line * (p["gstRate"] / 200)
            total = subtotal + cgst + sgst
            order_id = _id()
            created = (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 90))).isoformat()
            status = random.choice(["PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"])
            order = {
                "id": order_id, "orderNo": f"SO-2026-{1001+i}",
                "customerId": c["id"], "customerName": c["name"],
                "customerGst": c.get("gst"), "customerState": c.get("state"),
                "items": items, "subtotal": round(subtotal, 2),
                "cgst": round(cgst, 2), "sgst": round(sgst, 2), "igst": 0,
                "total": round(total, 2), "status": status,
                "store": c.get("vertical") or "GLC Store", "vertical": c.get("vertical"),
                "createdAt": created, "updatedAt": created,
            }
            await db.sales_orders.insert_one(order)
            # generate invoice for most orders
            if status in ("CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"):
                paid = random.choice([0, total * 0.5, total])
                await db.invoices.insert_one({
                    "id": _id(),
                    "invoiceNo": f"INV-2026-{1001+i}",
                    "orderId": order_id, "customerId": c["id"], "customerName": c["name"],
                    "customerGst": c.get("gst"), "customerState": c.get("state"),
                    "items": items, "subtotal": round(subtotal, 2),
                    "cgst": round(cgst, 2), "sgst": round(sgst, 2), "igst": 0,
                    "total": round(total, 2),
                    "paidAmount": round(paid, 2), "dueAmount": round(total - paid, 2),
                    "status": "PAID" if paid >= total else ("PARTIAL" if paid > 0 else "UNPAID"),
                    "vertical": c.get("vertical"),
                    "invoiceDate": created,
                    "dueDate": (datetime.fromisoformat(created.replace("+00:00", "")) + timedelta(days=15)).isoformat(),
                    "createdAt": created, "updatedAt": created,
                })

    # ---------- Employees ----------
    if await db.employees.count_documents({}) == 0:
        emp_seed = [
            ("Bishwajeet Kumar", "bk@glczone.in", "Leadership", "CEO", 200000),
            ("Riddhi Sharma", "riddhi@glczone.in", "Engineering", "Full Stack Dev", 90000),
            ("Dev Kumar", "dev@glczone.in", "Engineering", "Backend Dev", 75000),
            ("Danish Ali", "danish@glczone.in", "QA", "QA Lead", 65000),
            ("Ananya Verma", "ananya@glczone.in", "Sales", "Sales Head", 95000),
            ("Rohit Sharma", "rohit@glczone.in", "Sales", "Sales Executive", 45000),
            ("Neha Gupta", "neha@glczone.in", "Accounts", "Accountant", 55000),
            ("Karthik Nair", "karthik@glczone.in", "HR", "HR Manager", 60000),
            ("Priya Menon", "priyam@glczone.in", "Operations", "Ops Manager", 70000),
            ("Mohit Yadav", "mohit@glczone.in", "Delivery", "Delivery Lead", 32000),
            ("Suraj Patil", "suraj@glczone.in", "Delivery", "Delivery Boy", 22000),
            ("Kavita Rao", "kavita@glczone.in", "Support", "Support Executive", 35000),
        ]
        emps = []
        for i, (n, e, d, role, sal) in enumerate(emp_seed):
            emps.append({
                "id": _id(), "employeeId": f"GLC{1000+i+1}", "name": n, "email": e,
                "phone": f"+91 99{i:02d}0 1{10000+i}",
                "department": d, "designation": role, "salary": sal,
                "joiningDate": (datetime.now(timezone.utc) - timedelta(days=random.randint(60, 800))).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "avatar": f"https://api.dicebear.com/7.x/initials/svg?seed={n}",
                "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
        await db.employees.insert_many(emps)

    # ---------- Attendance (last 7 days for all employees) ----------
    if await db.attendance.count_documents({}) == 0:
        emps = await db.employees.find({}, {"_id": 0}).to_list(50)
        docs = []
        for i in range(7):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            for e in emps:
                docs.append({
                    "id": _id(), "employeeId": e["id"], "date": d,
                    "status": random.choices(["PRESENT", "ABSENT", "HALF_DAY", "LATE"], weights=[80, 5, 5, 10])[0],
                    "checkIn": "09:15", "checkOut": "18:30", "createdAt": _now_iso(),
                })
        await db.attendance.insert_many(docs)

    # ---------- Leaves ----------
    if await db.leaves.count_documents({}) == 0:
        emps = await db.employees.find({}, {"_id": 0}).limit(6).to_list(6)
        leaves = []
        for e in emps:
            leaves.append({
                "id": _id(), "employeeId": e["id"], "employeeName": e["name"],
                "leaveType": random.choice(["CL", "SL", "EL"]),
                "fromDate": (datetime.now(timezone.utc) + timedelta(days=random.randint(2, 20))).strftime("%Y-%m-%d"),
                "toDate": (datetime.now(timezone.utc) + timedelta(days=random.randint(21, 24))).strftime("%Y-%m-%d"),
                "days": random.randint(1, 3),
                "reason": "Personal work",
                "status": random.choice(["PENDING", "APPROVED"]),
                "createdAt": _now_iso(),
            })
        await db.leaves.insert_many(leaves)

    # ---------- Suppliers ----------
    if await db.suppliers.count_documents({}) == 0:
        sup_seed = [
            ("Punjab Grains Ltd", "03AABCP1234A1Z1", "punjab@grains.in", "GLC Fresh"),
            ("MetroTools India", "27AABCM5678B1Z2", "sales@metrotools.in", "GLC Hardwares"),
            ("Rajasthan Silver Craft", "08AABCR9999C1Z3", "orders@rajsilver.in", "Dhani Jewellers"),
            ("GreenLeaf Nursery", "07AABCG7777D1Z4", "info@greenleaf.in", "GLC Garden"),
            ("Nashik Mango Farms", "27AABCN2222E1Z5", "sales@nashikmango.in", "India Mandi"),
        ]
        docs = []
        for (n, g, e, v) in sup_seed:
            docs.append({
                "id": _id(), "name": n, "gst": g, "email": e, "vertical": v,
                "phone": f"+91 9{random.randint(10000,99999)}55555",
                "paymentTerms": "Net 30", "rating": round(random.uniform(3.5, 4.9), 1),
                "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
        await db.suppliers.insert_many(docs)

    # ---------- Accounts (Chart) ----------
    if await db.accounts.count_documents({}) == 0:
        coa = [
            ("1100", "Cash", "ASSET"),
            ("1200", "Bank - HDFC", "ASSET"),
            ("1300", "Accounts Receivable", "ASSET"),
            ("1400", "Inventory", "ASSET"),
            ("2100", "Accounts Payable", "LIABILITY"),
            ("2200", "GST Payable", "LIABILITY"),
            ("2300", "TDS Payable", "LIABILITY"),
            ("3100", "Owners Equity", "EQUITY"),
            ("4100", "Sales Revenue", "INCOME"),
            ("4200", "Service Revenue", "INCOME"),
            ("5100", "Cost of Goods Sold", "EXPENSE"),
            ("5200", "Salaries & Wages", "EXPENSE"),
            ("5300", "Rent", "EXPENSE"),
            ("5400", "Utilities", "EXPENSE"),
            ("5500", "Travel", "EXPENSE"),
        ]
        docs = [{"id": _id(), "code": c, "name": n, "type": t, "balance": 0, "createdAt": _now_iso()} for (c, n, t) in coa]
        await db.accounts.insert_many(docs)

    # ---------- Expenses ----------
    if await db.expenses.count_documents({}) == 0:
        docs = []
        for i in range(6):
            docs.append({
                "id": _id(),
                "title": random.choice(["Office Supplies", "Client Meeting Lunch", "Cab to Airport", "Domain Renewal", "Team Snacks", "Diwali Gifts"]),
                "amount": random.randint(500, 15000),
                "category": random.choice(["Travel", "Meals", "Office", "Software"]),
                "date": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
                "submittedBy": random.choice(["Riddhi", "Dev", "Danish", "Rohit"]),
                "status": random.choice(["PENDING", "APPROVED", "REJECTED"]),
                "createdAt": _now_iso(),
            })
        await db.expenses.insert_many(docs)

    # ---------- Deliveries ----------
    if await db.deliveries.count_documents({}) == 0:
        orders = await db.sales_orders.find({"status": {"$in": ["CONFIRMED", "PROCESSING", "SHIPPED"]}}, {"_id": 0}).limit(10).to_list(10)
        docs = []
        for o in orders:
            docs.append({
                "id": _id(), "orderId": o["id"], "orderNo": o["orderNo"],
                "customerName": o["customerName"],
                "address": "Sector 44, Gurugram, Haryana",
                "assignedTo": "Suraj Patil",
                "status": random.choice(["PENDING", "ASSIGNED", "IN_TRANSIT", "DELIVERED"]),
                "otp": f"{random.randint(1000,9999)}",
                "scheduledDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
        if docs:
            await db.deliveries.insert_many(docs)

    # ---------- Projects + Tasks ----------
    if await db.projects.count_documents({}) == 0:
        projects = [
            {"id": _id(), "name": "GLC Zone ERP Rollout", "status": "ACTIVE", "budget": 2500000,
             "startDate": "2026-01-01", "endDate": "2026-06-30",
             "description": "Rollout the ERP platform across all 8 verticals.", "team": [],
             "createdAt": _now_iso()},
            {"id": _id(), "name": "Dhani Jewellers Website", "status": "ACTIVE", "budget": 450000,
             "startDate": "2026-02-01", "endDate": "2026-04-30",
             "description": "Launch premium e-comm site for Dhani.", "team": [],
             "createdAt": _now_iso()},
            {"id": _id(), "name": "GLC Fresh App Launch", "status": "ON_HOLD", "budget": 800000,
             "startDate": "2026-03-01", "endDate": "2026-07-31",
             "description": "Consumer app for GLC Fresh.", "team": [],
             "createdAt": _now_iso()},
        ]
        await db.projects.insert_many(projects)
        # tasks
        stages = ["TODO", "IN_PROGRESS", "REVIEW", "DONE"]
        tasks = []
        titles = [
            "Set up production PostgreSQL", "Design GST invoice template",
            "Kanban drag-drop bug", "Payroll module review",
            "QA - login flow", "QA - inventory adjustment",
            "Sales pipeline redesign", "Add SLA timers to tickets",
            "Employee onboarding docs", "Homepage hero for Dhani",
            "Category page for jewellery", "Fresh app auth screens",
        ]
        for i, t in enumerate(titles):
            tasks.append({
                "id": _id(), "title": t,
                "projectId": projects[i % 3]["id"], "projectName": projects[i % 3]["name"],
                "assignedTo": random.choice(["Riddhi", "Dev", "Danish", "Rohit"]),
                "assignedToName": random.choice(["Riddhi Sharma", "Dev Kumar", "Danish Ali", "Rohit Sharma"]),
                "status": random.choice(stages),
                "priority": random.choice(["LOW", "MEDIUM", "HIGH", "URGENT"]),
                "dueDate": (datetime.now(timezone.utc) + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "createdAt": _now_iso(),
            })
        await db.tasks.insert_many(tasks)

    # ---------- Tickets ----------
    if await db.tickets.count_documents({}) == 0:
        customers = await db.customers.find({}, {"_id": 0}).to_list(50)
        subjects = [
            "Delivery delayed for order SO-2026-1005",
            "Wrong item received - Ceramic Pot Set",
            "GST invoice format issue",
            "Refund not processed",
            "Product quality concern",
            "Unable to login to portal",
        ]
        docs = []
        for i, s in enumerate(subjects):
            c = random.choice(customers)
            docs.append({
                "id": _id(),
                "ticketNo": f"TKT-{1001+i:04d}",
                "subject": s, "description": s + " - please help.",
                "customerId": c["id"], "customerName": c["name"],
                "priority": random.choice(["LOW", "MEDIUM", "HIGH", "URGENT"]),
                "status": random.choice(["OPEN", "IN_PROGRESS", "RESOLVED"]),
                "assignedTo": "Danish Ali",
                "replies": [{
                    "id": _id(), "message": "Thanks, looking into it.",
                    "by": "Danish Ali", "at": _now_iso(),
                }],
                "createdAt": _now_iso(), "updatedAt": _now_iso(),
            })
        await db.tickets.insert_many(docs)

    # ---------- Documents ----------
    if await db.documents.count_documents({}) == 0:
        docs = [
            {"id": _id(), "name": "Company GST Certificate.pdf", "url": "#", "category": "LEGAL", "mime": "application/pdf", "size": 245000, "uploadedBy": "Riddhi Sharma", "createdAt": _now_iso()},
            {"id": _id(), "name": "FY-2025 P&L.xlsx", "url": "#", "category": "FINANCE", "mime": "application/xlsx", "size": 512000, "uploadedBy": "Neha Gupta", "createdAt": _now_iso()},
            {"id": _id(), "name": "Employee Handbook v2.pdf", "url": "#", "category": "HR", "mime": "application/pdf", "size": 890000, "uploadedBy": "Karthik Nair", "createdAt": _now_iso()},
            {"id": _id(), "name": "Punjab Grains Contract.pdf", "url": "#", "category": "VENDOR", "mime": "application/pdf", "size": 320000, "uploadedBy": "Bishwajeet Kumar", "createdAt": _now_iso()},
        ]
        await db.documents.insert_many(docs)

    # ---------- Notifications ----------
    if await db.notifications.count_documents({}) == 0:
        ns = [
            ("New Order Received", "Order SO-2026-1012 from RetailMart", "order"),
            ("Payment Received", "₹45,000 received from Verma Retail Chain", "payment"),
            ("Low Stock Alert", "Bosch Cordless Drill is below minimum stock", "stock"),
            ("Lead Assigned", "New lead Manoj Tiwari has been assigned to you", "lead"),
            ("Leave Approval Pending", "Rohit Sharma has applied for leave", "hr"),
        ]
        docs = []
        for (t, m, k) in ns:
            docs.append({"id": _id(), "userId": "*", "title": t, "message": m, "kind": k, "isRead": False, "createdAt": _now_iso()})
        await db.notifications.insert_many(docs)

    # ---------- Audit Logs (seed a few) ----------
    if await db.audit_logs.count_documents({}) == 0:
        docs = [
            {"id": _id(), "userId": "system", "module": "system", "action": "seed", "meta": {"note": "Initial seed complete"}, "createdAt": _now_iso()},
        ]
        await db.audit_logs.insert_many(docs)
