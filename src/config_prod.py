import os

from config_common import on_before_startup
from youwol_tree_db_backend import Configuration
from youwol_utils import DocDbClient, get_authorization_header
from youwol_utils.clients.oidc.oidc_config import OidcInfos, PrivateClient
from youwol_utils.context import DeployedContextReporter
from youwol_utils.http_clients.tree_db_backend import create_doc_dbs
from youwol_utils.middlewares import AuthMiddleware
from youwol_utils.servers.env import OPENID_CLIENT, Env
from youwol_utils.servers.fast_api import FastApiMiddleware, ServerOptions, AppConfiguration


async def get_configuration():
    required_env_vars = OPENID_CLIENT

    not_founds = [v for v in required_env_vars if not os.getenv(v)]
    if not_founds:
        raise RuntimeError(f"Missing environments variable: {not_founds}")

    doc_dbs = create_doc_dbs(factory_db=DocDbClient, url_base="http://docdb/api", replication_factor=2)

    openid_infos = OidcInfos(
        base_uri=os.getenv(Env.OPENID_BASE_URL),
        client=PrivateClient(
            client_id=os.getenv(Env.OPENID_CLIENT_ID),
            client_secret=os.getenv(Env.OPENID_CLIENT_SECRET)
        )
    )

    async def _on_before_startup():
        await on_before_startup(service_config)

    service_config = Configuration(
        doc_dbs=doc_dbs,
        admin_headers=await get_authorization_header(openid_infos)
    )
    server_options = ServerOptions(
        root_path='/api/tree-db-backend',
        http_port=8080,
        base_path="",
        middlewares=[
            FastApiMiddleware(
                AuthMiddleware, {
                    'openid_infos': openid_infos,
                    'predicate_public_path': lambda url:
                    url.path.endswith("/healthz")
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
