import os
import sys
from dataclasses import dataclass
from typing import Callable, Dict, Union, Type, Any

from youwol_utils import (
    LocalDocDbClient, DocDbClient, AuthClient, CacheClient, LocalCacheClient,
    find_platform_path,
    get_valid_bucket_name, get_headers_auth_admin_from_env, get_headers_auth_admin_from_secrets_file, log_info,
)
from youwol_utils.context import ContextLogger, DeployedContextLogger
from youwol_utils.middlewares import Middleware
from youwol_utils.middlewares.authentication_local import AuthLocalMiddleware
from .models import (create_doc_dbs, DocDbs)

namespace = "tree-db"

AuthMiddleware = Union[Type[Middleware], Type[AuthLocalMiddleware]]


@dataclass(frozen=True)
class Configuration:
    open_api_prefix: str
    http_port: int
    base_path: str

    doc_dbs: DocDbs

    auth_middleware: AuthMiddleware
    auth_middleware_args: Dict[str, any]

    admin_headers: Any

    cache_prefix: str = "treedb-backend"
    bucket: str = get_valid_bucket_name(namespace)

    namespace: str = namespace
    unprotected_paths: Callable[[str], bool] = lambda url: \
        url.path.split("/")[-1] == "healthz" or url.path.split("/")[-1] == "openapi-docs"

    public_owner = '/youwol-users'
    ctx_logger: ContextLogger = DeployedContextLogger()


async def get_tricot_config() -> Configuration:
    required_env_vars = ["AUTH_HOST", "AUTH_CLIENT_ID", "AUTH_CLIENT_SECRET", "AUTH_CLIENT_SCOPE"]
    not_founds = [v for v in required_env_vars if not os.getenv(v)]
    if not_founds:
        raise RuntimeError(f"Missing environments variable: {not_founds}")
    openid_host = os.getenv("AUTH_HOST")

    log_info("Use tricot configuration", openid_host=openid_host)
    doc_dbs = create_doc_dbs(factory_db=DocDbClient, url_base="http://docdb/api",
                             replication_factor=2)
    return Configuration(
        open_api_prefix='/api/treedb-backend',
        http_port=8080,
        base_path="",
        doc_dbs=doc_dbs,
        auth_middleware=Middleware,
        auth_middleware_args={
            "auth_client": AuthClient(url_base=f"https://{openid_host}/auth"),
            "cache_client": CacheClient(host="redis-master.infra.svc.cluster.local", prefix=Configuration.cache_prefix),
            "unprotected_paths": Configuration.unprotected_paths
        },
        admin_headers=get_headers_auth_admin_from_env()
    )


async def get_local_config() -> Configuration:
    openid_host = "gs.auth.youwol.com"
    log_info("Use local configuration")

    doc_dbs = create_doc_dbs(
        factory_db=DocDbClient,
        url_base="https://dev.platform.youwol.com/api/docdb",
        replication_factor=2
    )

    return Configuration(
        open_api_prefix='',
        http_port=2387,
        base_path="/api/treedb-backend",
        doc_dbs=doc_dbs,
        auth_middleware=Middleware,
        auth_middleware_args={
            "auth_client": AuthClient(url_base=f"https://{openid_host}/auth"),
            "cache_client": LocalCacheClient(prefix=Configuration.cache_prefix),
            "unprotected_paths": Configuration.unprotected_paths
        },
        admin_headers=get_headers_auth_admin_from_secrets_file(
            find_platform_path() / "secrets" / "tricot.json",
            "dev.platform.youwol.com",
            openid_host=openid_host
        )
    )


async def get_full_local_config() -> Configuration:
    log_info("Use full-local configuration")

    platform_path = find_platform_path()
    doc_dbs = create_doc_dbs(
        factory_db=LocalDocDbClient,
        root_path=platform_path.parent / 'drive-shared' / 'docdb')

    return Configuration(
        open_api_prefix='',
        http_port=2387,
        base_path="",
        doc_dbs=doc_dbs,
        auth_middleware=AuthLocalMiddleware,
        auth_middleware_args={},
        admin_headers=None
    )


configurations = {
    'tricot': get_tricot_config,
    'local': get_local_config,
    'full-local': get_full_local_config
}

current_configuration = None


async def get_configuration():
    global current_configuration
    if current_configuration:
        return current_configuration

    current_configuration = await configurations[sys.argv[1]]()
    return current_configuration
