from fastmcp import FastMCP
from db.connection import create_tables
from tools.sync_jobs import sync_jobs
from tools.sync_applications import sync_applications
from tools.get_unapplied_jobs import get_unapplied_jobs
from tools.save_search_preset import save_search_preset
from tools.list_search_presets import list_search_presets
from tools.sync_job_details import sync_job_details
from tools.recommend_jobs import recommend_jobs

mcp = FastMCP("wanted-jobs")

mcp.tool()(sync_jobs)
mcp.tool()(sync_applications)
mcp.tool()(get_unapplied_jobs)
mcp.tool()(save_search_preset)
mcp.tool()(list_search_presets)
mcp.tool()(sync_job_details)
mcp.tool()(recommend_jobs)

if __name__ == "__main__":
    create_tables()
    mcp.run()
