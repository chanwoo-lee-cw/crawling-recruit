from fastmcp import FastMCP

from db.connection import create_tables
from tools.get_job_candidates import get_job_candidates
from tools.get_unapplied_jobs import get_unapplied_jobs
from tools.list_search_presets import list_search_presets
from tools.migrate_db import migrate_db
from tools.remember_sync_jobs import remember_sync_jobs
from tools.save_job_evaluations import save_job_evaluations
from tools.save_search_preset import save_search_preset
from tools.skip_jobs import skip_jobs
from tools.sync_applications import sync_applications
from tools.sync_job_details import sync_job_details
from tools.wanted_sync_jobs import wanted_sync_jobs

mcp = FastMCP("wanted-jobs")

mcp.tool()(wanted_sync_jobs)
mcp.tool()(remember_sync_jobs)
mcp.tool()(sync_applications)
mcp.tool()(get_unapplied_jobs)
mcp.tool()(save_search_preset)
mcp.tool()(list_search_presets)
mcp.tool()(sync_job_details)
mcp.tool()(get_job_candidates)
mcp.tool()(skip_jobs)
mcp.tool()(migrate_db)
mcp.tool()(save_job_evaluations)

if __name__ == "__main__":
    create_tables()
    mcp.run()
