from pathlib import Path

from config_common import get_py_youwol_env, on_before_startup

from youwol_tree_db_backend import Configuration

from youwol_utils import LocalDocDbClient
from youwol_utils.context import ConsoleContextReporter
from youwol_utils.http_clients.tree_db_backend import create_doc_dbs
from youwol_utils.middlewares.authentication_local import AuthLocalMiddleware
from youwol_utils.servers.fast_api import FastApiMiddleware, ServerOptions, AppConfiguration


async def get_configuration():

    env = await get_py_youwol_env()
    databases_path = Path(env['pathsBook']['databases'])

    doc_dbs = create_doc_dbs(
        factory_db=LocalDocDbClient,
        root_path=databases_path / 'docdb')

    async def _on_before_startup():
        await on_before_startup(service_config)

    service_config = Configuration(
        doc_dbs=doc_dbs
    )
    server_options = ServerOptions(
        root_path="",
        http_port=env['portsBook']['tree-db-backend'],
        base_path="",
        middlewares=[FastApiMiddleware(AuthLocalMiddleware, {})],
        on_before_startup=_on_before_startup,
        ctx_logger=ConsoleContextReporter()
    )
    return AppConfiguration(
        server=server_options,
        service=service_config
    )
