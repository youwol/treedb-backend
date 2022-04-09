from config_common import get_py_youwol_env, on_before_startup, cache_prefix

from youwol_tree_db_backend import Configuration
from youwol_utils import DocDbClient, AuthClient, LocalCacheClient
from youwol_utils.context import ConsoleContextLogger
from youwol_utils.http_clients.tree_db_backend import create_doc_dbs
from youwol_utils.middlewares import Middleware
from youwol_utils.servers.fast_api import FastApiMiddleware, ServerOptions, AppConfiguration


def get_auth_token(env, url_cluster: str):
    return next(t['value'] for t in env['tokensCache'] if t['dependencies']['host'] == url_cluster)


async def get_configuration():

    env = await get_py_youwol_env()
    openid_host = env['k8sInstance']['openIdConnect']['host']
    url_cluster = env['k8sInstance']['host']
    auth_token = get_auth_token(env, url_cluster)

    doc_dbs = create_doc_dbs(
        factory_db=DocDbClient,
        url_base=f"https://{url_cluster}/api/docdb",
        replication_factor=2
    )

    auth_client = AuthClient(url_base=f"https://{openid_host}/auth")
    cache_client = LocalCacheClient(prefix=cache_prefix)

    service_config = Configuration(
        doc_dbs=doc_dbs,
        admin_headers={'authorization': f'Bearer {auth_token}'}
    )

    async def _on_before_startup():
        await on_before_startup(service_config)

    server_options = ServerOptions(
        root_path="",
        http_port=env['portsBook']['tree-db-backend'],
        base_path="",
        middlewares=[FastApiMiddleware(Middleware, {
            "auth_client": auth_client,
            "cache_client": cache_client
        })],
        on_before_startup=_on_before_startup,
        ctx_logger=ConsoleContextLogger()
    )
    return AppConfiguration(
        server=server_options,
        service=service_config
    )
