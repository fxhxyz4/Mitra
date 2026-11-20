"""
    python scripts/smoke.py                          # http://localhost/api, needs DEMO_LOGIN=true
    python scripts/smoke.py http://192.168.0.10/api
"""
import re
import sys
import time

import httpx

B = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost/api"
c = httpx.Client(timeout=600)
failed: list[str] = []

accounts = c.get(B + "/auth/demo-accounts").json()
if not accounts:
    sys.exit("No demo accounts: start the stack with demo data and DEMO_LOGIN=true")
by_role: dict[str, str] = {}
for a in accounts:
    if a["role"] == "HEAD" and "head-sector" in a["token"]:
        continue
    by_role.setdefault(a["role"], a["token"])
TOK = {"demo-coord": by_role["COORDINATOR"], "demo-head": by_role["HEAD"], "demo-analyst": by_role["ANALYST"],
       "demo-admin": by_role["ADMIN"], "demo-ex-p01": by_role["EXECUTOR"]}
TOKENS = list(TOK)


def H(name: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOK[name]}"}


def check(name: str, r: httpx.Response, expect: int | tuple[int, ...] = 200) -> httpx.Response:
    ok = r.status_code in (expect if isinstance(expect, tuple) else (expect,))
    print(f"{'OK  ' if ok else 'FAIL'} {r.status_code} {name}" + ("" if ok else f": {r.text[:200]}"))
    if not ok:
        failed.append(name)
    return r


def ai(name: str, r: httpx.Response, token: str) -> httpx.Response:
    if r.status_code != 202:
        return check(name, r)
    job = r.json()["jobId"]
    while (s := c.get(B + f"/ai/jobs/{job}", headers=H(token)).json())["status"] in ("queued", "running"):
        time.sleep(2)
    return check(f"{name} (job)", httpx.Response(200 if s["status"] == "done" else s["error"]["status"], json=s))


def every_get() -> None:
    spec = c.get(B + "/openapi.json").json()
    ids = {
        "program_id": c.get(B + "/programs", headers=H("demo-coord")).json()[0]["id"],
        "measure_id": c.get(B + "/measures", headers=H("demo-coord")).json()[0]["id"],
        "risk_id": c.get(B + "/risks", headers=H("demo-coord")).json()[0]["id"],
        "org_unit_id": c.get(B + "/admin/org-units", headers=H("demo-admin")).json()[0]["id"],
        "user_id": c.get(B + "/admin/users", headers=H("demo-admin")).json()[0]["id"],
    }
    n = 0
    for path, ops in spec["paths"].items():
        params = re.findall(r"{(\w+)}", path)
        if "get" not in ops or any(p not in ids for p in params):
            continue
        url = path.removeprefix("/api")
        for p in params:
            url = url.replace("{" + p + "}", ids[p])
        for t in TOKENS:
            r = c.get(B + url, headers=H(t))
            n += 1
            if r.status_code >= 500:
                check(f"GET {url} as {t}", r)
    print(f"GET: {n} requests across {len(TOKENS)} roles")


def full_cycle() -> None:
    prog = c.get(B + "/programs", headers=H("demo-coord")).json()[0]["id"]
    rep = check("generate NAZK report", c.post(B + "/reports/generate", headers=H("demo-coord"),
                json={"programId": prog, "period": "2026-H1", "type": "NAZK"}), 201).json()
    for f in ("docx", "xlsx"):
        check(f"export {f}", c.get(B + f"/reports/{rep['id']}/export?format={f}", headers=H("demo-analyst")))
    check("csv", c.get(B + f"/reports/{rep['id']}/nazk?format=csv", headers=H("demo-coord")))
    integ = check("integrity + QR", c.get(B + f"/reports/{rep['id']}/integrity", headers=H("demo-coord"))).json()
    print("     verify URL:", integ.get("verifyUrl"))
    memo = check("generate INTERNAL memo", c.post(B + "/reports/generate", headers=H("demo-coord"),
                 json={"programId": prog, "period": "2026-H1", "type": "INTERNAL"}), 201).json()
    check("memo docx", c.get(B + f"/reports/{memo['id']}/export?format=docx", headers=H("demo-coord")))

    risk = c.get(B + "/risks", headers=H("demo-coord")).json()[0]["id"]
    st = check("ai status", c.get(B + "/ai/status", headers=H("demo-coord"))).json()
    print(f"     model {st.get('chatModel')}: reachable={st.get('reachable')} ready={st.get('ready')}")
    ai("explain risk", c.post(B + f"/ai/risks/{risk}/explain", headers=H("demo-coord")), "demo-coord")
    ai("weekly digest", c.post(B + "/ai/digest/weekly", headers=H("demo-head")), "demo-head")
    ai("ask (head)", c.post(B + "/ai/ask", headers=H("demo-head"), json={"question": "Які заходи прострочені?"}), "demo-head")
    ai("ask (executor)", c.post(B + "/ai/ask", headers=H("demo-ex-p01"), json={"question": "Що мені зробити?"}), "demo-ex-p01")

    mine = c.get(B + "/measures?mine=true", headers=H("demo-ex-p01")).json()
    editable = [m for m in mine if m["status"] in ("PLANNED", "IN_PROGRESS", "RETURNED")]
    if editable:
        m = editable[0]
        check("executor submit", c.post(B + f"/measures/{m['id']}/submit", headers=H("demo-ex-p01"),
              data={"resultDescription": "Проведено навчання 25 працівників, протокол № 12 від 01.07.2026"},
              files=[("files", ("protokol.txt", b"protokol 12", "text/plain"))]))
        check("return without comment", c.post(B + f"/measures/{m['id']}/return", headers=H("demo-coord"),
              json={"comment": ""}), 422)
        check("coordinator approve", c.post(B + f"/measures/{m['id']}/approve", headers=H("demo-coord"), json={}))
    else:
        print("SKIP executor cycle: demo-ex-p01 has no editable measures (DB already used?)")
    foreign = next(x for x in c.get(B + "/measures", headers=H("demo-coord")).json()
                   if x["id"] not in {m["id"] for m in mine})
    check("executor: foreign measure", c.get(B + f"/measures/{foreign['id']}", headers=H("demo-ex-p01")), 403)
    check("no token", c.get(B + "/measures"), 401)
    v = check("audit chain", c.get(B + "/audit/verify", headers=H("demo-admin"))).json()
    if not v.get("ok"):
        failed.append("audit chain broken")
        print("FAIL audit chain:", v)


check("health", c.get(B + "/health"))
every_get()
full_cycle()
print("\nALL OK" if not failed else f"\nFAILED ({len(failed)}): " + ", ".join(failed))
sys.exit(1 if failed else 0)
