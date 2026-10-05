import sqlite3
import time
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from ..db import get_conn
from ..security import current_user
from ..services import assistant, audit, reports

router = APIRouter(prefix="/api", tags=["assistant", "reports"])


class Query(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@router.post("/assistant/query")
def assistant_query(body: Query, conn: sqlite3.Connection = Depends(get_conn), user=Depends(current_user)):
    t0 = time.time()
    res = assistant.answer(conn, body.question)
    res["elapsed_s"] = round(time.time() - t0, 3)
    audit.log(conn, user["username"], "assistant_query", "assistant", "", {"q": body.question, "intent": res["intent"]})
    return res


@router.get("/assistant/examples")
def examples(_=Depends(current_user)):
    return assistant.HELP


@router.get("/reports/{report_id}")
def get_report(report_id: str, format: str = "html", conn: sqlite3.Connection = Depends(get_conn), user=Depends(current_user)):
    """report_id: «management» | شناسه تجهیز (EQ-…) | شناسه NDT (NDT-…)."""
    if format not in ("html", "xlsx", "pdf"):
        raise HTTPException(422, "فرمت باید html، xlsx یا pdf باشد")
    if report_id == "management":
        rep = reports.management_report(conn)
    elif report_id.startswith("NDT-"):
        rep = reports.ndt_report(conn, report_id)
    else:
        rep = reports.equipment_report(conn, report_id)
    if not rep:
        raise HTTPException(404, "گزارش یافت نشد")
    audit.log(conn, user["username"], "report", "report", report_id, {"format": format})
    fname = quote(f"report-{report_id}.{format}")
    if format == "html":
        return HTMLResponse(reports.to_html(rep))
    if format == "xlsx":
        return Response(reports.to_xlsx(rep), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})
    if not reports.pdf_available():
        raise HTTPException(501, "تولید PDF نیازمند فونت فارسی و کتابخانه arabic-reshaper است؛ از فرمت html یا xlsx استفاده کنید")
    return Response(reports.to_pdf(rep), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})
