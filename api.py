import argparse
import importlib.metadata
import os.path

import uvicorn
from fastapi import FastAPI

from app.fastapi_extends.responses import JSONResponse
from app.routes import mount_all_routes
from app.utils import write_fake_config


def main():
    parser = argparse.ArgumentParser(prog='OpenSPG API Server', description='An OpenSPG Knowledge Base API Server')
    parser.add_argument('--host', type=str, default="127.0.0.1")
    parser.add_argument('--port', type=int, default=9999)
    parser.add_argument('--servlet', type=str, default='/api')
    parser.add_argument('--desc', type=str, default='OpenSPG API Server')
    parser.add_argument('--openspg-service', type=str, default='http://127.0.0.1:8887')
    parser.add_argument('--openspg-modules', action="store", type=str, nargs='*', default=[])
    args = parser.parse_args()

    print(args)

    write_fake_config(os.path.join(os.path.dirname(__file__), 'kag_config.yaml'), args.openspg_service)

    kag_version = importlib.metadata.version('openspg-kag')
    print(f'OpenSPG-KAG version: {kag_version}')

    app = FastAPI(
        title=args.desc,
        version=kag_version,
        default_response_class=JSONResponse,
        response_model_exclude_none=True,
        openapi_url=f'{args.servlet}/openapi.json',
    )

    mount_all_routes(app, args)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == '__main__':
    main()
