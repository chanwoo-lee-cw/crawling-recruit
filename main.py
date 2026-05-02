from fastmcp import FastMCP

from db.connection import create_tables
from tools.coupang_sync_jobs import coupang_sync_jobs
from tools.get_job_candidates import get_job_candidates
from tools.get_unapplied_jobs import get_unapplied_jobs
from tools.kakaobank_sync_jobs import kakaobank_sync_jobs
from tools.list_search_presets import list_search_presets
from tools.migrate_db import migrate_db
from tools.naver_sync_jobs import naver_sync_jobs
from tools.nhn_sync_jobs import nhn_sync_jobs
from tools.remember_sync_jobs import remember_sync_jobs
from tools.add_skill_keyword import add_skill_keyword
from tools.delete_skill_keyword import delete_skill_keyword
from tools.list_skill_keywords import list_skill_keywords
from tools.save_job_evaluations import save_job_evaluations
from tools.save_search_preset import save_search_preset
from tools.skip_jobs import skip_jobs
from tools.sync_all_jobs import sync_all_jobs
from tools.sync_applications import sync_applications
from tools.sync_job_details import sync_job_details
from tools.wanted_sync_jobs import wanted_sync_jobs
from tools.woowahan_sync_jobs import woowahan_sync_jobs

mcp = FastMCP("wanted-jobs")

mcp.tool()(wanted_sync_jobs)
mcp.tool()(remember_sync_jobs)
mcp.tool()(sync_all_jobs)
mcp.tool()(nhn_sync_jobs)
mcp.tool()(naver_sync_jobs)
mcp.tool()(coupang_sync_jobs)
mcp.tool()(kakaobank_sync_jobs)
mcp.tool()(woowahan_sync_jobs)
mcp.tool()(sync_applications)
mcp.tool()(get_unapplied_jobs)
mcp.tool()(save_search_preset)
mcp.tool()(list_search_presets)
mcp.tool()(sync_job_details)
mcp.tool()(get_job_candidates)
mcp.tool()(skip_jobs)
mcp.tool()(migrate_db)
mcp.tool()(save_job_evaluations)
mcp.tool()(add_skill_keyword)
mcp.tool()(list_skill_keywords)
mcp.tool()(delete_skill_keyword)

if __name__ == "__main__":
    create_tables()
    mcp.run()
