import os

from config_common import on_before_startup, cache_prefix

from youwol_tree_db_backend import Configuration

from youwol_utils import DocDbClient, AuthClient, CacheClient, get_headers_auth_admin_from_env
from youwol_utils.context import DeployedContextReporter
from youwol_utils.http_clients.tree_db_backend import create_doc_dbs
from youwol_utils.middlewares import Middleware
from youwol_utils.servers.fast_api import FastApiMiddleware, ServerOptions, AppConfiguration


async def get_configuration():
    required_env_vars = ["AUTH_HOST", "AUTH_CLIENT_ID", "AUTH_CLIENT_SECRET", "AUTH_CLIENT_SCOPE"]

    not_founds = [v for v in required_env_vars if not os.getenv(v)]
    if not_founds:
        raise RuntimeError(f"Missing environments variable: {not_founds}")

    doc_dbs = create_doc_dbs(factory_db=DocDbClient, url_base="http://docdb/api", replication_factor=2)

    openid_host = os.getenv("AUTH_HOST")
    auth_client = AuthClient(url_base=f"https://{openid_host}/auth")

    cache_client = CacheClient(host="redis-master.infra.svc.cluster.local", prefix=cache_prefix)

    async def _on_before_startup():
        await on_before_startup(service_config)

    service_config = Configuration(
        doc_dbs=doc_dbs,
        admin_headers=await get_headers_auth_admin_from_env()
    )
    server_options = ServerOptions(
        root_path='/api/tree-db-backend',
        http_port=8080,
        base_path="",
        middlewares=[
            FastApiMiddleware(
                Middleware, {
                    "auth_client": auth_client,
                    "cache_client": cache_client,
                    # healthz need to not be protected as it is used for liveness prob
                    "unprotected_paths": lambda url: url.path.split("/")[-1] == "healthz"
                }
            )
        ],
        on_before_startup=_on_before_startup,
        ctx_logger=DeployedContextReporter()
    )
    return AppConfiguration(
        server=server_options,
        service=service_config
    )
