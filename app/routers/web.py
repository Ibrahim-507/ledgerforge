"""A small login page at  http://127.0.0.1:8000/  so people can log in, try the API and see 401 / 403 answers.
The page is plain HTML + JavaScript. It only calls the same secured API routes: the SERVER still decides who may do what."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LedgerForge login</title>
<style>
 :root{--bg:#f4f6f9;--card:#fff;--ink:#1b2430;--muted:#5d6b7c;--line:#d9e0e8;--navy:#1f3a5f;--ok:#1a7f4b;--bad:#b3261e}
 @media (prefers-color-scheme:dark){:root{--bg:#10151c;--card:#18202a;--ink:#e8edf3;--muted:#9aa8b8;--line:#2a3441;--navy:#5b8bd0;--ok:#4cc38a;--bad:#ff7a70}}
 *{box-sizing:border-box} body{margin:0;font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--ink)}
 main{max-width:880px;margin:0 auto;padding:24px 16px 48px} h1{font-size:22px;margin:0 0 4px} p.sub{margin:0 0 20px;color:var(--muted)}
 .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px}
 label{display:block;font-weight:600;margin:10px 0 4px} input{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--ink);font:inherit}
 button{padding:9px 14px;border:0;border-radius:8px;background:var(--navy);color:#fff;font:inherit;font-weight:600;cursor:pointer;margin:4px 6px 4px 0}
 button.ghost{background:transparent;color:var(--navy);border:1px solid var(--navy)} .row{display:flex;gap:12px;flex-wrap:wrap} .row>div{flex:1;min-width:200px}
 .badge{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:700;color:#fff;background:var(--muted)} .b200{background:var(--ok)} .b4{background:var(--bad)}
 pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:12px;max-height:380px;overflow:auto;margin:10px 0 0}
 .muted{color:var(--muted);font-size:13px} .hide{display:none} .who b{color:var(--navy)}
</style></head><body><main>
<h1>LedgerForge</h1><p class="sub">Payroll and accounting API. Log in, then try the buttons. The server checks your role on every request.</p>

<section class="card" id="loginCard">
 <h2 style="margin-top:0;font-size:17px">Log in</h2>
 <label for="u">Username</label><input id="u" autocomplete="username" placeholder="name@znova-demo.example">
 <label for="p">Password</label><input id="p" type="password" autocomplete="current-password" placeholder="password">
 <div style="margin-top:12px"><button id="loginBtn">Log in</button></div>
 <div id="loginMsg" class="muted"></div>
</section>

<section class="card hide" id="appCard">
 <div class="who">Logged in as <b id="whoName"></b> (<span id="whoRole"></span>, employee <span id="whoEmp"></span>).
  <span class="muted">Your token lasts 30 minutes.</span> <button class="ghost" id="logoutBtn">Log out</button></div>
 <h3 style="font-size:15px;margin:16px 0 4px">Quick tries</h3>
 <button data-get="/auth/me">My profile</button>
 <button data-get="/employees">List all employees (HR/Admin)</button>
 <button data-get="/payroll-runs">Payroll runs (HR/Admin)</button>
 <button data-get="/reports/balance-sheet?as_of=2026-09-30">Balance sheet (Admin)</button>
 <button data-get="/reports/statutory-summary">PF / ESI / TDS summary (HR/Admin)</button>
 <h3 style="font-size:15px;margin:16px 0 4px">Payslips</h3>
 <div class="row"><div><label for="emp">Employee id</label><input id="emp" placeholder="EMP-0002"></div>
 <div><label for="run">Payroll run</label><input id="run" value="PR-2025-04"></div></div>
 <button id="slipBtn">Show payslip</button><button id="pdfBtn" class="ghost">Open PDF</button>
 <div class="muted">Change the employee id to someone else's: an Employee gets 403, HR and Admin get the payslip.</div>
</section>

<section class="card hide" id="outCard"><span class="badge" id="status">-</span> <b id="what"></b><pre id="out"></pre></section>
</main>
<script>
(function(){
 var $=function(id){return document.getElementById(id)}; var token=sessionStorage.getItem("lf_token");
 function show(code,what,body){var b=$("status");b.textContent=code;b.className="badge "+(code==200?"b200":(code>=400?"b4":""));
  $("what").textContent=what;$("out").textContent=typeof body==="string"?body:JSON.stringify(body,null,2);$("outCard").classList.remove("hide");}
 function setUser(u){$("whoName").textContent=u.username||u.user_id;$("whoRole").textContent=u.role;$("whoEmp").textContent=u.employee_id||"-";
  if(!$("emp").value&&u.employee_id){$("emp").value=u.employee_id;}
  $("loginCard").classList.add("hide");$("appCard").classList.remove("hide");}
 function api(path,opts){opts=opts||{};opts.headers=Object.assign({},opts.headers||{});if(token){opts.headers["Authorization"]="Bearer "+token;}return fetch(path,opts);}
 function logout(msg){token=null;sessionStorage.removeItem("lf_token");$("appCard").classList.add("hide");$("outCard").classList.add("hide");$("loginCard").classList.remove("hide");$("loginMsg").textContent=msg||"";}
 async function callJson(path){var r=await api(path);var t=await r.text();var d;try{d=JSON.parse(t)}catch(e){d=t}
  if(r.status===401&&token&&path!=="/auth/me"){/* token expired or user deactivated */}
  show(r.status,"GET "+path,d);return r;}
 async function loadMe(){var r=await api("/auth/me");if(r.status===200){setUser(await r.json());return true}logout(r.status===401?"Please log in again.":"");return false}
 $("loginBtn").onclick=async function(){$("loginMsg").textContent="Signing in...";
  try{var r=await fetch("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:$("u").value.trim(),password:$("p").value})});
   var d=await r.json();
   if(r.status===200){token=d.access_token;sessionStorage.setItem("lf_token",token);$("p").value="";$("loginMsg").textContent="";await loadMe();show(200,"POST /auth/login",{role:d.role,expires_in_seconds:d.expires_in,token_type:d.token_type});}
   else{$("loginMsg").textContent=(d.detail||"Login failed")+" (HTTP "+r.status+")";}}
  catch(e){$("loginMsg").textContent="Could not reach the server: "+e;}};
 $("p").addEventListener("keydown",function(e){if(e.key==="Enter"){$("loginBtn").click();}});
 $("logoutBtn").onclick=function(){logout("You are logged out.")};
 document.querySelectorAll("[data-get]").forEach(function(b){b.onclick=function(){callJson(b.getAttribute("data-get"))}});
 $("slipBtn").onclick=function(){callJson("/payslips/"+encodeURIComponent($("emp").value.trim())+"/"+encodeURIComponent($("run").value.trim()))};
 $("pdfBtn").onclick=async function(){var p="/payslips/"+encodeURIComponent($("emp").value.trim())+"/"+encodeURIComponent($("run").value.trim())+"/pdf";
  var r=await api(p);if(r.status===200){var blob=await r.blob();window.open(URL.createObjectURL(blob),"_blank");show(200,"GET "+p,"PDF opened in a new tab")}
  else{var t=await r.text();var d;try{d=JSON.parse(t)}catch(e){d=t}show(r.status,"GET "+p,d)}};
 if(token){loadMe();}
})();
</script></body></html>"""


@router.get("/", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store"})
